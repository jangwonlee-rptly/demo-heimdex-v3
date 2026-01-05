"""Queue adapter for Dramatiq task publishing.

This module provides a clean interface for enqueueing video processing tasks
using the shared actor definition.

Phase 1 refactor: Removed module-level Redis broker initialization.
Broker is now initialized in TaskQueue.__init__() to prevent import-time side effects.
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

import dramatiq
from dramatiq.brokers.redis import RedisBroker

logger = logging.getLogger(__name__)


class TaskQueue:
    """Task queue for background job processing.

    Manages Dramatiq broker initialization and provides methods for enqueueing
    background tasks without creating global state at import time.
    """

    def __init__(self, redis_url: str):
        """Initialize the task queue with Redis broker.

        Args:
            redis_url: Redis connection URL (e.g., "redis://redis:6379/0")
        """
        self._redis_url = redis_url
        self._broker: Optional[RedisBroker] = None
        self._initialized = False

    def _ensure_broker(self) -> None:
        """Lazily initialize Redis broker and import actors.

        This defers broker creation and actor import until first use,
        preventing import-time side effects.
        """
        if self._initialized:
            return

        # Create Redis broker
        self._broker = RedisBroker(url=self._redis_url)
        dramatiq.set_broker(self._broker)

        # Import the canonical actors from shared tasks module
        # The API service only uses .send() - the function body never executes here
        # Import inside method to avoid circular dependency and import-time actor registration
        from libs.tasks import (
            process_video,
            export_scene_as_short,
            process_highlight_export,
            process_reference_photo,
        )

        # Store actor references (actors are now registered with the broker)
        self._process_video = process_video
        self._export_scene_as_short = export_scene_as_short
        self._process_highlight_export = process_highlight_export
        self._process_reference_photo = process_reference_photo

        self._initialized = True
        logger.info(f"TaskQueue initialized with Redis broker: {self._redis_url}")

    def enqueue_video_processing(self, video_id: UUID, db = None) -> None:
        """
        Enqueue a video processing task.

        Uses the shared process_video actor to send a job to the worker.

        Phase 2: Sets queued_at timestamp for queue time tracking.

        Args:
            video_id: ID of the video to process
            db: Database adapter (optional, for setting queued_at timestamp)

        Returns:
            None: This function does not return a value.
        """
        self._ensure_broker()

        logger.info(f"Enqueueing video processing task for video_id={video_id}")

        # Phase 2: Set queued_at timestamp before enqueueing
        if db:
            queued_at = datetime.utcnow()
            try:
                db.update_video_queued_at(video_id, queued_at)
            except Exception as e:
                # Log but don't fail - timing is non-critical
                logger.warning(f"Failed to set queued_at for video {video_id}: {e}")

        # Use the shared actor's .send() method to enqueue the job
        # The function body never executes in the API context - only in the worker
        self._process_video.send(str(video_id))

        logger.info(f"Successfully enqueued video_id={video_id}")

    def enqueue_scene_export(self, scene_id: UUID, export_id: UUID) -> None:
        """
        Enqueue a scene export task.

        Uses the shared export_scene_as_short actor to send a job to the worker.

        Args:
            scene_id: ID of the scene to export
            export_id: ID of the export record

        Returns:
            None: This function does not return a value.
        """
        self._ensure_broker()

        logger.info(f"Enqueueing scene export task for scene_id={scene_id}, export_id={export_id}")

        # Use the shared actor's .send() method to enqueue the job
        # The function body never executes in the API context - only in the worker
        self._export_scene_as_short.send(str(scene_id), str(export_id))

        logger.info(f"Successfully enqueued export_id={export_id}")

    def enqueue_highlight_export(self, job_id: UUID) -> None:
        """
        Enqueue a highlight reel export task.

        Uses the shared process_highlight_export actor to send a job to the worker.

        Args:
            job_id: ID of the highlight export job

        Returns:
            None: This function does not return a value.
        """
        self._ensure_broker()

        logger.info(f"Enqueueing highlight export task for job_id={job_id}")

        # Use the shared actor's .send() method to enqueue the job
        # The function body never executes in the API context - only in the worker
        self._process_highlight_export.send(str(job_id))

        logger.info(f"Successfully enqueued highlight export job_id={job_id}")

    def enqueue_reference_photo_processing(self, photo_id: UUID) -> None:
        """
        Enqueue a reference photo processing task.

        Uses the shared process_reference_photo actor to send a job to the worker.

        Args:
            photo_id: ID of the person reference photo to process

        Returns:
            None: This function does not return a value.
        """
        self._ensure_broker()

        logger.info(f"Enqueueing reference photo processing task for photo_id={photo_id}")

        # Use the shared actor's .send() method to enqueue the job
        # The function body never executes in the API context - only in the worker
        self._process_reference_photo.send(str(photo_id))

        logger.info(f"Successfully enqueued photo_id={photo_id}")

    def close(self) -> None:
        """Close the Redis broker connection.

        Should be called at application shutdown.
        """
        if self._broker:
            try:
                self._broker.close()
                logger.info("Task queue Redis broker closed")
            except Exception as e:
                logger.warning(f"Error closing Redis broker: {e}")


# DEPRECATED: Global instance removed for Phase 1 refactor.
# Use dependency injection instead via get_queue() from dependencies.py
task_queue: TaskQueue = None  # type: ignore
