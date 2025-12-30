"""Highlight reel export Dramatiq actor.

This module defines the process_highlight_export actor for combining multiple
video scenes into a single highlight reel video.

Architecture:
- API service: Imports this actor and calls process_highlight_export.send(job_id)
- Worker service: Imports this actor; when executed, it uses FFmpeg to concatenate scenes
"""
import logging
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID

import dramatiq

logger = logging.getLogger(__name__)


@dramatiq.actor(
    queue_name="highlight_export",
    max_retries=1,  # Limit retries for expensive FFmpeg operations
    min_backoff=30000,  # 30 seconds
    max_backoff=120000,  # 2 minutes
    time_limit=1800000,  # 30 minute timeout
)
def process_highlight_export(job_id: str) -> None:
    """
    Process a highlight reel export job.

    This task:
    1. Fetches job configuration from database
    2. Downloads source video segments from storage
    3. Cuts each segment with FFmpeg
    4. Concatenates segments in user-specified order
    5. Uploads final video to storage
    6. Updates job record with output metadata

    Args:
        job_id: UUID of the highlight export job (as string)

    Raises:
        Exception: Any processing error (logged and saved to job record)
    """
    # Get worker context for dependency injection
    from src.tasks import get_worker_context

    ctx = get_worker_context()
    db = ctx.db
    storage = ctx.storage
    ffmpeg = ctx.ffmpeg

    logger.info(f"Starting highlight export job {job_id}")

    job_uuid = UUID(job_id)

    try:
        # Update status to processing
        db.update_highlight_export_job(job_uuid, status="processing")

        # Get job configuration
        job = db.get_highlight_export_job(job_uuid)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        request = job["request"]
        scenes = request.get("scenes", [])
        total_scenes = len(scenes)

        if not scenes:
            raise ValueError("No scenes in job request")

        logger.info(
            f"Processing {total_scenes} scenes, "
            f"total duration: {request.get('total_duration_s', 0):.1f}s"
        )

        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            clips_dir = temp_path / "clips"
            clips_dir.mkdir()

            # Track downloaded videos to avoid re-downloading
            downloaded_videos: dict[str, Path] = {}

            # Update progress: cutting stage
            db.update_highlight_export_job(
                job_uuid,
                progress={"stage": "cutting", "done": 0, "total": total_scenes}
            )

            # Process each scene
            clip_paths: list[Path] = []
            for idx, scene in enumerate(scenes):
                scene_id = scene["scene_id"]
                video_id = scene["video_id"]
                storage_path = scene["video_storage_path"]
                start_s = scene["start_s"]
                end_s = scene["end_s"]

                logger.info(
                    f"Processing scene {idx + 1}/{total_scenes}: "
                    f"{start_s:.1f}s - {end_s:.1f}s from {storage_path}"
                )

                # Download source video if not already cached
                if storage_path not in downloaded_videos:
                    source_path = temp_path / f"source_{video_id}.mp4"
                    logger.info(f"Downloading: {storage_path}")
                    storage.download_file(storage_path, source_path)
                    downloaded_videos[storage_path] = source_path
                    logger.info(f"Downloaded: {source_path.stat().st_size / 1024 / 1024:.2f} MB")

                source_video = downloaded_videos[storage_path]

                # Cut the clip with FFmpeg
                clip_path = clips_dir / f"clip_{idx:03d}.mp4"
                _cut_clip(source_video, start_s, end_s, clip_path)
                clip_paths.append(clip_path)

                # Update progress
                db.update_highlight_export_job(
                    job_uuid,
                    progress={"stage": "cutting", "done": idx + 1, "total": total_scenes}
                )

            # Update progress: concatenation stage
            db.update_highlight_export_job(
                job_uuid,
                progress={"stage": "concat", "done": total_scenes, "total": total_scenes}
            )

            # Create concat list file
            concat_list_path = temp_path / "concat.txt"
            with open(concat_list_path, "w") as f:
                for clip_path in clip_paths:
                    f.write(f"file '{clip_path}'\n")

            # Concatenate clips
            output_path = temp_path / f"highlight_{job_id}.mp4"
            _concat_clips(concat_list_path, output_path)

            logger.info(
                f"Concatenated output: {output_path.stat().st_size / 1024 / 1024:.2f} MB"
            )

            # Update progress: upload stage
            db.update_highlight_export_job(
                job_uuid,
                progress={"stage": "upload", "done": total_scenes, "total": total_scenes}
            )

            # Upload to storage
            storage_output_path = f"highlights/{job['user_id']}/{job_id}.mp4"
            logger.info(f"Uploading to: {storage_output_path}")
            storage.upload_file(output_path, storage_output_path, content_type="video/mp4")

            # Get output metadata
            file_size = output_path.stat().st_size
            duration = request.get("total_duration_s", 0)

            # Update job with success
            db.update_highlight_export_job(
                job_uuid,
                status="done",
                progress={"stage": "complete", "done": total_scenes, "total": total_scenes},
                output={
                    "storage_path": storage_output_path,
                    "file_size_bytes": file_size,
                    "duration_s": duration,
                    "resolution": "original",
                },
            )

        logger.info(f"Highlight export job {job_id} completed successfully")

    except Exception as e:
        error_message = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Highlight export job {job_id} failed: {error_message}", exc_info=True)

        # Get ffmpeg stderr if available
        ffmpeg_stderr = None
        if hasattr(e, "stderr"):
            ffmpeg_stderr = str(e.stderr)[-500:]  # Last 500 chars

        # Update job with failure
        try:
            db.update_highlight_export_job(
                job_uuid,
                status="error",
                error={
                    "message": error_message[:500],
                    "detail": str(e)[:1000],
                    "ffmpeg_stderr_tail": ffmpeg_stderr,
                },
            )
        except Exception as db_error:
            logger.error(f"Failed to update job status: {db_error}")

        raise


def _cut_clip(input_path: Path, start_s: float, end_s: float, output_path: Path) -> None:
    """
    Cut a segment from a video file using FFmpeg.

    Uses re-encoding for compatibility and consistent output format.

    Args:
        input_path: Path to source video
        start_s: Start time in seconds
        end_s: End time in seconds
        output_path: Path for output clip
    """
    cmd = [
        "ffmpeg",
        "-ss", str(start_s),
        "-to", str(end_s),
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-y",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"FFmpeg cut failed: {result.stderr}")
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )


def _concat_clips(concat_list_path: Path, output_path: Path) -> None:
    """
    Concatenate clips using FFmpeg concat demuxer.

    First tries stream copy (faster), falls back to re-encoding if needed.

    Args:
        concat_list_path: Path to concat.txt file listing clips
        output_path: Path for final output video
    """
    # Try stream copy first (faster if all clips have same encoding)
    cmd_copy = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c", "copy",
        "-movflags", "+faststart",
        "-y",
        str(output_path),
    ]

    result = subprocess.run(cmd_copy, capture_output=True, text=True)

    if result.returncode == 0:
        logger.info("Concatenation completed with stream copy")
        return

    logger.warning(f"Stream copy concat failed, falling back to re-encode: {result.stderr[:200]}")

    # Fallback: re-encode for compatibility
    cmd_reencode = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-y",
        str(output_path),
    ]

    result = subprocess.run(cmd_reencode, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"FFmpeg concat re-encode failed: {result.stderr}")
        raise subprocess.CalledProcessError(
            result.returncode, cmd_reencode, result.stdout, result.stderr
        )

    logger.info("Concatenation completed with re-encode")
