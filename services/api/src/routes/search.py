"""Scene search endpoint."""
import logging
import time
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user, User
from ..domain.schemas import SearchRequest, SearchResponse, VideoSceneResponse
from ..adapters.database import db
from ..adapters.openai_client import openai_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_scenes(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Search for video scenes using natural language.

    The search is performed using semantic similarity between the query
    and scene embeddings. Results are ordered by relevance.

    Args:
        request: Search request parameters including query text, filters, and limits.
        current_user: The authenticated user (injected).

    Returns:
        SearchResponse: Search results including matching scenes, total count, and latency.

    Raises:
        HTTPException:
            - 404: If the specified video is not found.
            - 403: If the user is not authorized to access the video.
            - 500: If embedding generation fails.
    """
    user_id = UUID(current_user.user_id)
    start_time = time.time()

    # Get user's preferred language for logging
    user_profile = db.get_user_profile(user_id)
    user_language = user_profile.preferred_language if user_profile else "ko"

    logger.info(
        f"Search request from user {user_id} (language: {user_language}): "
        f"query='{request.query}', video_id={request.video_id}, limit={request.limit}, "
        f"weights=(asr={request.asr_weight:.2f}, image={request.image_weight:.2f}, metadata={request.metadata_weight:.2f})"
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
    try:
        query_embedding = openai_client.create_embedding(request.query)
    except Exception as e:
        logger.error(f"Failed to create embedding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process search query",
        )

    # Search for similar scenes using weighted search
    scenes = db.search_scenes_weighted(
        query_embedding=query_embedding,
        limit=request.limit,
        threshold=request.threshold,
        video_id=request.video_id,
        user_id=user_id,
        asr_weight=request.asr_weight,
        image_weight=request.image_weight,
        metadata_weight=request.metadata_weight,
    )

    # Calculate latency
    latency_ms = int((time.time() - start_time) * 1000)

    # Log search query
    try:
        db.log_search_query(
            user_id=user_id,
            query_text=request.query,
            results_count=len(scenes),
            latency_ms=latency_ms,
            video_id=request.video_id,
        )
    except Exception as e:
        logger.error(f"Failed to log search query: {e}")
        # Don't fail the request if logging fails

    logger.info(
        f"Search completed: found {len(scenes)} results in {latency_ms}ms"
    )

    return SearchResponse(
        query=request.query,
        results=[
            VideoSceneResponse(
                id=scene.id,
                video_id=scene.video_id,
                index=scene.index,
                start_s=scene.start_s,
                end_s=scene.end_s,
                transcript_segment=scene.transcript_segment,
                visual_summary=scene.visual_summary,
                combined_text=scene.combined_text,
                thumbnail_url=scene.thumbnail_url,
                similarity=scene.similarity,
                created_at=scene.created_at,
            )
            for scene in scenes
        ],
        total=len(scenes),
        latency_ms=latency_ms,
    )
