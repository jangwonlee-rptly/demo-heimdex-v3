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

# Initialize Redis connection pool with resilience settings
from redis import ConnectionPool, Redis

redis_pool = ConnectionPool.from_url(
    settings.redis_url,
    max_connections=10,
    socket_keepalive=True,
    # Remove socket_keepalive_options to avoid EINVAL on Railway
    # Railway's internal networking handles keepalive automatically
    socket_connect_timeout=10,  # Increased timeout for Railway's network
    socket_timeout=10,  # Increased timeout for Railway's network
    retry_on_timeout=True,
    health_check_interval=30,  # Check connection health every 30s
)

# Create Redis client with the resilient pool
redis_client = Redis(connection_pool=redis_pool)

# Initialize Redis broker with the configured client
redis_broker = RedisBroker(client=redis_client)
dramatiq.set_broker(redis_broker)

# Import the canonical actors from shared tasks module
# This registers the actors with the broker initialized above
from libs.tasks import process_video, export_scene_as_short, process_highlight_export  # noqa: F401

logger.info("Worker initialized with process_video, export_scene_as_short, and process_highlight_export actors from libs.tasks")
