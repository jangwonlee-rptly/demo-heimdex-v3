"""Video processing Dramatiq actor.

This module defines the canonical process_video actor that is shared between
the API service (for sending jobs) and the Worker service (for processing jobs).

Architecture:
- API service: Imports this actor and calls process_video.send(video_id)
- Worker service: Imports this actor; when executed, it delegates to the domain layer
"""
import logging
from uuid import UUID

import dramatiq

logger = logging.getLogger(__name__)


@dramatiq.actor(
    queue_name="video_processing",
    max_retries=3,
    min_backoff=15000,  # 15 seconds
    max_backoff=300000,  # 5 minutes
    time_limit=3600000,  # 1 hour timeout
)
def process_video(video_id: str) -> None:
    """
    Process a video through the complete pipeline.

    This actor is executed by the worker service. The API service only calls
    .send() to enqueue jobs - the function body never executes in the API context.

    Args:
        video_id: UUID of the video to process (as string)

    Raises:
        ImportError: If worker dependencies are not available (shouldn't happen in worker)
        Exception: If video processing fails
    """
    logger.info(f"Received process_video task for video_id={video_id}")

    try:
        # Lazy import to avoid requiring worker dependencies in API service
        # When API calls .send(), this function body never executes
        # When Worker executes the job, this imports and runs successfully
        from src.domain.video_processor import video_processor

        video_uuid = UUID(video_id)
        video_processor.process_video(video_uuid)
        logger.info(f"Successfully processed video_id={video_id}")

    except ImportError as e:
        logger.error(
            f"Worker dependencies not available: {e}. "
            "This actor can only execute in the worker service."
        )
        raise RuntimeError(
            "This actor must be executed by the worker service. "
            "The API service should only use .send() to enqueue jobs."
        ) from e

    except Exception as e:
        logger.error(f"Failed to process video_id={video_id}: {e}", exc_info=True)
        raise
