#!/usr/bin/env python3
"""
Backfill script for Phase 2 video timing fields.

This script backfills processing_finished_at from updated_at for existing videos
that were processed before Phase 2 timing instrumentation was added.

IMPORTANT: This only backfills completion timestamps. It does NOT fabricate
processing_started_at or processing_duration_ms, as those would be incorrect.

Usage:
    # Direct Python (from services/api directory)
    python3 -m src.scripts.backfill_video_timing [--dry-run]

    # Docker Compose (from project root)
    docker-compose exec api python3 -m src.scripts.backfill_video_timing [--dry-run]

    # Docker run (from project root)
    ./run-backfill.sh [--dry-run]

Options:
    --dry-run    Show what would be updated without making changes
"""

import argparse
import logging
import sys
import os

# Set up Python path for imports
# This works both in Docker and local environments
if os.path.exists('/app/src'):
    # Running in Docker
    sys.path.insert(0, '/app')
else:
    # Running locally
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.adapters.database import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_video_timing(dry_run: bool = False) -> dict:
    """
    Backfill processing_finished_at from updated_at for existing videos.

    Args:
        dry_run: If True, only count videos that would be updated.

    Returns:
        dict: Statistics about the backfill operation.
    """
    logger.info("=" * 60)
    logger.info("Phase 2 Video Timing Backfill Script")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info("")

    # Count videos that need backfill
    logger.info("Querying videos that need backfilling...")

    response = db.client.table("videos").select(
        "id, status, updated_at, processing_finished_at"
    ).in_(
        "status", ["READY", "FAILED"]
    ).is_(
        "processing_finished_at", "null"
    ).execute()

    videos_to_backfill = response.data

    if not videos_to_backfill:
        logger.info("✅ No videos need backfilling. All done!")
        return {
            "total_videos": 0,
            "updated": 0,
            "dry_run": dry_run
        }

    logger.info(f"Found {len(videos_to_backfill)} videos to backfill:")
    logger.info(f"  - Videos with status READY or FAILED")
    logger.info(f"  - Missing processing_finished_at timestamp")
    logger.info("")

    # Show breakdown by status
    ready_count = sum(1 for v in videos_to_backfill if v["status"] == "READY")
    failed_count = sum(1 for v in videos_to_backfill if v["status"] == "FAILED")
    logger.info(f"Breakdown:")
    logger.info(f"  - READY: {ready_count} videos")
    logger.info(f"  - FAILED: {failed_count} videos")
    logger.info("")

    if dry_run:
        logger.info("DRY RUN: Would backfill processing_finished_at from updated_at")
        logger.info("DRY RUN: Would NOT backfill processing_started_at or processing_duration_ms")
        logger.info("         (those require precise measurement and cannot be fabricated)")
        logger.info("")
        logger.info("To execute the backfill, run without --dry-run flag")
        return {
            "total_videos": len(videos_to_backfill),
            "updated": 0,
            "dry_run": True
        }

    # Execute backfill
    logger.info("Executing backfill...")
    logger.info("This will set processing_finished_at = updated_at for these videos")
    logger.info("")

    # Perform bulk update using SQL
    # We use raw SQL here because Supabase PostgREST doesn't support UPDATE ... FROM easily
    sql = """
    UPDATE videos
    SET processing_finished_at = updated_at
    WHERE processing_finished_at IS NULL
      AND status IN ('READY', 'FAILED')
    RETURNING id;
    """

    try:
        # Use the RPC mechanism to execute raw SQL
        # Note: This requires a helper RPC function in the database
        # For now, we'll do it via client.table().update() with individual updates

        updated_count = 0
        for video in videos_to_backfill:
            try:
                db.client.table("videos").update({
                    "processing_finished_at": video["updated_at"]
                }).eq("id", video["id"]).execute()
                updated_count += 1

                if updated_count % 100 == 0:
                    logger.info(f"  Progress: {updated_count}/{len(videos_to_backfill)} videos updated...")
            except Exception as e:
                logger.error(f"  Failed to update video {video['id']}: {e}")

        logger.info("")
        logger.info(f"✅ Backfill complete! Updated {updated_count} videos")
        logger.info("")
        logger.info("What was backfilled:")
        logger.info("  ✅ processing_finished_at = updated_at")
        logger.info("")
        logger.info("What was NOT backfilled (intentionally):")
        logger.info("  ❌ processing_started_at (remains NULL - no precise data)")
        logger.info("  ❌ processing_duration_ms (remains NULL - no precise data)")
        logger.info("  ❌ queued_at (remains NULL - no precise data)")
        logger.info("")
        logger.info("Impact on Phase 2 metrics:")
        logger.info("  - Throughput time series will now include historical data")
        logger.info("  - Latency percentiles will only use newly processed videos (correct)")
        logger.info("  - RTF calculations will only use newly processed videos (correct)")
        logger.info("  - Queue analysis will only use newly processed videos (correct)")
        logger.info("")
        logger.info("Going forward, all new videos will have precise timing from worker instrumentation.")

        return {
            "total_videos": len(videos_to_backfill),
            "updated": updated_count,
            "dry_run": False
        }

    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}", exc_info=True)
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill Phase 2 video timing fields",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes"
    )

    args = parser.parse_args()

    try:
        stats = backfill_video_timing(dry_run=args.dry_run)
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Total videos: {stats['total_videos']}")
        logger.info(f"  Updated: {stats['updated']}")
        logger.info(f"  Dry run: {stats['dry_run']}")
        logger.info("=" * 60)
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
