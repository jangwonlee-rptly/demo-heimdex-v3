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

# Initialize Redis broker with connection resilience
redis_broker = RedisBroker(
    url=settings.redis_url,
    # Connection pool settings for resilience
    connection_pool_kwargs={
        "max_connections": 10,
        "socket_keepalive": True,
        "socket_keepalive_options": {
            1: 1,  # TCP_KEEPIDLE: Start keepalives after 1 second
            2: 1,  # TCP_KEEPINTVL: Interval between keepalives
            3: 3,  # TCP_KEEPCNT: Number of keepalives before death
        },
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "retry_on_timeout": True,
        "health_check_interval": 30,  # Check connection health every 30s
    }
)
dramatiq.set_broker(redis_broker)

# Import the canonical actors from shared tasks module
# This registers the actors with the broker initialized above
from libs.tasks import process_video, export_scene_as_short  # noqa: F401

logger.info("Worker initialized with process_video and export_scene_as_short actors from libs.tasks")
