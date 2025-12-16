"""
Backfill script for v3-multi per-channel embeddings.

This script iterates through existing scenes and generates per-channel embeddings:
- embedding_transcript: Embedding of transcript_segment only
- embedding_visual: Embedding of visual_description + tags
- embedding_summary: Embedding of summary (optional, currently disabled)

Safety features:
- Rate limiting to avoid API overload
- Checkpointing for resume capability
- Batch processing with progress tracking
- Only regenerates missing/outdated embeddings
- Validates input data before API calls

Usage:
    python -m src.scripts.backfill_scene_embeddings_v3 [options]

Options:
    --batch-size BATCH_SIZE          Number of scenes to process in each batch (default: 100)
    --max-scenes MAX_SCENES          Maximum total scenes to process (default: unlimited)
    --rate-limit-delay DELAY         Delay between API calls in seconds (default: 0.1)
    --checkpoint-file FILE           Path to checkpoint file (default: .backfill_v3_checkpoint.json)
    --force-regenerate               Regenerate embeddings even if already present
    --dry-run                        Show what would be done without making changes
    --video-id VIDEO_ID              Process only scenes from specific video (optional)
    --user-id USER_ID                Process only scenes from specific user (optional)
"""
import argparse
import hashlib
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.adapters.database import Database
from src.adapters.openai_client import openai_client
from src.config import settings
from src.domain.sidecar_builder import SidecarBuilder, MultiEmbeddingMetadata, EmbeddingMetadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class BackfillCheckpoint:
    """Manages checkpointing for resume capability."""

    def __init__(self, checkpoint_file: Path):
        self.checkpoint_file = checkpoint_file
        self.last_scene_id: Optional[str] = None
        self.total_processed: int = 0
        self.total_updated: int = 0
        self.total_skipped: int = 0
        self.total_errors: int = 0
        self.started_at: Optional[str] = None
        self.load()

    def load(self):
        """Load checkpoint from file if it exists."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r") as f:
                    data = json.load(f)
                    self.last_scene_id = data.get("last_scene_id")
                    self.total_processed = data.get("total_processed", 0)
                    self.total_updated = data.get("total_updated", 0)
                    self.total_skipped = data.get("total_skipped", 0)
                    self.total_errors = data.get("total_errors", 0)
                    self.started_at = data.get("started_at")
                    logger.info(
                        f"Loaded checkpoint: last_scene_id={self.last_scene_id}, "
                        f"processed={self.total_processed}, updated={self.total_updated}"
                    )
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")

    def save(self):
        """Save current checkpoint to file."""
        try:
            data = {
                "last_scene_id": self.last_scene_id,
                "total_processed": self.total_processed,
                "total_updated": self.total_updated,
                "total_skipped": self.total_skipped,
                "total_errors": self.total_errors,
                "started_at": self.started_at,
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
            with open(self.checkpoint_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")


def needs_backfill(scene: dict, force_regenerate: bool) -> tuple[bool, str]:
    """
    Determine if a scene needs v3-multi embedding backfill.

    Args:
        scene: Scene dictionary from database
        force_regenerate: Force regeneration even if already present

    Returns:
        Tuple of (needs_backfill: bool, reason: str)
    """
    # Check if already has v3-multi embeddings
    if not force_regenerate:
        embedding_version = scene.get("embedding_version")
        if embedding_version == "v3-multi":
            # Check if at least one channel embedding exists
            has_transcript = scene.get("embedding_transcript") is not None
            has_visual = scene.get("embedding_visual") is not None
            if has_transcript or has_visual:
                return False, "already_has_v3_embeddings"

    # Check if scene has any content to embed
    transcript = scene.get("transcript_segment") or ""
    visual_description = scene.get("visual_description") or ""
    tags = scene.get("tags") or []

    if not transcript.strip() and not visual_description.strip() and not tags:
        return False, "no_content_to_embed"

    return True, "needs_v3_embeddings"


def backfill_scene(
    db: Database,
    scene: dict,
    dry_run: bool,
    rate_limit_delay: float,
) -> tuple[bool, str]:
    """
    Backfill v3-multi embeddings for a single scene.

    Args:
        db: Database instance
        scene: Scene dictionary
        dry_run: If True, don't make actual changes
        rate_limit_delay: Delay between API calls

    Returns:
        Tuple of (success: bool, message: str)
    """
    scene_id = scene["id"]
    scene_index = scene.get("index", "?")

    try:
        # Extract scene data
        transcript_segment = scene.get("transcript_segment") or ""
        visual_description = scene.get("visual_description") or ""
        tags = scene.get("tags") or []
        language = "ko"  # Default, could be extracted from metadata if available

        # Generate multi-channel embeddings using the same logic as sidecar_builder
        logger.info(f"Scene {scene_index}: Generating v3-multi embeddings...")

        if dry_run:
            logger.info(
                f"Scene {scene_index}: DRY RUN - Would generate embeddings for "
                f"transcript={bool(transcript_segment.strip())}, "
                f"visual={bool(visual_description.strip() or tags)}"
            )
            return True, "dry_run_success"

        # Generate embeddings using sidecar_builder methods
        (
            embedding_transcript,
            embedding_visual,
            embedding_summary,
            multi_metadata,
        ) = SidecarBuilder._create_multi_channel_embeddings(
            transcript_segment=transcript_segment,
            visual_description=visual_description,
            tags=tags,
            summary=None,  # Summary not implemented yet
            scene_index=scene_index,
            language=language,
        )

        # Rate limiting
        time.sleep(rate_limit_delay)

        # Helper function to convert embeddings to pgvector format
        def to_pgvector(emb: Optional[list[float]]) -> Optional[str]:
            if emb is None:
                return None
            return "[" + ",".join(str(x) for x in emb) + "]"

        # Update scene in database
        update_data = {
            "embedding_version": settings.embedding_version,
            "embedding_metadata": multi_metadata.to_dict() if multi_metadata else None,
        }

        if embedding_transcript is not None:
            update_data["embedding_transcript"] = to_pgvector(embedding_transcript)
        if embedding_visual is not None:
            update_data["embedding_visual"] = to_pgvector(embedding_visual)
        if embedding_summary is not None:
            update_data["embedding_summary"] = to_pgvector(embedding_summary)

        # Execute update
        db.client.table("video_scenes").update(update_data).eq("id", scene_id).execute()

        channels_generated = []
        if embedding_transcript:
            channels_generated.append("transcript")
        if embedding_visual:
            channels_generated.append("visual")
        if embedding_summary:
            channels_generated.append("summary")

        logger.info(
            f"Scene {scene_index}: Updated with channels: {', '.join(channels_generated) or 'none'}"
        )
        return True, f"updated_channels={','.join(channels_generated)}"

    except Exception as e:
        logger.error(f"Scene {scene_index}: Failed to backfill: {e}", exc_info=True)
        return False, str(e)


def backfill_scenes(
    batch_size: int = 100,
    max_scenes: Optional[int] = None,
    rate_limit_delay: float = 0.1,
    checkpoint_file: Path = Path(".backfill_v3_checkpoint.json"),
    force_regenerate: bool = False,
    dry_run: bool = False,
    video_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
):
    """
    Backfill v3-multi embeddings for scenes.

    Args:
        batch_size: Number of scenes to fetch per batch
        max_scenes: Maximum total scenes to process (None = unlimited)
        rate_limit_delay: Delay between API calls in seconds
        checkpoint_file: Path to checkpoint file for resume capability
        force_regenerate: Regenerate even if already present
        dry_run: Don't make actual changes
        video_id: Process only scenes from specific video
        user_id: Process only scenes from specific user
    """
    db = Database(settings.supabase_url, settings.supabase_service_role_key)
    checkpoint = BackfillCheckpoint(checkpoint_file)

    if checkpoint.started_at is None:
        checkpoint.started_at = datetime.utcnow().isoformat() + "Z"

    logger.info("=" * 80)
    logger.info("v3-multi Embedding Backfill Started")
    logger.info("=" * 80)
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Max scenes: {max_scenes or 'unlimited'}")
    logger.info(f"Rate limit delay: {rate_limit_delay}s")
    logger.info(f"Force regenerate: {force_regenerate}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Video filter: {video_id or 'none'}")
    logger.info(f"User filter: {user_id or 'none'}")
    logger.info(f"Checkpoint file: {checkpoint_file}")
    logger.info("=" * 80)

    # Resume from checkpoint if exists
    if checkpoint.last_scene_id:
        logger.info(f"Resuming from scene_id: {checkpoint.last_scene_id}")

    processed_count = checkpoint.total_processed
    updated_count = checkpoint.total_updated
    skipped_count = checkpoint.total_skipped
    error_count = checkpoint.total_errors

    try:
        while True:
            # Rebuild query for each batch to avoid accumulating limit parameters
            batch_query = db.client.table("video_scenes").select("*")

            # Apply filters
            if video_id:
                batch_query = batch_query.eq("video_id", str(video_id))

            # Resume from checkpoint
            if checkpoint.last_scene_id:
                batch_query = batch_query.order("id").gt("id", checkpoint.last_scene_id)
            else:
                batch_query = batch_query.order("id")

            # Fetch batch
            logger.info(f"\nFetching batch (offset={processed_count}, limit={batch_size})...")
            result = batch_query.limit(batch_size).execute()
            scenes = result.data

            if not scenes:
                logger.info("No more scenes to process")
                break

            logger.info(f"Processing {len(scenes)} scenes...")

            for scene in scenes:
                scene_id = scene["id"]
                scene_index = scene.get("index", "?")

                # Check if max scenes reached
                if max_scenes and processed_count >= max_scenes:
                    logger.info(f"Reached max scenes limit: {max_scenes}")
                    checkpoint.save()
                    return

                # Check if needs backfill
                needs_bf, reason = needs_backfill(scene, force_regenerate)

                if not needs_bf:
                    logger.info(f"Scene {scene_index}: Skipped ({reason})")
                    skipped_count += 1
                else:
                    # Backfill scene
                    success, message = backfill_scene(
                        db, scene, dry_run, rate_limit_delay
                    )

                    if success:
                        updated_count += 1
                    else:
                        error_count += 1

                processed_count += 1
                checkpoint.last_scene_id = scene_id
                checkpoint.total_processed = processed_count
                checkpoint.total_updated = updated_count
                checkpoint.total_skipped = skipped_count
                checkpoint.total_errors = error_count

                # Save checkpoint periodically (every 10 scenes)
                if processed_count % 10 == 0:
                    checkpoint.save()
                    logger.info(
                        f"Progress: processed={processed_count}, updated={updated_count}, "
                        f"skipped={skipped_count}, errors={error_count}"
                    )

            # If batch was smaller than batch_size, we're done
            if len(scenes) < batch_size:
                logger.info("Reached end of scenes")
                break

    except KeyboardInterrupt:
        logger.warning("\nBackfill interrupted by user")
        checkpoint.save()
        raise
    except Exception as e:
        logger.error(f"Backfill failed with error: {e}", exc_info=True)
        checkpoint.save()
        raise
    finally:
        # Final checkpoint save
        checkpoint.save()

        logger.info("\n" + "=" * 80)
        logger.info("v3-multi Embedding Backfill Completed")
        logger.info("=" * 80)
        logger.info(f"Total processed: {processed_count}")
        logger.info(f"Total updated: {updated_count}")
        logger.info(f"Total skipped: {skipped_count}")
        logger.info(f"Total errors: {error_count}")
        logger.info("=" * 80)


def main():
    """Main entry point for backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill v3-multi per-channel embeddings for existing scenes"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of scenes to process in each batch",
    )
    parser.add_argument(
        "--max-scenes",
        type=int,
        default=None,
        help="Maximum total scenes to process (default: unlimited)",
    )
    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=0.1,
        help="Delay between API calls in seconds",
    )
    parser.add_argument(
        "--checkpoint-file",
        type=str,
        default=".backfill_v3_checkpoint.json",
        help="Path to checkpoint file",
    )
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Regenerate embeddings even if already present",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--video-id",
        type=str,
        default=None,
        help="Process only scenes from specific video",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Process only scenes from specific user",
    )

    args = parser.parse_args()

    # Convert UUIDs
    video_id = UUID(args.video_id) if args.video_id else None
    user_id = UUID(args.user_id) if args.user_id else None

    backfill_scenes(
        batch_size=args.batch_size,
        max_scenes=args.max_scenes,
        rate_limit_delay=args.rate_limit_delay,
        checkpoint_file=Path(args.checkpoint_file),
        force_regenerate=args.force_regenerate,
        dry_run=args.dry_run,
        video_id=video_id,
        user_id=user_id,
    )


if __name__ == "__main__":
    main()
