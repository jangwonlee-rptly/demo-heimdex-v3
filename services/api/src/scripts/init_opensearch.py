#!/usr/bin/env python3
"""Initialize OpenSearch index for hybrid search.

This script creates the scene_docs index with proper mapping.
It's idempotent - safe to run multiple times.

Usage:
    # From API container or with proper environment:
    python -m src.scripts.init_opensearch

    # Or directly if dependencies are installed:
    python services/api/src/scripts/init_opensearch.py
"""
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Initialize OpenSearch index.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    # Import here to ensure settings are loaded
    from ..adapters.opensearch_client import opensearch_client
    from ..config import settings

    logger.info(f"Connecting to OpenSearch at {settings.opensearch_url}")
    logger.info(f"Index name: {settings.opensearch_index_scenes}")

    # Wait for OpenSearch to be ready (useful during container startup)
    max_retries = 30
    retry_delay = 2

    for attempt in range(max_retries):
        if opensearch_client.ping():
            logger.info("OpenSearch is available")
            break
        logger.warning(f"OpenSearch not ready, retrying in {retry_delay}s... ({attempt + 1}/{max_retries})")
        time.sleep(retry_delay)
    else:
        logger.error("OpenSearch not available after max retries")
        return 1

    # Create/ensure index exists
    if opensearch_client.ensure_index():
        logger.info("Index initialization complete")

        # Get and display index stats
        stats = opensearch_client.get_index_stats()
        if stats:
            logger.info(f"Index stats: {stats['doc_count']} documents, {stats['size_bytes']} bytes")

        return 0
    else:
        logger.error("Failed to initialize index")
        return 1


if __name__ == "__main__":
    sys.exit(main())
