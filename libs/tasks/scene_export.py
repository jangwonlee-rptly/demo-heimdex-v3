"""Dramatiq task for scene export processing."""
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import dramatiq

logger = logging.getLogger(__name__)


@dramatiq.actor(max_retries=0, time_limit=600_000)  # 10 minute timeout
def export_scene_as_short(scene_id: str, export_id: str) -> None:
    """
    Export a video scene as YouTube Short (9:16, MP4).

    This task:
    1. Fetches scene and export metadata from database
    2. Downloads source video from storage
    3. Extracts scene clip (start_s to end_s)
    4. Converts to 9:16 aspect ratio (crop or letterbox)
    5. Encodes to YouTube Shorts specs (1080x1920, H.264, AAC)
    6. Uploads to storage (exports/{user_id}/{export_id}.mp4)
    7. Updates export record with metadata

    Args:
        scene_id: UUID of the scene to export (as string)
        export_id: UUID of the export record (as string)

    Raises:
        Exception: Any processing error (logged and saved to export record)
    """
    # Lazy import to avoid requiring worker dependencies in API service
    # When API calls .send(), this function body never executes
    # When Worker executes the job, this imports and runs successfully
    from src.adapters.database import db
    from src.adapters.supabase import storage
    from src.adapters.ffmpeg import ffmpeg

    logger.info(f"Starting export {export_id} for scene {scene_id}")

    scene_uuid = UUID(scene_id)
    export_uuid = UUID(export_id)

    try:
        # Update status to processing
        db.update_scene_export(export_uuid, status="processing")

        # Get export configuration
        export = db.get_scene_export(export_uuid)
        if not export:
            raise ValueError(f"Export {export_id} not found")

        # Get scene metadata
        scene = db.get_scene_by_id(scene_uuid)
        if not scene:
            raise ValueError(f"Scene {scene_id} not found")

        # Get parent video
        video_id = UUID(scene["video_id"])
        video = db.get_video(video_id)
        if not video:
            raise ValueError(f"Video {video_id} not found")

        if not video.get("storage_path"):
            raise ValueError(f"Video {video_id} has no storage_path")

        logger.info(
            f"Export config: {export['aspect_ratio_strategy']}, "
            f"{export['output_quality']}"
        )
        logger.info(
            f"Scene: {scene['start_s']:.2f}s - {scene['end_s']:.2f}s "
            f"(duration: {scene['end_s'] - scene['start_s']:.2f}s)"
        )

        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Download source video to temp directory
            source_video_path = temp_path / "source_video.mp4"
            logger.info(f"Downloading source video: {video['storage_path']}")
            storage.download_file(video["storage_path"], source_video_path)
            logger.info(f"Source video downloaded: {source_video_path.stat().st_size / 1024 / 1024:.2f} MB")

            # Extract and convert scene clip
            output_path = temp_path / f"export_{export_id}.mp4"
            logger.info("Extracting scene clip with FFmpeg...")

            metadata = ffmpeg.extract_scene_clip_with_aspect_conversion(
                video_path=source_video_path,
                start_s=scene["start_s"],
                end_s=scene["end_s"],
                output_path=output_path,
                aspect_ratio_strategy=export["aspect_ratio_strategy"],
                output_quality=export["output_quality"],
            )

            logger.info(
                f"Scene clip created: {metadata['file_size_bytes'] / 1024 / 1024:.2f} MB, "
                f"{metadata['duration_s']:.2f}s, {metadata['resolution']}"
            )

            # Upload to storage: exports/{user_id}/{export_id}.mp4
            storage_path = f"exports/{export['user_id']}/{export_id}.mp4"
            logger.info(f"Uploading to storage: {storage_path}")
            storage.upload_file(output_path, storage_path, content_type="video/mp4")
            logger.info("Upload complete")

            # Update export record with success
            db.update_scene_export(
                export_uuid,
                status="completed",
                storage_path=storage_path,
                file_size_bytes=metadata["file_size_bytes"],
                duration_s=metadata["duration_s"],
                resolution=metadata["resolution"],
                completed_at=datetime.now(timezone.utc),
            )

        logger.info(f"Export {export_id} completed successfully")

    except Exception as e:
        error_message = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Export {export_id} failed: {error_message}", exc_info=True)

        # Update export record with failure
        try:
            db.update_scene_export(
                export_uuid,
                status="failed",
                error_message=error_message[:500],  # Truncate long errors
                completed_at=datetime.now(timezone.utc),
            )
        except Exception as db_error:
            logger.error(f"Failed to update export status: {db_error}")

        # Re-raise to mark task as failed in Dramatiq
        raise
