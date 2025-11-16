"""Dramatiq tasks for video processing."""
import logging
from uuid import UUID
import dramatiq
from dramatiq.brokers.redis import RedisBroker

from .config import settings
from .domain.video_processor import video_processor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize Redis broker
redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)


@dramatiq.actor(
    max_retries=3,
    min_backoff=15000,  # 15 seconds
    max_backoff=300000,  # 5 minutes
    time_limit=3600000,  # 1 hour timeout
    queue_name="video_processing",
)
def process_video(video_id: str) -> None:
    """
    Process a video through the complete pipeline.

    This is the main Dramatiq actor for video processing.

    Args:
        video_id: UUID of the video to process (as string)
    """
    logger.info(f"Received process_video task for video_id={video_id}")

    try:
        video_uuid = UUID(video_id)
        video_processor.process_video(video_uuid)
        logger.info(f"Successfully processed video_id={video_id}")
    except Exception as e:
        logger.error(f"Failed to process video_id={video_id}: {e}", exc_info=True)
        raise
