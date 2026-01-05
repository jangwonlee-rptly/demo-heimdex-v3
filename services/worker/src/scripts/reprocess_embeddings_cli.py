#!/usr/bin/env python3
"""
CLI tool for triggering embedding reprocessing.

This script allows manual execution of the embedding reprocessing pipeline
via docker or direct python invocation.

Usage:
    # Reprocess a single video
    python -m src.scripts.reprocess_embeddings_cli --scope video --video-id <uuid>

    # Reprocess all videos for an owner
    python -m src.scripts.reprocess_embeddings_cli --scope owner --owner-id <uuid>

    # Reprocess all videos (admin only)
    python -m src.scripts.reprocess_embeddings_cli --scope all

    # Force regeneration even if embeddings exist
    python -m src.scripts.reprocess_embeddings_cli --scope all --force

Docker usage:
    docker-compose run worker python -m src.scripts.reprocess_embeddings_cli --scope all
"""

import argparse
import logging
import sys
from datetime import datetime
from uuid import UUID

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Reprocess embeddings using the latest embedding methods",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reprocess a single video
  python -m src.scripts.reprocess_embeddings_cli --scope video --video-id a1b2c3d4-...

  # Reprocess all videos for an owner
  python -m src.scripts.reprocess_embeddings_cli --scope owner --owner-id a1b2c3d4-...

  # Reprocess all videos in the system
  python -m src.scripts.reprocess_embeddings_cli --scope all

  # Force regeneration (overwrite existing embeddings)
  python -m src.scripts.reprocess_embeddings_cli --scope all --force

  # Run via docker
  docker-compose run worker python -m src.scripts.reprocess_embeddings_cli --scope all
        """,
    )

    parser.add_argument(
        "--scope",
        type=str,
        required=True,
        choices=["video", "owner", "all"],
        help="Reprocessing scope: 'video', 'owner', or 'all'",
    )
    parser.add_argument(
        "--video-id",
        type=str,
        help="Video UUID (required for scope='video')",
    )
    parser.add_argument(
        "--owner-id",
        type=str,
        help="Owner UUID (required for scope='owner')",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration even if embeddings already exist",
    )
    parser.add_argument(
        "--since",
        type=str,
        help="ISO datetime string - only reprocess videos updated after this date",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.scope == "video" and not args.video_id:
        parser.error("--video-id is required when scope='video'")
    if args.scope == "owner" and not args.owner_id:
        parser.error("--owner-id is required when scope='owner'")

    # Convert UUIDs
    video_uuid = UUID(args.video_id) if args.video_id else None
    owner_uuid = UUID(args.owner_id) if args.owner_id else None
    since_dt = datetime.fromisoformat(args.since) if args.since else None

    logger.info("=" * 80)
    logger.info("EMBEDDING REPROCESSING CLI")
    logger.info("=" * 80)

    # Bootstrap worker context
    logger.info("Bootstrapping worker context...")
    from src.config import Settings
    from src.tasks import bootstrap

    settings = Settings()
    bootstrap(settings)

    # Import after bootstrap to avoid import-time side effects
    from src.domain.reprocess import (
        ReprocessRunner,
        ReprocessRequest,
        ReprocessScope,
        LATEST_EMBEDDING_SPEC_VERSION,
    )
    from src.tasks import get_worker_context

    logger.info(f"Using embedding spec version: {LATEST_EMBEDDING_SPEC_VERSION}")
    logger.info(f"Scope: {args.scope}")
    if video_uuid:
        logger.info(f"Video ID: {video_uuid}")
    if owner_uuid:
        logger.info(f"Owner ID: {owner_uuid}")
    logger.info(f"Force regeneration: {args.force}")
    logger.info("=" * 80)

    # Get worker context
    ctx = get_worker_context()

    # Create reprocess runner
    runner = ReprocessRunner(
        db=ctx.db,
        storage=ctx.storage,
        opensearch=ctx.opensearch,
        openai=ctx.openai,
        clip_embedder=ctx.clip_embedder,
        ffmpeg=ctx.ffmpeg,
        settings=ctx.settings,
    )

    # Create request
    request = ReprocessRequest(
        scope=ReprocessScope(args.scope),
        video_id=video_uuid,
        owner_id=owner_uuid,
        force=args.force,
        since=since_dt,
        spec_version=LATEST_EMBEDDING_SPEC_VERSION,
    )

    # Execute reprocessing
    try:
        logger.info("Starting reprocessing...")
        progress = runner.run_reprocess(request)

        logger.info("=" * 80)
        logger.info("REPROCESSING COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Videos processed: {progress.videos_processed}/{progress.videos_total}")
        logger.info(f"Videos skipped: {progress.videos_skipped}")
        logger.info(f"Videos failed: {progress.videos_failed}")
        logger.info(f"Scenes processed: {progress.scenes_processed}/{progress.scenes_total}")
        logger.info(f"Scenes skipped: {progress.scenes_skipped}")
        logger.info(f"Scenes failed: {progress.scenes_failed}")
        logger.info(f"Person photos processed: {progress.person_photos_processed}/{progress.person_photos_total}")
        logger.info(f"Persons processed: {progress.persons_processed}/{progress.persons_total}")
        logger.info(f"Total errors: {len(progress.errors)}")
        logger.info("=" * 80)

        if progress.errors:
            logger.warning("Errors encountered during reprocessing:")
            for error in progress.errors[:10]:  # Show first 10 errors
                logger.warning(f"  - {error}")
            if len(progress.errors) > 10:
                logger.warning(f"  ... and {len(progress.errors) - 10} more errors")

        # Exit code based on results
        if progress.videos_failed > 0 or len(progress.errors) > 0:
            logger.warning("Reprocessing completed with errors")
            sys.exit(1)
        else:
            logger.info("Reprocessing completed successfully!")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error during reprocessing: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
