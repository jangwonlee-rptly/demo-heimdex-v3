"""Worker entrypoint.

This module bootstraps the worker context and starts Dramatiq.
It should be invoked via: python -m src

This ensures bootstrap() is called before Dramatiq starts processing tasks.
"""
import logging
import sys

from .tasks import bootstrap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Bootstrapping worker context...")
    bootstrap()
    logger.info("Worker context initialized successfully")

    # Start Dramatiq worker
    logger.info("Starting Dramatiq worker...")
    from dramatiq.cli import main as dramatiq_main

    # Pass Dramatiq CLI arguments: module name and worker settings
    sys.argv = ["dramatiq", "src.tasks", "-p", "1", "-t", "1"]
    dramatiq_main()
