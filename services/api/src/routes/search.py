"""Scene search endpoint with hybrid retrieval (dense + lexical + configurable fusion)."""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user, User
from ..dependencies import get_db, get_openai, get_opensearch, get_clip, get_settings
from ..adapters.database import Database
from ..adapters.openai_client import OpenAIClient
from ..adapters.opensearch_client import OpenSearchClient
from ..adapters.clip_client import ClipClient, ClipClientError
from ..config import Settings
from ..domain.schemas import SearchRequest, SearchResponse, VideoSceneResponse
from ..domain.search.fusion import (
    fuse,
    dense_only_fusion,
    lexical_only_fusion,
    multi_channel_minmax_fuse,
    multi_channel_rrf_fuse,
    Candidate,
    FusedCandidate,
    ScoreType,
)
from ..domain.search.rerank import rerank_with_clip
from ..domain.search.intent import detect_query_intent
from ..domain.visual_router import get_visual_intent_router

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_fusion_weights(weight_dense: float, weight_lexical: float) -> None:
    """Validate that fusion weights sum to approximately 1.0.

    Args:
        weight_dense: Weight for dense scores.
        weight_lexical: Weight for lexical scores.

    Raises:
        HTTPException: If weights don't sum to ~1.0 (tolerance 0.01).
    """
    if abs(weight_dense + weight_lexical - 1.0) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fusion weights must sum to 1.0, got dense={weight_dense}, "
                   f"lexical={weight_lexical}, sum={weight_dense + weight_lexical}"
        )


def _run_dense_search(
    query_embedding: list[float],
    user_id: UUID,
    video_id: Optional[UUID],
    limit: int,
    threshold: float,
    db: Database,
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
    opensearch_client: OpenSearchClient,
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


def _run_multi_dense_search(
    query_embedding: list[float],
    user_id: UUID,
    video_id: Optional[UUID],
    query: str,
    db: Database,
    opensearch_client: OpenSearchClient,
    settings: Settings,
    query_embedding_clip: Optional[list[float]] = None,
    allowlist_scene_ids: Optional[set[str]] = None,
) -> tuple[dict[str, list[Candidate]], dict[str, int]]:
    """Run multi-channel dense + lexical search in parallel with timeouts.

    Uses ThreadPoolExecutor to run all retrieval tasks concurrently.
    Each task has an individual timeout (settings.multi_dense_timeout_s).
    If a channel times out or fails, it's treated as empty (graceful degradation).

    Args:
        query_embedding: OpenAI text query embedding (1536d).
        user_id: User ID for tenant scoping.
        video_id: Optional video ID filter.
        query: Original query text for BM25.
        query_embedding_clip: Optional CLIP text query embedding (512d) for visual channel.
        allowlist_scene_ids: Optional set of scene IDs to filter results (for lookup soft gating).
                            If provided, only candidates with scene_id in this set are kept.

    Returns:
        tuple: (channel_candidates dict, timing_ms dict)
               channel_candidates: {"transcript": [...], "visual": [...], "summary": [...], "lexical": [...]}
               timing_ms: {"transcript": 123, "visual": 456, ...}
    """
    channel_candidates: dict[str, list[Candidate]] = {}
    timing_ms: dict[str, int] = {}

    # Define retrieval tasks
    def run_transcript():
        start = time.time()
        results = db.search_scenes_transcript_embedding(
            query_embedding=query_embedding,
            user_id=user_id,
            video_id=video_id,
            match_count=settings.candidate_k_transcript,
            threshold=settings.threshold_transcript,
        )
        elapsed = int((time.time() - start) * 1000)
        candidates = [Candidate(scene_id=sid, rank=rank, score=score) for sid, rank, score in results]
        return ("transcript", candidates, elapsed)

    def run_visual():
        # Use CLIP embedding if available, otherwise skip visual channel
        if query_embedding_clip is None:
            logger.debug("Visual channel skipped: no CLIP embedding")
            return ("visual", [], 0)

        start = time.time()
        results = db.search_scenes_visual_clip_embedding(
            query_embedding=query_embedding_clip,  # Use CLIP embedding (512d)
            user_id=user_id,
            video_id=video_id,
            match_count=settings.candidate_k_visual,
            threshold=settings.threshold_visual,
        )
        elapsed = int((time.time() - start) * 1000)
        candidates = [Candidate(scene_id=sid, rank=rank, score=score) for sid, rank, score in results]
        return ("visual", candidates, elapsed)

    def run_summary():
        start = time.time()
        results = db.search_scenes_summary_embedding(
            query_embedding=query_embedding,
            user_id=user_id,
            video_id=video_id,
            match_count=settings.candidate_k_summary,
            threshold=settings.threshold_summary,
        )
        elapsed = int((time.time() - start) * 1000)
        candidates = [Candidate(scene_id=sid, rank=rank, score=score) for sid, rank, score in results]
        return ("summary", candidates, elapsed)

    def run_lexical():
        start = time.time()
        results = opensearch_client.bm25_search(
            query=query,
            owner_id=str(user_id),
            video_id=str(video_id) if video_id else None,
            size=settings.candidate_k_lexical,
        )
        elapsed = int((time.time() - start) * 1000)
        candidates = [Candidate(scene_id=r["scene_id"], rank=r["rank"], score=r["score"]) for r in results]
        return ("lexical", candidates, elapsed)

    # Determine active channels based on weights (skip zero-weight channels)
    is_valid, error_msg, active_weights = settings.validate_multi_dense_weights()
    if not is_valid:
        logger.error(f"Invalid multi-dense weights: {error_msg}")
        # Fall back to all channels (shouldn't happen in production)
        active_weights = {"transcript": 0.45, "visual": 0.25, "summary": 0.10, "lexical": 0.20}

    # Map channel names to retrieval functions
    retrieval_tasks = {}
    if "transcript" in active_weights:
        retrieval_tasks["transcript"] = run_transcript
    if "visual" in active_weights:
        retrieval_tasks["visual"] = run_visual
    if "summary" in active_weights:
        retrieval_tasks["summary"] = run_summary
    if "lexical" in active_weights:
        retrieval_tasks["lexical"] = run_lexical

    # Run all retrieval tasks in parallel with timeouts
    with ThreadPoolExecutor(max_workers=len(retrieval_tasks)) as executor:
        futures = {executor.submit(task_fn): ch_name for ch_name, task_fn in retrieval_tasks.items()}

        for future in as_completed(futures):
            channel_name = futures[future]
            try:
                ch_name, candidates, elapsed = future.result(timeout=settings.multi_dense_timeout_s)
                channel_candidates[ch_name] = candidates
                timing_ms[ch_name] = elapsed
            except TimeoutError:
                logger.warning(f"Multi-dense: {channel_name} channel timed out after {settings.multi_dense_timeout_s}s")
                channel_candidates[channel_name] = []
                timing_ms[channel_name] = int(settings.multi_dense_timeout_s * 1000)
            except Exception as e:
                logger.error(f"Multi-dense: {channel_name} channel failed: {e}")
                channel_candidates[channel_name] = []
                timing_ms[channel_name] = 0

    # Apply allowlist filtering if provided (for lookup soft gating)
    if allowlist_scene_ids:
        filtered_count_before = sum(len(cands) for cands in channel_candidates.values())
        for channel_name, candidates in channel_candidates.items():
            # Filter to only candidates in allowlist
            filtered_candidates = [c for c in candidates if c.scene_id in allowlist_scene_ids]
            channel_candidates[channel_name] = filtered_candidates
        filtered_count_after = sum(len(cands) for cands in channel_candidates.values())
        logger.info(
            f"Lookup soft gating: Allowlist filtering applied - "
            f"{filtered_count_before} -> {filtered_count_after} candidates "
            f"(allowlist size={len(allowlist_scene_ids)})"
        )

    return channel_candidates, timing_ms


def _hydrate_scenes(
    fused_results: list[FusedCandidate],
    db: Database,
    include_debug: bool = False,
    display_score_map: Optional[dict[str, float]] = None,
    match_quality: Optional[str] = None,
    allowlist_ids: Optional[set[str]] = None,
) -> tuple[list[VideoSceneResponse], int]:
    """Fetch full scene data for fused results.

    Args:
        fused_results: List of fused candidates from fusion.
        include_debug: If True, include debug fields (raw/norm scores, ranks).
        display_score_map: Optional mapping of scene_id -> calibrated display_score.
                           If provided, adds display_score to each result.
        match_quality: Optional match quality label for all results (e.g., 'supported', 'best_guess').
                      Used for lookup soft gating to indicate result reliability.
        allowlist_ids: Optional set of allowlisted scene IDs. If provided and match_quality is None,
                      scenes in the allowlist get 'supported', others get None.

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

    # Fetch video filenames for all scenes (batch query)
    video_ids = list(set(scene.video_id for scene in scenes))
    filename_map = db.get_video_filenames_by_ids(video_ids)

    # Build lookup for fused results
    fused_by_id = {r.scene_id: r for r in fused_results}

    # Convert to response objects
    responses = []
    for scene in scenes:
        fused = fused_by_id.get(str(scene.id))
        if not fused:
            continue

        # Build response with score information
        response_data = {
            "id": scene.id,
            "video_id": scene.video_id,
            "video_filename": filename_map.get(str(scene.video_id)),
            "index": scene.index,
            "start_s": scene.start_s,
            "end_s": scene.end_s,
            "transcript_segment": scene.transcript_segment,
            "visual_summary": scene.visual_summary,
            "combined_text": scene.combined_text,
            "thumbnail_url": scene.thumbnail_url,
            "visual_description": scene.visual_description,
            "visual_entities": scene.visual_entities,
            "visual_actions": scene.visual_actions,
            "tags": scene.tags,
            "created_at": scene.created_at,
            # New score fields
            "score": fused.score,
            "score_type": fused.score_type.value,
            # Legacy field for backward compatibility
            "similarity": fused.score,
            # Display score (calibrated for UI, if enabled)
            "display_score": display_score_map.get(str(scene.id)) if display_score_map else None,
            # Match quality (for lookup soft gating)
            "match_quality": (
                match_quality if match_quality
                else ("supported" if allowlist_ids and str(scene.id) in allowlist_ids else None)
            ),
        }

        # Add debug fields if enabled
        if include_debug:
            # Check if this is multi-dense result (has channel_scores)
            if fused.channel_scores:
                # Multi-dense mode: include channel_scores
                response_data.update({
                    "channel_scores": fused.channel_scores,
                })
            else:
                # Legacy 2-signal mode: include dense/lexical debug fields
                response_data.update({
                    "dense_score_raw": fused.dense_score_raw,
                    "lexical_score_raw": fused.lexical_score_raw,
                    "dense_score_norm": fused.dense_score_norm,
                    "lexical_score_norm": fused.lexical_score_norm,
                    "dense_rank": fused.dense_rank,
                    "lexical_rank": fused.lexical_rank,
                })

        responses.append(VideoSceneResponse(**response_data))

    elapsed_ms = int((time.time() - start) * 1000)
    return responses, elapsed_ms


@router.post("/search", response_model=SearchResponse)
async def search_scenes(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    openai_client: OpenAIClient = Depends(get_openai),
    opensearch_client: OpenSearchClient = Depends(get_opensearch),
    clip_client: Optional[ClipClient] = Depends(get_clip),
    settings: Settings = Depends(get_settings),
):
    """
    Search for video scenes using natural language.

    Uses hybrid search combining:
    - Dense vector search (pgvector) for semantic similarity
    - BM25 lexical search (OpenSearch) for keyword matching
    - Configurable fusion method (Min-Max Mean or RRF) to combine results

    Fusion Methods:
    - minmax_mean (default): Normalizes scores to [0,1] and combines with weighted mean
    - rrf: Reciprocal Rank Fusion using rank positions, more stable with outliers

    Falls back to dense-only or lexical-only if one system fails.

    Args:
        request: Search request parameters including query text, filters, limits,
                 and optional fusion overrides (fusion_method, weight_dense, weight_lexical).
        current_user: The authenticated user (injected).

    Returns:
        SearchResponse: Search results including matching scenes, total count, latency,
                        and fusion metadata (method, weights used).

    Raises:
        HTTPException:
            - 400: If fusion weights don't sum to 1.0.
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

    # Determine fusion configuration (request overrides server defaults)
    fusion_method = request.fusion_method or settings.fusion_method
    weight_dense = request.weight_dense if request.weight_dense is not None else settings.fusion_weight_dense
    weight_lexical = request.weight_lexical if request.weight_lexical is not None else settings.fusion_weight_lexical

    # Validate weights if both are provided in request
    if request.weight_dense is not None or request.weight_lexical is not None:
        _validate_fusion_weights(weight_dense, weight_lexical)

    # Get user's preferred language for logging
    user_profile = db.get_user_profile(user_id)
    user_language = user_profile.preferred_language if user_profile else "ko"

    # Detect query intent for soft lexical gating (lookup vs semantic)
    query_intent = detect_query_intent(request.query, language=user_language)

    logger.info(
        f"Search request from user {user_id} (language: {user_language}): "
        f"query='{request.query}', video_id={request.video_id}, limit={request.limit}, "
        f"intent={query_intent}, "
        f"hybrid_enabled={settings.hybrid_search_enabled}, "
        f"fusion_method={fusion_method}, weights=({weight_dense:.2f}/{weight_lexical:.2f})"
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

    # Generate embeddings for query
    query_embedding = None  # OpenAI embedding (1536d) for transcript/summary
    query_embedding_clip = None  # CLIP embedding (512d) for visual
    clip_embedding_ms = 0
    embedding_failed = False

    # OpenAI embedding (always needed for transcript/summary)
    try:
        embed_start = time.time()
        query_embedding = openai_client.create_embedding(request.query)
        embedding_ms = int((time.time() - embed_start) * 1000)
    except Exception as e:
        logger.error(f"Failed to create OpenAI embedding: {e}")
        embedding_failed = True

    # Determine visual mode (recall/rerank/auto/skip)
    visual_mode = settings.visual_mode
    visual_intent_result = None
    clip_enabled = (clip_client is not None) and settings.weight_visual > 0

    if visual_mode == "auto" and clip_enabled:
        # Use visual intent router to decide
        router = get_visual_intent_router()
        visual_intent_result = router.analyze(request.query)
        visual_mode = visual_intent_result.suggested_mode

        logger.info(
            f"Visual intent router: mode={visual_mode}, "
            f"confidence={visual_intent_result.confidence:.2f}, "
            f"reason={visual_intent_result.explanation}"
        )

    # Generate CLIP text embedding if needed
    if clip_enabled and visual_mode in ("recall", "rerank"):
        try:
            clip_start = time.time()
            query_embedding_clip = clip_client.create_text_embedding(
                request.query,
                normalize=True,
            )
            clip_embedding_ms = int((time.time() - clip_start) * 1000)

            logger.info(
                f"CLIP text embedding generated: dim={len(query_embedding_clip)}, "
                f"elapsed_ms={clip_embedding_ms}"
            )
        except ClipClientError as e:
            logger.warning(f"CLIP text embedding failed: {e}, visual mode disabled")
            query_embedding_clip = None
            visual_mode = "skip"  # Degrade gracefully
        except Exception as e:
            logger.error(f"Unexpected CLIP error: {e}", exc_info=True)
            query_embedding_clip = None
            visual_mode = "skip"

    # Determine search strategy
    use_multi_dense = (
        settings.multi_dense_enabled
        and not embedding_failed
    )
    use_hybrid = (
        settings.hybrid_search_enabled
        and opensearch_client.is_available()
        and not embedding_failed
        and not use_multi_dense  # Multi-dense takes precedence
    )
    use_lexical_only = (
        embedding_failed
        and settings.hybrid_search_enabled
        and opensearch_client.is_available()
    )

    dense_candidates: list[Candidate] = []
    lexical_candidates: list[Candidate] = []
    fused_results: list[FusedCandidate] = []
    actual_score_type: ScoreType = ScoreType.MINMAX_MEAN  # Will be updated based on path taken
    multi_dense_timings: dict[str, int] = {}

    # Soft lexical gating for lookup queries
    lookup_allowlist_ids: set[str] = set()  # Scene IDs from lexical hits (for allowlisting)
    lookup_used_allowlist: bool = False     # Whether we used allowlist filtering
    lookup_fallback_used: bool = False      # Whether we fell back to dense best guess
    lexical_hits_count: int = 0             # Number of lexical hits found
    match_quality: Optional[str] = None     # Match quality label for response

    # If soft gating enabled AND query is lookup intent, run lexical first to check hits
    if (
        settings.enable_lookup_soft_gating
        and query_intent == "lookup"
        and opensearch_client.is_available()
    ):
        logger.info(f"Lookup soft gating: Running early lexical check for query intent={query_intent}")

        try:
            lexical_start = time.time()
            lexical_results = opensearch_client.bm25_search(
                query=request.query,
                user_id=user_id,
                video_id=request.video_id,
                limit=settings.candidate_k_lexical,
            )
            lexical_check_ms = int((time.time() - lexical_start) * 1000)
            lexical_hits_count = len(lexical_results)

            logger.info(
                f"Lookup soft gating: Lexical check found {lexical_hits_count} hits "
                f"(threshold={settings.lookup_lexical_min_hits}, elapsed_ms={lexical_check_ms})"
            )

            # If we have enough lexical hits, use allowlist mode
            if lexical_hits_count >= settings.lookup_lexical_min_hits:
                lookup_allowlist_ids = {str(sid) for sid, _, _ in lexical_results}
                lookup_used_allowlist = True
                match_quality = "supported"
                logger.info(
                    f"Lookup soft gating: ALLOWLIST MODE - Filtering dense channels to "
                    f"{len(lookup_allowlist_ids)} lexically-supported scene IDs"
                )
            else:
                # Fallback to dense best guess
                lookup_fallback_used = True
                match_quality = "best_guess"
                logger.info(
                    f"Lookup soft gating: FALLBACK MODE - No lexical hits, proceeding with "
                    f"dense retrieval (results will be labeled as best_guess)"
                )

        except Exception as e:
            logger.warning(f"Lookup soft gating: Lexical check failed, proceeding normally: {e}")
            # On error, proceed normally (no gating)
            pass

    if use_multi_dense:
        # Multi-dense mode: run N dense channels + lexical in parallel
        logger.debug("Running multi-dense search (transcript + visual + summary + lexical)")

        # Resolve weights with precedence: request > saved > defaults
        from ..domain.search.weights import resolve_weights, get_default_weights, map_to_user_keys

        # Get saved preferences if enabled
        saved_prefs_weights = None
        if request.use_saved_preferences:
            try:
                prefs_data = db.get_user_search_preferences(user_id)
                if prefs_data and prefs_data.get("weights"):
                    saved_prefs_weights = prefs_data["weights"]
            except Exception as e:
                logger.warning(f"Failed to load saved preferences: {e}")

        # Resolve final weights
        try:
            weight_resolution = resolve_weights(
                request_weights=request.channel_weights,
                saved_weights=saved_prefs_weights,
                default_weights=get_default_weights(settings),
                use_saved_preferences=request.use_saved_preferences,
                visual_mode=visual_mode,
                enable_guardrails=True,
            )

            # Log warnings
            for warning in weight_resolution.warnings:
                logger.warning(f"Weight resolution: {warning}")

            # Get fusion weights (internal fusion keys)
            active_weights_fusion = weight_resolution.weights_applied
            weight_source = weight_resolution.source

            logger.info(
                f"Weights resolved: source={weight_source}, "
                f"weights={map_to_user_keys(active_weights_fusion)}"
            )

        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid channel weights: {e}",
            )

        # Save weights if requested
        if request.save_weights and request.channel_weights:
            try:
                prefs_dict = {
                    "weights": weight_resolution.weights_resolved,
                    "fusion_method": fusion_method,
                    "visual_mode": visual_mode,
                    "version": 1,
                }
                db.save_user_search_preferences(user_id=user_id, preferences=prefs_dict)
                logger.info(f"Saved search preferences for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to save preferences: {e}")

        # Run parallel multi-channel retrieval
        # Pass CLIP embedding for visual channel (recall mode) or None (rerank mode)
        clip_for_retrieval = query_embedding_clip if visual_mode == "recall" else None

        channel_candidates, multi_dense_timings = _run_multi_dense_search(
            query_embedding,
            user_id,
            request.video_id,
            request.query,
            db,
            opensearch_client,
            settings,
            query_embedding_clip=clip_for_retrieval,
            allowlist_scene_ids=lookup_allowlist_ids if lookup_allowlist_ids else None,
        )

        # Check if we got any results at all
        total_results = sum(len(candidates) for candidates in channel_candidates.values())
        if total_results == 0:
            logger.warning("Multi-dense search returned no results from any channel")
        else:
            # Fuse using configured method
            fusion_start = time.time()

            # Use channel-specific naming for dense channels
            # Map internal channel names to fusion function keys
            # Only include channels that have non-zero weights
            fusion_channels = {}
            if "transcript" in channel_candidates and "dense_transcript" in active_weights_fusion:
                fusion_channels["dense_transcript"] = channel_candidates["transcript"]
            if "visual" in channel_candidates and "dense_visual" in active_weights_fusion:
                fusion_channels["dense_visual"] = channel_candidates["visual"]
            if "summary" in channel_candidates and "dense_summary" in active_weights_fusion:
                fusion_channels["dense_summary"] = channel_candidates["summary"]
            if "lexical" in channel_candidates and "lexical" in active_weights_fusion:
                fusion_channels["lexical"] = channel_candidates["lexical"]

            # Use resolved weights (active_weights_fusion already has fusion keys)
            fusion_weights = active_weights_fusion

            # Track fusion metadata for response
            fusion_metadata = None

            if fusion_method == "rrf":
                fused_results, fusion_metadata = multi_channel_rrf_fuse(
                    channel_candidates=fusion_channels,
                    k=settings.rrf_k,
                    top_k=request.limit,
                    include_debug=settings.search_debug,
                    return_metadata=True,
                )
                actual_score_type = ScoreType.MULTI_DENSE_RRF
            else:  # minmax_mean (default)
                fused_results, fusion_metadata = multi_channel_minmax_fuse(
                    channel_candidates=fusion_channels,
                    channel_weights=fusion_weights,
                    settings=settings,
                    eps=settings.fusion_minmax_eps,
                    top_k=request.limit,
                    include_debug=settings.search_debug,
                    return_metadata=True,
                )
                actual_score_type = ScoreType.MULTI_DENSE_MINMAX_MEAN

            fusion_ms = int((time.time() - fusion_start) * 1000)

            # CLIP Rerank mode: Apply CLIP visual reranking to fused results
            rerank_ms = 0
            if visual_mode == "rerank" and query_embedding_clip is not None and fused_results:
                rerank_start = time.time()

                # Get candidate pool for reranking
                candidate_pool = fused_results[:settings.rerank_candidate_pool_size]
                candidate_scene_ids = [c.scene_id for c in candidate_pool]

                logger.info(
                    f"CLIP rerank: Scoring {len(candidate_scene_ids)} candidates "
                    f"from top {settings.rerank_candidate_pool_size} results"
                )

                # Batch score candidates with CLIP
                clip_scores = db.batch_score_scenes_clip(
                    scene_ids=candidate_scene_ids,
                    query_embedding=query_embedding_clip,
                    user_id=user_id,
                )

                # Apply reranking
                rerank_result = rerank_with_clip(
                    base_candidates=candidate_pool,
                    clip_scores=clip_scores,
                    clip_weight=settings.rerank_clip_weight,
                    min_score_range=settings.rerank_min_score_range,
                    eps=settings.fusion_minmax_eps,
                )

                # Replace fused results with reranked results
                # Keep any results beyond the candidate pool unchanged
                fused_results = (
                    rerank_result.reranked_candidates
                    + fused_results[settings.rerank_candidate_pool_size:]
                )

                # Update score type
                if not rerank_result.clip_skipped:
                    actual_score_type = ScoreType.RERANK_CLIP

                rerank_ms = int((time.time() - rerank_start) * 1000)

                logger.info(
                    f"CLIP rerank complete: scored={rerank_result.candidates_scored}, "
                    f"skipped={rerank_result.clip_skipped}, "
                    f"reason={rerank_result.skip_reason}, "
                    f"clip_weight={rerank_result.clip_weight_used}, "
                    f"elapsed_ms={rerank_ms}"
                )
            else:
                rerank_ms = 0

    elif use_hybrid:
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
                    db,
                ): "dense",
                executor.submit(
                    _run_lexical_search,
                    request.query,
                    user_id,
                    request.video_id,
                    settings.candidate_k_lexical,
                    opensearch_client,
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

        # Fuse results using configured method
        fusion_start = time.time()
        if dense_candidates or lexical_candidates:
            fused_results = fuse(
                dense_candidates=dense_candidates,
                lexical_candidates=lexical_candidates,
                method=fusion_method,
                weight_dense=weight_dense,
                weight_lexical=weight_lexical,
                rrf_k=settings.rrf_k,
                eps=settings.fusion_minmax_eps,
                top_k=request.limit,
            )
            if fused_results:
                actual_score_type = fused_results[0].score_type
        fusion_ms = int((time.time() - fusion_start) * 1000)

    elif use_lexical_only:
        # Embedding failed but OpenSearch is available - use lexical only
        logger.warning("Embedding failed, falling back to lexical-only search")
        lexical_candidates, lexical_ms = _run_lexical_search(
            request.query,
            user_id,
            request.video_id,
            request.limit,
            opensearch_client,
        )
        fused_results = lexical_only_fusion(
            lexical_candidates,
            request.limit,
            normalize=(fusion_method == "minmax_mean"),  # Normalize if using minmax
            eps=settings.fusion_minmax_eps,
        )
        actual_score_type = ScoreType.LEXICAL_ONLY

    elif query_embedding is not None:
        # Dense-only mode (OpenSearch unavailable or hybrid disabled)
        logger.debug("Running dense-only search")
        dense_candidates, dense_ms = _run_dense_search(
            query_embedding,
            user_id,
            request.video_id,
            request.limit,
            request.threshold,
            db,
        )
        fused_results = dense_only_fusion(
            dense_candidates,
            request.limit,
            normalize=(fusion_method == "minmax_mean"),  # Normalize if using minmax
            eps=settings.fusion_minmax_eps,
        )
        actual_score_type = ScoreType.DENSE_ONLY

    else:
        # Both embedding and OpenSearch failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process search query",
        )

    # Apply display score calibration if enabled (post-fusion, pre-hydration)
    display_score_map: dict[str, float] = {}
    if settings.enable_display_score_calibration and fused_results:
        from ..domain.search.display_score import calibrate_display_scores

        # Extract fused scores in result order
        fused_scores = [r.score for r in fused_results]

        # Calibrate for display (preserves ranking order)
        display_scores = calibrate_display_scores(
            fused_scores,
            method=settings.display_score_method,
            max_cap=settings.display_score_max_cap,
            alpha=settings.display_score_alpha,
        )

        # Build scene_id -> display_score mapping
        display_score_map = {
            r.scene_id: display_scores[i]
            for i, r in enumerate(fused_results)
        }

        if settings.search_debug:
            logger.info(
                f"Display score calibration: method={settings.display_score_method}, "
                f"max_cap={settings.display_score_max_cap}, alpha={settings.display_score_alpha}, "
                f"range=[{min(display_scores):.4f}, {max(display_scores):.4f}]"
            )

    # Hydrate scenes with debug info if enabled
    scene_responses, hydrate_ms = _hydrate_scenes(
        fused_results,
        db,
        include_debug=settings.search_debug,
        display_score_map=display_score_map if display_score_map else None,
        match_quality=match_quality if match_quality else None,
        allowlist_ids=lookup_allowlist_ids if lookup_allowlist_ids else None,
    )

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
    if use_multi_dense:
        search_mode = "multi_dense"
        # Log per-channel timing and candidate counts
        channel_info = ", ".join(
            f"{ch}={multi_dense_timings.get(ch, 0)}ms"
            for ch in ["transcript", "visual", "summary", "lexical"]
            if ch in multi_dense_timings
        )

        # Build CLIP info string
        clip_info = ""
        if clip_embedding_ms > 0 or 'rerank_ms' in locals():
            clip_parts = []
            if clip_embedding_ms > 0:
                clip_parts.append(f"clip_embed={clip_embedding_ms}ms")
            if 'rerank_ms' in locals() and rerank_ms > 0:
                clip_parts.append(f"clip_rerank={rerank_ms}ms")
            if visual_mode:
                clip_parts.append(f"visual_mode={visual_mode}")
            clip_info = ", " + ", ".join(clip_parts) if clip_parts else ""

        logger.info(
            f"Search completed: mode={search_mode}, fusion={actual_score_type.value}, "
            f"results={len(scene_responses)}, latency={latency_ms}ms "
            f"(embed={embedding_ms}ms{clip_info}, channels=[{channel_info}], "
            f"fusion={fusion_ms}ms, hydrate={hydrate_ms}ms)"
        )
    else:
        search_mode = "hybrid" if use_hybrid else ("lexical" if use_lexical_only else "dense")
        logger.info(
            f"Search completed: mode={search_mode}, fusion={actual_score_type.value}, "
            f"results={len(scene_responses)}, latency={latency_ms}ms "
            f"(embed={embedding_ms}ms, dense={dense_ms}ms, lexical={lexical_ms}ms, "
            f"fusion={fusion_ms}ms, hydrate={hydrate_ms}ms), "
            f"dense_candidates={len(dense_candidates)}, lexical_candidates={len(lexical_candidates)}"
        )

    # Build fusion metadata for response
    fusion_weights_response = None
    weight_source_response = None
    channels_active_response = None
    channels_empty_response = None
    channel_score_ranges_response = None

    if actual_score_type == ScoreType.MINMAX_MEAN:
        fusion_weights_response = {"dense": weight_dense, "lexical": weight_lexical}
    elif actual_score_type in (ScoreType.MULTI_DENSE_MINMAX_MEAN, ScoreType.MULTI_DENSE_RRF):
        # Include multi-channel weights (convert to user keys)
        if 'weight_source' in locals() and 'active_weights_fusion' in locals():
            fusion_weights_response = map_to_user_keys(active_weights_fusion)
            weight_source_response = weight_source
        else:
            # Fallback to settings
            is_valid, _, active_weights = settings.validate_multi_dense_weights()
            if is_valid:
                fusion_weights_response = active_weights

        # Add fusion metadata if available
        if 'fusion_metadata' in locals() and fusion_metadata:
            # Map internal channel names to user-facing names (e.g., "dense_transcript" -> "transcript")
            channels_active_response = [
                list(map_to_user_keys({ch: 1}).keys())[0] if map_to_user_keys({ch: 1}) else ch.replace("dense_", "")
                for ch in fusion_metadata.active_channels
            ]
            channels_empty_response = [
                list(map_to_user_keys({ch: 1}).keys())[0] if map_to_user_keys({ch: 1}) else ch.replace("dense_", "")
                for ch in fusion_metadata.empty_channels
            ]
            if fusion_metadata.channel_score_ranges:
                channel_score_ranges_response = {
                    list(map_to_user_keys({ch: 1}).keys())[0] if map_to_user_keys({ch: 1}) else ch.replace("dense_", ""): ranges
                    for ch, ranges in fusion_metadata.channel_score_ranges.items()
                }

    # Build response
    response = SearchResponse(
        query=request.query,
        results=scene_responses,
        total=len(scene_responses),
        latency_ms=latency_ms,
        fusion_method=actual_score_type.value,
        fusion_weights=fusion_weights_response,
        weight_source=weight_source_response if settings.search_debug else None,
        weights_requested=weight_resolution.weights_requested if settings.search_debug and 'weight_resolution' in locals() else None,
        channels_active=channels_active_response if settings.search_debug else None,
        channels_empty=channels_empty_response if settings.search_debug else None,
        channel_score_ranges=channel_score_ranges_response if settings.search_debug else None,
        visual_mode_used=visual_mode if settings.search_debug else None,
    )

    # Log search with metadata
    search_metadata = None
    if use_multi_dense and 'fusion_metadata' in locals():
        search_metadata = {
            "fusion_method": actual_score_type.value,
            "weights": fusion_weights_response,
            "weight_source": weight_source_response if 'weight_source' in locals() else "default",
            "visual_mode": visual_mode,
            "channels_active": channels_active_response or [],
            "channels_empty": channels_empty_response or [],
            "timing": {
                "embedding_ms": embedding_ms,
                "clip_embedding_ms": clip_embedding_ms if clip_embedding_ms > 0 else 0,
                **multi_dense_timings,
                "fusion_ms": fusion_ms if 'fusion_ms' in locals() else 0,
                "rerank_ms": rerank_ms if 'rerank_ms' in locals() else 0,
            },
        }

    # Log search query
    db.log_search_query(
        user_id=user_id,
        query_text=request.query,
        results_count=len(scene_responses),
        latency_ms=latency_ms,
        video_id=request.video_id,
        search_metadata=search_metadata,
    )

    # Reset OpenSearch availability cache for next request
    opensearch_client.reset_availability_cache()

    # Structured logging for lookup soft gating metrics (for tuning)
    if settings.enable_lookup_soft_gating and query_intent == "lookup":
        # Get top scores for analysis
        top_scores = scene_responses[:3] if scene_responses else []
        top_display_scores = [s.display_score for s in top_scores if s.display_score is not None]
        top_raw_scores = [s.score for s in top_scores if s.score is not None]

        logger.info(
            f"Lookup soft gating metrics: "
            f"query='{request.query}', intent={query_intent}, "
            f"lexical_hits={lexical_hits_count}, "
            f"used_allowlist={lookup_used_allowlist}, "
            f"fallback_used={lookup_fallback_used}, "
            f"match_quality={match_quality}, "
            f"results_count={len(scene_responses)}, "
            f"top_raw_scores={top_raw_scores[:3]}, "
            f"top_display_scores={top_display_scores[:3]}"
        )

    return response
