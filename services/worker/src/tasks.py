"""Dramatiq tasks for video processing.

This module initializes the Dramatiq broker and imports the shared actor definition.
The actual process_video actor is defined in libs/tasks/video_processing.py.
"""
import logging

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from .config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize Redis broker
redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)

# Import the canonical actors from shared tasks module
# This registers the actors with the broker initialized above
from libs.tasks import process_video, export_scene_as_short  # noqa: F401

logger.info("Worker initialized with process_video and export_scene_as_short actors from libs.tasks")
