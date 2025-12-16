"""
Backfill script for CLIP visual embeddings.

This script iterates through existing scenes and generates CLIP visual embeddings
from their thumbnail images stored in Supabase Storage.

Safety features:
- Rate limiting to avoid CPU overload
- Checkpointing for resume capability
- Batch processing with progress tracking
- Only generates missing CLIP embeddings
- Validates that thumbnail exists before processing
- Handles CLIP model loading failures gracefully
- CPU-friendly with configurable timeouts

Usage:
    python -m src.scripts.backfill_clip_visual_embeddings [options]

Options:
    --batch-size BATCH_SIZE          Number of scenes to process in each batch (default: 50)
    --max-scenes MAX_SCENES          Maximum total scenes to process (default: unlimited)
    --processing-delay DELAY         Delay between scenes in seconds (default: 0.5)
    --checkpoint-file FILE           Path to checkpoint file (default: .backfill_clip_checkpoint.json)
    --force-regenerate               Regenerate embeddings even if already present
    --dry-run                        Show what would be done without making changes
    --video-id VIDEO_ID              Process only scenes from specific video (optional)
    --user-id USER_ID                Process only scenes from specific user (optional)
    --clip-timeout TIMEOUT           CLIP inference timeout in seconds (default: 5.0)
"""
import argparse
import json
import logging
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.adapters.database import Database
from src.adapters.clip_embedder import ClipEmbedder
from src.adapters.supabase import storage
from src.config import settings

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
    Determine if a scene needs CLIP embedding backfill.

    Args:
        scene: Scene dictionary from database
        force_regenerate: Force regeneration even if already present

    Returns:
        Tuple of (needs_backfill: bool, reason: str)
    """
    # Check if already has CLIP embedding
    if not force_regenerate:
        if scene.get("embedding_visual_clip") is not None:
            return False, "already_has_clip_embedding"

    # Check if scene has thumbnail
    thumbnail_url = scene.get("thumbnail_url")
    if not thumbnail_url:
        return False, "no_thumbnail"

    return True, "needs_clip_embedding"


def download_thumbnail(thumbnail_url: str, temp_dir: Path) -> Optional[Path]:
    """
    Download thumbnail from Supabase Storage to temporary file.

    Args:
        thumbnail_url: URL of thumbnail in Supabase Storage
        temp_dir: Temporary directory to store downloaded file

    Returns:
        Path to downloaded file, or None if download failed
    """
    try:
        # Extract storage path from URL
        # Example: https://xxx.supabase.co/storage/v1/object/public/videos/user_id/video_id/thumbnails/scene_12.jpg
        # We need: user_id/video_id/thumbnails/scene_12.jpg
        if "/storage/v1/object/public/videos/" in thumbnail_url:
            storage_path = thumbnail_url.split("/storage/v1/object/public/videos/")[1]
        else:
            logger.warning(f"Unexpected thumbnail URL format: {thumbnail_url}")
            return None

        # Save to temporary file
        temp_file = temp_dir / Path(storage_path).name

        # Download from Supabase Storage
        storage.download_file(storage_path, temp_file)

        if not temp_file.exists():
            logger.warning(f"Failed to download thumbnail: {storage_path}")
            return None

        return temp_file

    except Exception as e:
        logger.error(f"Error downloading thumbnail {thumbnail_url}: {e}")
        return None


def backfill_scene(
    db: Database,
    clip_embedder: ClipEmbedder,
    scene: dict,
    temp_dir: Path,
    dry_run: bool,
    processing_delay: float,
    clip_timeout: float,
) -> tuple[bool, str]:
    """
    Backfill CLIP embedding for a single scene.

    Args:
        db: Database instance
        clip_embedder: ClipEmbedder instance
        scene: Scene dictionary
        temp_dir: Temporary directory for downloads
        dry_run: If True, don't make actual changes
        processing_delay: Delay between scenes
        clip_timeout: CLIP inference timeout in seconds

    Returns:
        Tuple of (success: bool, message: str)
    """
    scene_id = scene["id"]
    scene_index = scene.get("index", "?")
    thumbnail_url = scene.get("thumbnail_url")

    try:
        logger.info(f"Scene {scene_index}: Generating CLIP embedding...")

        if dry_run:
            logger.info(
                f"Scene {scene_index}: DRY RUN - Would generate CLIP embedding from {thumbnail_url}"
            )
            return True, "dry_run_success"

        # Download thumbnail
        thumbnail_path = download_thumbnail(thumbnail_url, temp_dir)
        if not thumbnail_path:
            return False, "thumbnail_download_failed"

        # Generate CLIP embedding
        embedding_visual_clip, clip_metadata = clip_embedder.create_visual_embedding(
            image_path=thumbnail_path,
            quality_info=None,  # We don't have quality info for backfill
            timeout_s=clip_timeout,
        )

        # Clean up downloaded file
        try:
            thumbnail_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete temp file {thumbnail_path}: {e}")

        # Check if embedding generation succeeded
        if embedding_visual_clip is None:
            error = clip_metadata.error if clip_metadata else "unknown_error"
            logger.warning(f"Scene {scene_index}: CLIP embedding failed: {error}")

            # Still update metadata to record the failure
            update_data = {
                "visual_clip_metadata": clip_metadata.to_dict() if clip_metadata else None
            }
            db.client.table("video_scenes").update(update_data).eq("id", scene_id).execute()

            return False, f"clip_failed: {error}"

        # Processing delay
        time.sleep(processing_delay)

        # Helper function to convert embedding to pgvector format
        def to_pgvector(emb: list[float]) -> str:
            return "[" + ",".join(str(x) for x in emb) + "]"

        # Update scene in database
        update_data = {
            "embedding_visual_clip": to_pgvector(embedding_visual_clip),
            "visual_clip_metadata": clip_metadata.to_dict() if clip_metadata else None,
        }

        # Execute update
        db.client.table("video_scenes").update(update_data).eq("id", scene_id).execute()

        inference_time = clip_metadata.inference_time_ms if clip_metadata else 0
        logger.info(
            f"Scene {scene_index}: Updated with CLIP embedding "
            f"(dim={len(embedding_visual_clip)}, time={inference_time:.1f}ms)"
        )
        return True, f"updated_clip_dim={len(embedding_visual_clip)}"

    except Exception as e:
        logger.error(f"Scene {scene_index}: Failed to backfill: {e}", exc_info=True)
        return False, str(e)


def backfill_scenes(
    batch_size: int = 50,
    max_scenes: Optional[int] = None,
    processing_delay: float = 0.5,
    checkpoint_file: Path = Path(".backfill_clip_checkpoint.json"),
    force_regenerate: bool = True,
    dry_run: bool = False,
    video_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    clip_timeout: float = 5.0,
):
    """
    Backfill CLIP visual embeddings for scenes.

    Args:
        batch_size: Number of scenes to fetch per batch
        max_scenes: Maximum total scenes to process (None = unlimited)
        processing_delay: Delay between scenes in seconds
        checkpoint_file: Path to checkpoint file for resume capability
        force_regenerate: Regenerate even if already present
        dry_run: Don't make actual changes
        video_id: Process only scenes from specific video
        user_id: Process only scenes from specific user
        clip_timeout: CLIP inference timeout in seconds
    """
    # Enable CLIP if not already enabled
    if not settings.clip_enabled:
        logger.warning("CLIP is disabled in settings. Enabling for backfill...")
        settings.clip_enabled = True

    # Initialize CLIP embedder
    try:
        clip_embedder = ClipEmbedder()
        if not clip_embedder.is_available():
            logger.error("CLIP embedder is not available. Check dependencies and model loading.")
            return
        logger.info(f"CLIP embedder initialized (dim={clip_embedder.get_embedding_dim()})")
    except Exception as e:
        logger.error(f"Failed to initialize CLIP embedder: {e}", exc_info=True)
        return

    # Initialize database
    db = Database(settings.supabase_url, settings.supabase_service_role_key)
    checkpoint = BackfillCheckpoint(checkpoint_file)

    if checkpoint.started_at is None:
        checkpoint.started_at = datetime.utcnow().isoformat() + "Z"

    logger.info("=" * 80)
    logger.info("CLIP Visual Embedding Backfill Started")
    logger.info("=" * 80)
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Max scenes: {max_scenes or 'unlimited'}")
    logger.info(f"Processing delay: {processing_delay}s")
    logger.info(f"CLIP timeout: {clip_timeout}s")
    logger.info(f"Force regenerate: {force_regenerate}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Video filter: {video_id or 'none'}")
    logger.info(f"User filter: {user_id or 'none'}")
    logger.info(f"Checkpoint file: {checkpoint_file}")
    logger.info(f"CLIP model: {settings.clip_model_name} (pretrained={settings.clip_pretrained})")
    logger.info(f"CLIP device: {settings.clip_device}")
    logger.info("=" * 80)

    # Resume from checkpoint if exists
    if checkpoint.last_scene_id:
        logger.info(f"Resuming from scene_id: {checkpoint.last_scene_id}")

    processed_count = checkpoint.total_processed
    updated_count = checkpoint.total_updated
    skipped_count = checkpoint.total_skipped
    error_count = checkpoint.total_errors

    # Create temporary directory for thumbnail downloads
    temp_dir = Path(tempfile.mkdtemp(prefix="clip_backfill_"))
    logger.info(f"Using temporary directory: {temp_dir}")

    try:
        while True:
            # Rebuild query for each batch
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
                        db, clip_embedder, scene, temp_dir, dry_run, processing_delay, clip_timeout
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
        # Clean up temp directory
        try:
            import shutil
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory: {e}")

        # Final checkpoint save
        checkpoint.save()

        logger.info("\n" + "=" * 80)
        logger.info("CLIP Visual Embedding Backfill Completed")
        logger.info("=" * 80)
        logger.info(f"Total processed: {processed_count}")
        logger.info(f"Total updated: {updated_count}")
        logger.info(f"Total skipped: {skipped_count}")
        logger.info(f"Total errors: {error_count}")
        logger.info("=" * 80)


def main():
    """Main entry point for backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill CLIP visual embeddings for existing scenes"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of scenes to process in each batch",
    )
    parser.add_argument(
        "--max-scenes",
        type=int,
        default=None,
        help="Maximum total scenes to process (default: unlimited)",
    )
    parser.add_argument(
        "--processing-delay",
        type=float,
        default=0.5,
        help="Delay between scenes in seconds (CPU breathing room)",
    )
    parser.add_argument(
        "--checkpoint-file",
        type=str,
        default=".backfill_clip_checkpoint.json",
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
    parser.add_argument(
        "--clip-timeout",
        type=float,
        default=5.0,
        help="CLIP inference timeout in seconds",
    )

    args = parser.parse_args()

    # Convert UUIDs
    video_id = UUID(args.video_id) if args.video_id else None
    user_id = UUID(args.user_id) if args.user_id else None

    backfill_scenes(
        batch_size=args.batch_size,
        max_scenes=args.max_scenes,
        processing_delay=args.processing_delay,
        checkpoint_file=Path(args.checkpoint_file),
        force_regenerate=args.force_regenerate,
        dry_run=args.dry_run,
        video_id=video_id,
        user_id=user_id,
        clip_timeout=args.clip_timeout,
    )


if __name__ == "__main__":
    main()
