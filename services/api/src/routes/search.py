"""Scene search endpoint with hybrid retrieval (dense + lexical + RRF)."""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user, User
from ..config import settings
from ..domain.schemas import SearchRequest, SearchResponse, VideoSceneResponse
from ..domain.search.fusion import (
    rrf_fuse,
    dense_only_fusion,
    lexical_only_fusion,
    Candidate,
    FusedCandidate,
)
from ..adapters.database import db
from ..adapters.openai_client import openai_client
from ..adapters.opensearch_client import opensearch_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_dense_search(
    query_embedding: list[float],
    user_id: UUID,
    video_id: Optional[UUID],
    limit: int,
    threshold: float,
) -> tuple[list[Candidate], int]:
    """Run dense vector search and return candidates with timing.

    Returns:
        tuple: (list of Candidate objects, elapsed time in ms)
    """
    start = time.time()
    scenes = db.search_scenes(
        query_embedding=query_embedding,
        limit=limit,
        threshold=threshold,
        video_id=video_id,
        user_id=user_id,
    )
    elapsed_ms = int((time.time() - start) * 1000)

    candidates = []
    for rank, scene in enumerate(scenes, start=1):
        candidates.append(Candidate(
            scene_id=str(scene.id),
            rank=rank,
            score=scene.similarity or 0.0,
        ))

    return candidates, elapsed_ms


def _run_lexical_search(
    query: str,
    user_id: UUID,
    video_id: Optional[UUID],
    limit: int,
) -> tuple[list[Candidate], int]:
    """Run BM25 lexical search and return candidates with timing.

    Returns:
        tuple: (list of Candidate objects, elapsed time in ms)
    """
    start = time.time()

    results = opensearch_client.bm25_search(
        query=query,
        owner_id=str(user_id),
        video_id=str(video_id) if video_id else None,
        size=limit,
    )

    elapsed_ms = int((time.time() - start) * 1000)

    candidates = []
    for result in results:
        candidates.append(Candidate(
            scene_id=result["scene_id"],
            rank=result["rank"],
            score=result["score"],
        ))

    return candidates, elapsed_ms


def _hydrate_scenes(
    fused_results: list[FusedCandidate],
) -> tuple[list[VideoSceneResponse], int]:
    """Fetch full scene data for fused results.

    Returns:
        tuple: (list of VideoSceneResponse objects, elapsed time in ms)
    """
    if not fused_results:
        return [], 0

    start = time.time()

    # Get scene IDs in fused order
    scene_ids = [UUID(r.scene_id) for r in fused_results]

    # Fetch scenes from database
    scenes = db.get_scenes_by_ids(scene_ids, preserve_order=True)

    # Build lookup for fused scores
    fused_scores = {r.scene_id: r.fused_score for r in fused_results}

    # Convert to response objects
    responses = []
    for scene in scenes:
        responses.append(VideoSceneResponse(
            id=scene.id,
            video_id=scene.video_id,
            index=scene.index,
            start_s=scene.start_s,
            end_s=scene.end_s,
            transcript_segment=scene.transcript_segment,
            visual_summary=scene.visual_summary,
            combined_text=scene.combined_text,
            thumbnail_url=scene.thumbnail_url,
            visual_description=scene.visual_description,
            visual_entities=scene.visual_entities,
            visual_actions=scene.visual_actions,
            tags=scene.tags,
            similarity=fused_scores.get(str(scene.id)),  # Use fused score as similarity
            created_at=scene.created_at,
        ))

    elapsed_ms = int((time.time() - start) * 1000)
    return responses, elapsed_ms


@router.post("/search", response_model=SearchResponse)
async def search_scenes(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Search for video scenes using natural language.

    Uses hybrid search combining:
    - Dense vector search (pgvector) for semantic similarity
    - BM25 lexical search (OpenSearch) for keyword matching
    - Reciprocal Rank Fusion (RRF) to combine results

    Falls back to dense-only if OpenSearch is unavailable.

    Args:
        request: Search request parameters including query text, filters, and limits.
        current_user: The authenticated user (injected).

    Returns:
        SearchResponse: Search results including matching scenes, total count, and latency.

    Raises:
        HTTPException:
            - 404: If the specified video is not found.
            - 403: If the user is not authorized to access the video.
            - 500: If both retrieval methods fail.
    """
    user_id = UUID(current_user.user_id)
    start_time = time.time()

    # Timing metrics
    embedding_ms = 0
    dense_ms = 0
    lexical_ms = 0
    fusion_ms = 0
    hydrate_ms = 0

    # Get user's preferred language for logging
    user_profile = db.get_user_profile(user_id)
    user_language = user_profile.preferred_language if user_profile else "ko"

    logger.info(
        f"Search request from user {user_id} (language: {user_language}): "
        f"query='{request.query}', video_id={request.video_id}, limit={request.limit}, "
        f"hybrid_enabled={settings.hybrid_search_enabled}"
    )

    # If video_id is provided, verify user has access to it
    if request.video_id:
        video = db.get_video(request.video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found",
            )
        if video.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this video",
            )

    # Generate embedding for query
    query_embedding = None
    embedding_failed = False
    try:
        embed_start = time.time()
        query_embedding = openai_client.create_embedding(request.query)
        embedding_ms = int((time.time() - embed_start) * 1000)
    except Exception as e:
        logger.error(f"Failed to create embedding: {e}")
        embedding_failed = True

    # Determine search strategy
    use_hybrid = (
        settings.hybrid_search_enabled
        and opensearch_client.is_available()
        and not embedding_failed
    )
    use_lexical_only = (
        embedding_failed
        and settings.hybrid_search_enabled
        and opensearch_client.is_available()
    )

    dense_candidates: list[Candidate] = []
    lexical_candidates: list[Candidate] = []
    fused_results: list[FusedCandidate] = []

    if use_hybrid:
        # Run both retrievals concurrently
        logger.debug("Running hybrid search (dense + lexical)")

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(
                    _run_dense_search,
                    query_embedding,
                    user_id,
                    request.video_id,
                    settings.candidate_k_dense,
                    request.threshold,
                ): "dense",
                executor.submit(
                    _run_lexical_search,
                    request.query,
                    user_id,
                    request.video_id,
                    settings.candidate_k_lexical,
                ): "lexical",
            }

            for future in as_completed(futures):
                search_type = futures[future]
                try:
                    if search_type == "dense":
                        dense_candidates, dense_ms = future.result()
                    else:
                        lexical_candidates, lexical_ms = future.result()
                except Exception as e:
                    logger.error(f"{search_type} search failed: {e}")

        # Fuse results
        fusion_start = time.time()
        if dense_candidates or lexical_candidates:
            fused_results = rrf_fuse(
                dense_candidates=dense_candidates,
                lexical_candidates=lexical_candidates,
                rrf_k=settings.rrf_k,
                top_k=request.limit,
            )
        fusion_ms = int((time.time() - fusion_start) * 1000)

    elif use_lexical_only:
        # Embedding failed but OpenSearch is available - use lexical only
        logger.warning("Embedding failed, falling back to lexical-only search")
        lexical_candidates, lexical_ms = _run_lexical_search(
            request.query,
            user_id,
            request.video_id,
            request.limit,
        )
        fused_results = lexical_only_fusion(lexical_candidates, request.limit)

    elif query_embedding is not None:
        # Dense-only mode (OpenSearch unavailable or hybrid disabled)
        logger.debug("Running dense-only search")
        dense_candidates, dense_ms = _run_dense_search(
            query_embedding,
            user_id,
            request.video_id,
            request.limit,
            request.threshold,
        )
        fused_results = dense_only_fusion(dense_candidates, request.limit)

    else:
        # Both embedding and OpenSearch failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process search query",
        )

    # Hydrate scenes
    scene_responses, hydrate_ms = _hydrate_scenes(fused_results)

    # Calculate total latency
    latency_ms = int((time.time() - start_time) * 1000)

    # Log search query
    try:
        db.log_search_query(
            user_id=user_id,
            query_text=request.query,
            results_count=len(scene_responses),
            latency_ms=latency_ms,
            video_id=request.video_id,
        )
    except Exception as e:
        logger.error(f"Failed to log search query: {e}")

    # Log timing breakdown
    search_mode = "hybrid" if use_hybrid else ("lexical" if use_lexical_only else "dense")
    logger.info(
        f"Search completed: mode={search_mode}, results={len(scene_responses)}, "
        f"latency={latency_ms}ms "
        f"(embed={embedding_ms}ms, dense={dense_ms}ms, lexical={lexical_ms}ms, "
        f"fusion={fusion_ms}ms, hydrate={hydrate_ms}ms), "
        f"dense_candidates={len(dense_candidates)}, lexical_candidates={len(lexical_candidates)}"
    )

    # Build response
    response = SearchResponse(
        query=request.query,
        results=scene_responses,
        total=len(scene_responses),
        latency_ms=latency_ms,
    )

    # Reset OpenSearch availability cache for next request
    opensearch_client.reset_availability_cache()

    return response
