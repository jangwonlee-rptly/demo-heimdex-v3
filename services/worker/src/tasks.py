"""Dramatiq tasks for video processing.

Phase 1 refactor: Removed import-time Redis broker initialization.
Broker is now initialized in bootstrap() to prevent import-time side effects.

The actual task actors are defined in libs/tasks/ and registered when the broker is set.
"""
import logging
from typing import Optional

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from redis import ConnectionPool, Redis

from .config import Settings
from .context import WorkerContext, create_worker_context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global worker context (set by bootstrap())
_worker_context: Optional[WorkerContext] = None


def bootstrap(settings: Optional[Settings] = None) -> WorkerContext:
    """Bootstrap the worker with all dependencies and Dramatiq broker.

    This function must be called before the worker starts processing tasks.
    It creates the WorkerContext and initializes the Dramatiq broker.

    Args:
        settings: Optional settings (will create new instance if not provided)

    Returns:
        WorkerContext with all initialized dependencies
    """
    global _worker_context

    if _worker_context is not None:
        logger.warning("Worker already bootstrapped, returning existing context")
        return _worker_context

    # Load settings
    if settings is None:
        settings = Settings()

    logger.info("Bootstrapping worker...")

    # Initialize Redis connection pool with resilience settings
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

    logger.info(f"Dramatiq Redis broker initialized: {settings.redis_url}")

    # Import the canonical actors from shared tasks module
    # This registers the actors with the broker we just set
    from libs.tasks import (  # noqa: F401
        process_video,
        export_scene_as_short,
        process_highlight_export,
        process_reference_photo,
    )

    logger.info(
        "Imported actors: process_video, export_scene_as_short, "
        "process_highlight_export, process_reference_photo"
    )

    # Create worker context
    _worker_context = create_worker_context(settings)

    logger.info("Worker bootstrapped successfully")

    return _worker_context


def get_worker_context() -> WorkerContext:
    """Get the global worker context.

    This should only be called from within task handlers after bootstrap() has been called.

    Returns:
        WorkerContext instance

    Raises:
        RuntimeError: If bootstrap() hasn't been called yet
    """
    if _worker_context is None:
        raise RuntimeError(
            "Worker context not initialized. Call bootstrap() before processing tasks."
        )
    return _worker_context


# NOTE: Bootstrap is NOT called automatically at import time to maintain import safety.
# The Dramatiq worker process MUST call bootstrap() before starting to process tasks.
# This can be done via the worker's __main__.py or by using the -p/--processes flag
# which ensures bootstrap runs in each worker process.
#
# For testing: Tests should call bootstrap() explicitly when needed, or mock the context.
#
# To run the worker:
#   python -m dramatiq src.tasks --processes 1 --threads 1
#   OR
#   python -m src.__main__  # Uses the __main__.py entrypoint which calls bootstrap()
