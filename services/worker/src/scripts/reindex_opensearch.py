#!/usr/bin/env python3
"""Reindex all scenes from Supabase to OpenSearch.

This script backfills OpenSearch with existing scene data from Supabase.
Use this when:
- Setting up hybrid search for the first time
- After changing the OpenSearch index mapping
- To recover from data inconsistencies

Usage:
    # From worker container or with proper environment:
    python -m src.scripts.reindex_opensearch

    # With options:
    python -m src.scripts.reindex_opensearch --batch-size 100 --sleep 0.5

    # Dry run (no actual indexing):
    python -m src.scripts.reindex_opensearch --dry-run
"""
import argparse
import logging
import sys
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Reindex scenes from Supabase to OpenSearch"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of scenes to process per batch (default: 100)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to sleep between batches to respect rate limits (default: 0.2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually index, just show what would be done",
    )
    parser.add_argument(
        "--video-id",
        type=str,
        help="Only reindex scenes for a specific video ID",
    )
    return parser.parse_args()


def main() -> int:
    """Reindex all scenes to OpenSearch.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    args = parse_args()

    # Import here to ensure settings are loaded
    from ..adapters.database import db
    from ..adapters.opensearch_client import opensearch_client
    from ..config import settings

    logger.info("Starting OpenSearch reindex")
    logger.info(f"OpenSearch URL: {settings.opensearch_url}")
    logger.info(f"Index name: {settings.opensearch_index_scenes}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Sleep between batches: {args.sleep}s")
    logger.info(f"Dry run: {args.dry_run}")

    if args.dry_run:
        logger.info("DRY RUN MODE - No actual indexing will occur")

    # Ensure OpenSearch is available and index exists
    if not args.dry_run:
        if not opensearch_client.ping():
            logger.error("OpenSearch is not available")
            return 1

        if not opensearch_client.ensure_index():
            logger.error("Failed to ensure OpenSearch index exists")
            return 1

    # Get all scenes with their video owner info
    offset = 0
    total_indexed = 0
    total_errors = 0
    start_time = datetime.now()

    # Build query base
    query = db.client.table("video_scenes").select(
        "id, video_id, index, start_s, end_s, transcript_segment, "
        "visual_summary, visual_description, combined_text, tags, thumbnail_url, created_at, "
        "videos!inner(owner_id)"
    ).order("created_at")

    if args.video_id:
        logger.info(f"Filtering to video_id: {args.video_id}")
        query = query.eq("video_id", args.video_id)

    while True:
        # Fetch batch of scenes with video owner info (using join)
        try:
            response = (
                db.client.table("video_scenes")
                .select(
                    "id, video_id, index, start_s, end_s, transcript_segment, "
                    "visual_summary, visual_description, combined_text, tags, thumbnail_url, created_at, "
                    "videos!inner(owner_id)"
                )
                .order("created_at")
                .range(offset, offset + args.batch_size - 1)
                .execute()
            )

            if args.video_id:
                # Re-query with filter if specified
                response = (
                    db.client.table("video_scenes")
                    .select(
                        "id, video_id, index, start_s, end_s, transcript_segment, "
                        "visual_summary, visual_description, combined_text, tags, thumbnail_url, created_at, "
                        "videos!inner(owner_id)"
                    )
                    .eq("video_id", args.video_id)
                    .order("created_at")
                    .range(offset, offset + args.batch_size - 1)
                    .execute()
                )

        except Exception as e:
            logger.error(f"Failed to fetch scenes at offset {offset}: {e}")
            return 1

        scenes = response.data
        if not scenes:
            logger.info("No more scenes to process")
            break

        logger.info(f"Processing batch of {len(scenes)} scenes (offset {offset})")

        # Prepare documents for bulk indexing
        docs = []
        for scene in scenes:
            # Extract owner_id from joined video data
            owner_id = scene.get("videos", {}).get("owner_id")
            if not owner_id:
                logger.warning(f"Scene {scene['id']} has no owner_id, skipping")
                total_errors += 1
                continue

            doc = {
                "scene_id": scene["id"],
                "video_id": scene["video_id"],
                "owner_id": owner_id,
                "index": scene["index"],
                "start_s": scene["start_s"],
                "end_s": scene["end_s"],
                "transcript_segment": scene.get("transcript_segment") or "",
                "visual_summary": scene.get("visual_summary") or "",
                "visual_description": scene.get("visual_description") or "",
                "combined_text": scene.get("combined_text") or "",
                "tags": scene.get("tags") or [],
                "tags_text": " ".join(scene.get("tags") or []),
                "thumbnail_url": scene.get("thumbnail_url"),
                "created_at": scene.get("created_at"),
            }
            docs.append(doc)

        if docs and not args.dry_run:
            success, errors = opensearch_client.bulk_upsert(docs)
            total_indexed += success
            total_errors += errors

            if errors > 0:
                logger.warning(f"Batch had {errors} indexing errors")

        elif args.dry_run:
            logger.info(f"Would index {len(docs)} documents")
            total_indexed += len(docs)

        offset += args.batch_size

        # Sleep to respect rate limits
        if args.sleep > 0:
            time.sleep(args.sleep)

    # Report results
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 50)
    logger.info("Reindex complete!")
    logger.info(f"Total indexed: {total_indexed}")
    logger.info(f"Total errors: {total_errors}")
    logger.info(f"Elapsed time: {elapsed:.1f}s")

    if total_indexed > 0:
        logger.info(f"Rate: {total_indexed / elapsed:.1f} docs/sec")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
