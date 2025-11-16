"""Queue adapter for Dramatiq task publishing."""
import logging
from uuid import UUID
import dramatiq
from dramatiq.brokers.redis import RedisBroker

from ..config import settings

logger = logging.getLogger(__name__)

# Initialize Redis broker
redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)


class TaskQueue:
    """Task queue for background job processing."""

    @staticmethod
    def enqueue_video_processing(video_id: UUID) -> None:
        """
        Enqueue a video processing task.

        Args:
            video_id: ID of the video to process
        """
        logger.info(f"Enqueueing video processing task for video_id={video_id}")

        # Import the actor here to avoid circular imports
        # The actual actor is defined in the worker service
        # We just need to declare it here for sending messages
        process_video = dramatiq.actor(
            lambda video_id: None,
            actor_name="process_video",
            queue_name="video_processing"  # Must match worker queue
        )
        process_video.send(str(video_id))


# Global task queue instance
task_queue = TaskQueue()
