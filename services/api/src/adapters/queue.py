"""Queue adapter for Dramatiq task publishing.

This module initializes the Dramatiq broker and provides a clean interface
for enqueueing video processing tasks using the shared actor definition.
"""
import logging
from uuid import UUID

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from ..config import settings

logger = logging.getLogger(__name__)

# Initialize Redis broker
redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)

# Import the canonical process_video actor from shared tasks module
# The API service only uses .send() - the function body never executes here
from libs.tasks import process_video


class TaskQueue:
    """Task queue for background job processing."""

    @staticmethod
    def enqueue_video_processing(video_id: UUID) -> None:
        """
        Enqueue a video processing task.

        Uses the shared process_video actor to send a job to the worker.

        Args:
            video_id: ID of the video to process

        Returns:
            None: This function does not return a value.
        """
        logger.info(f"Enqueueing video processing task for video_id={video_id}")

        # Use the shared actor's .send() method to enqueue the job
        # The function body never executes in the API context - only in the worker
        process_video.send(str(video_id))

        logger.info(f"Successfully enqueued video_id={video_id}")


# Global task queue instance
task_queue = TaskQueue()
