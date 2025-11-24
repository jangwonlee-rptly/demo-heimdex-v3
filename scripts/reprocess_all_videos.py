#!/usr/bin/env python3
"""Bulk reprocess all videos to apply Visual Semantics v2.

This script queries all videos in the database that need reprocessing
(status=READY and has_rich_semantics=false) and enqueues them for
processing with the new Visual Semantics v2 feature.

Prerequisites:
1. Apply database migration: infra/migrations/009_add_rich_semantics.sql
2. Ensure worker service is running to process the jobs
3. Monitor Redis queue and worker logs

Usage:
    # Dry run (preview what will be reprocessed)
    python scripts/reprocess_all_videos.py --dry-run

    # Actually reprocess all videos
    python scripts/reprocess_all_videos.py

    # Reprocess specific user's videos only
    python scripts/reprocess_all_videos.py --owner-id <uuid>

    # Reprocess with delay between jobs (to avoid overwhelming workers)
    python scripts/reprocess_all_videos.py --delay 2.0
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path
from uuid import UUID

import dramatiq
from dotenv import load_dotenv
from dramatiq.brokers.redis import RedisBroker
from supabase import create_client, Client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
if not env_path.exists():
    logger.error(f"Environment file not found at {env_path}")
    sys.exit(1)

load_dotenv(env_path)

# Validate required environment variables
REQUIRED_ENV_VARS = [
    'SUPABASE_URL',
    'SUPABASE_SERVICE_ROLE_KEY',
    'REDIS_URL',
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    sys.exit(1)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')


def init_supabase() -> Client:
    """Initialize Supabase client with service role key."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def init_dramatiq() -> None:
    """Initialize Dramatiq broker for enqueueing jobs."""
    redis_broker = RedisBroker(url=REDIS_URL)
    dramatiq.set_broker(redis_broker)
    logger.info(f"Dramatiq broker initialized with Redis at {REDIS_URL}")


def get_videos_to_reprocess(
    supabase: Client,
    owner_id: str = None,
) -> list[dict]:
    """Query videos that need reprocessing.

    Args:
        supabase: Supabase client instance
        owner_id: Optional user UUID to filter by

    Returns:
        List of video records to reprocess
    """
    logger.info("Querying videos that need reprocessing...")

    query = (
        supabase.table("videos")
        .select("id,owner_id,filename,status,has_rich_semantics,created_at")
        .eq("status", "READY")
        .eq("has_rich_semantics", False)
    )

    if owner_id:
        query = query.eq("owner_id", owner_id)

    response = query.execute()

    if not response.data:
        logger.warning("No videos found that need reprocessing")
        return []

    logger.info(f"Found {len(response.data)} videos to reprocess")
    return response.data


def enqueue_video_processing(video_id: str) -> None:
    """Enqueue a video for processing.

    Args:
        video_id: UUID of the video to process (as string)
    """
    # Import the shared actor from libs.tasks
    # This must be imported AFTER dramatiq broker is initialized
    from libs.tasks import process_video

    # Use the actor's .send() method to enqueue the job
    process_video.send(video_id)
    logger.info(f"Enqueued video {video_id}")


def reprocess_videos(
    videos: list[dict],
    dry_run: bool = False,
    delay: float = 0.0,
) -> None:
    """Reprocess all videos in the list.

    Args:
        videos: List of video records to reprocess
        dry_run: If True, only preview what will be reprocessed
        delay: Delay in seconds between enqueueing jobs
    """
    if dry_run:
        logger.info("DRY RUN MODE - No videos will actually be reprocessed")
        logger.info(f"Would reprocess {len(videos)} videos:")
        for video in videos:
            logger.info(
                f"  - {video['filename']} (ID: {video['id'][:8]}..., "
                f"Owner: {video['owner_id'][:8]}..., Created: {video['created_at']})"
            )
        return

    logger.info(f"Starting to reprocess {len(videos)} videos...")

    success_count = 0
    error_count = 0

    for idx, video in enumerate(videos, start=1):
        video_id = video['id']
        filename = video.get('filename', 'Unknown')

        try:
            logger.info(
                f"[{idx}/{len(videos)}] Processing {filename} (ID: {video_id[:8]}...)"
            )

            enqueue_video_processing(video_id)
            success_count += 1

            # Add delay between jobs to avoid overwhelming workers
            if delay > 0 and idx < len(videos):
                time.sleep(delay)

        except Exception as e:
            logger.error(f"Failed to enqueue video {video_id}: {e}")
            error_count += 1

    logger.info("=" * 80)
    logger.info("Bulk reprocessing complete!")
    logger.info(f"Successfully enqueued: {success_count} videos")
    if error_count > 0:
        logger.warning(f"Failed to enqueue: {error_count} videos")
    logger.info("=" * 80)
    logger.info("Monitor worker logs to track processing progress:")
    logger.info("  docker-compose logs -f worker")


def main():
    """Main entry point for the reprocessing script."""
    parser = argparse.ArgumentParser(
        description="Bulk reprocess videos with Visual Semantics v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to preview what will be reprocessed
  python scripts/reprocess_all_videos.py --dry-run

  # Reprocess all videos
  python scripts/reprocess_all_videos.py

  # Reprocess with 2 second delay between jobs
  python scripts/reprocess_all_videos.py --delay 2.0

  # Reprocess only a specific user's videos
  python scripts/reprocess_all_videos.py --owner-id <uuid>
        """
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what will be reprocessed without actually enqueueing jobs'
    )
    parser.add_argument(
        '--owner-id',
        type=str,
        help='Only reprocess videos for a specific user (UUID)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.0,
        help='Delay in seconds between enqueueing jobs (default: 0.0)'
    )

    args = parser.parse_args()

    # Validate owner_id if provided
    if args.owner_id:
        try:
            UUID(args.owner_id)
        except ValueError:
            logger.error(f"Invalid UUID format for owner_id: {args.owner_id}")
            sys.exit(1)

    logger.info("=" * 80)
    logger.info("Heimdex Bulk Video Reprocessing Script")
    logger.info("Visual Semantics v2 - Tags + Summaries")
    logger.info("=" * 80)

    # Initialize clients
    supabase = init_supabase()
    init_dramatiq()

    # Get videos to reprocess
    videos = get_videos_to_reprocess(supabase, owner_id=args.owner_id)

    if not videos:
        logger.info("No videos to reprocess. Exiting.")
        return

    # Reprocess videos
    reprocess_videos(videos, dry_run=args.dry_run, delay=args.delay)


if __name__ == '__main__':
    main()
