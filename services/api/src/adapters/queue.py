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

# Import the canonical actors from shared tasks module
# The API service only uses .send() - the function body never executes here
from libs.tasks import process_video, export_scene_as_short


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

    @staticmethod
    def enqueue_scene_export(scene_id: UUID, export_id: UUID) -> None:
        """
        Enqueue a scene export task.

        Uses the shared export_scene_as_short actor to send a job to the worker.

        Args:
            scene_id: ID of the scene to export
            export_id: ID of the export record

        Returns:
            None: This function does not return a value.
        """
        logger.info(f"Enqueueing scene export task for scene_id={scene_id}, export_id={export_id}")

        # Use the shared actor's .send() method to enqueue the job
        # The function body never executes in the API context - only in the worker
        export_scene_as_short.send(str(scene_id), str(export_id))

        logger.info(f"Successfully enqueued export_id={export_id}")


# Global task queue instance
task_queue = TaskQueue()
