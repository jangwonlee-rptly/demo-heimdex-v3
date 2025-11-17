"""Main video processing pipeline."""
import logging
import shutil
from pathlib import Path
from uuid import UUID

from .scene_detector import scene_detector
from .sidecar_builder import sidecar_builder
from ..adapters.database import db, VideoStatus
from ..adapters.supabase import storage
from ..adapters.ffmpeg import ffmpeg
from ..adapters.openai_client import openai_client
from ..config import settings

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Orchestrates the complete video processing pipeline."""

    @staticmethod
    def process_video(video_id: UUID) -> None:
        """
        Process a video through the complete pipeline.

        Steps:
        1. Fetch video record and download file
        2. Extract metadata (duration, resolution, fps, etc.)
        3. Detect scenes
        4. Extract audio and transcribe
        5. For each scene:
           - Extract keyframes
           - Analyze visuals with GPT-4o
           - Build combined text and embedding
           - Save scene sidecar
        6. Mark video as READY or FAILED

        Args:
            video_id: ID of the video to process

        Raises:
            Exception: If processing fails
        """
        logger.info(f"Starting video processing for video_id={video_id}")

        # Create working directory
        work_dir = Path(settings.temp_dir) / str(video_id)
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: Fetch video record
            logger.info("Fetching video record from database")
            video = db.get_video(video_id)
            if not video:
                raise ValueError(f"Video {video_id} not found")

            owner_id = UUID(video["owner_id"])
            storage_path = video["storage_path"]

            # Fetch user's preferred language
            user_profile = db.get_user_profile(owner_id)
            language = user_profile.get("preferred_language", "ko") if user_profile else "ko"
            logger.info(f"Processing video in language: {language}")

            # Update status to PROCESSING
            db.update_video_status(video_id, VideoStatus.PROCESSING)

            # Step 2: Download video file
            logger.info(f"Downloading video from storage: {storage_path}")
            video_path = work_dir / "video.mp4"
            storage.download_file(storage_path, video_path)

            # Step 3: Extract metadata
            logger.info("Extracting video metadata")
            metadata = ffmpeg.probe_video(video_path)
            db.update_video_metadata(
                video_id=video_id,
                duration_s=metadata.duration_s,
                frame_rate=metadata.frame_rate,
                width=metadata.width,
                height=metadata.height,
                video_created_at=metadata.created_at,
            )

            # Step 4: Detect scenes
            logger.info("Detecting scenes")
            scenes = scene_detector.detect_scenes(video_path)

            if not scenes:
                logger.warning("No scenes detected, creating single scene for entire video")
                from .scene_detector import Scene
                scenes = [Scene(index=0, start_s=0.0, end_s=metadata.duration_s)]

            logger.info(f"Detected {len(scenes)} scenes")

            # Step 5: Extract audio and transcribe (with caching for idempotency)
            logger.info("Checking for cached transcript")
            full_transcript = db.get_cached_transcript(video_id)

            if full_transcript:
                logger.info(f"Using cached transcript ({len(full_transcript)} characters)")
            else:
                logger.info("No cached transcript found, checking for audio stream")
                full_transcript = ""

                if ffmpeg.has_audio_stream(video_path):
                    logger.info("Extracting and transcribing audio (this may take a while...)")
                    audio_path = work_dir / "audio.mp3"
                    ffmpeg.extract_audio(video_path, audio_path)

                    full_transcript = openai_client.transcribe_audio(audio_path)
                    logger.info(f"Transcription complete: {len(full_transcript)} characters")

                    # Save transcript as checkpoint for future retries
                    db.save_transcript(video_id, full_transcript)
                else:
                    logger.warning("No audio stream found, skipping transcription")

            # Step 6: Process each scene (skip already processed scenes for idempotency)
            logger.info(f"Processing {len(scenes)} scenes")

            # Get set of scene indices that have already been processed
            existing_scene_indices = db.get_existing_scene_indices(video_id)
            if existing_scene_indices:
                logger.info(f"Found {len(existing_scene_indices)} already processed scenes, skipping them")

            scenes_processed = 0
            scenes_skipped = 0

            for scene in scenes:
                # Skip if scene already exists (idempotent retry)
                if scene.index in existing_scene_indices:
                    logger.info(f"Scene {scene.index} already exists, skipping processing")
                    scenes_skipped += 1
                    continue

                logger.info(f"Processing scene {scene.index + 1}/{len(scenes)}")

                # Build sidecar with user's preferred language
                sidecar = sidecar_builder.build_sidecar(
                    scene=scene,
                    video_path=video_path,
                    full_transcript=full_transcript,
                    video_id=video_id,
                    owner_id=owner_id,
                    work_dir=work_dir,
                    language=language,
                )

                # Save to database
                scene_id = db.create_scene(
                    video_id=video_id,
                    index=sidecar.index,
                    start_s=sidecar.start_s,
                    end_s=sidecar.end_s,
                    transcript_segment=sidecar.transcript_segment,
                    visual_summary=sidecar.visual_summary,
                    combined_text=sidecar.combined_text,
                    embedding=sidecar.embedding,
                    thumbnail_url=sidecar.thumbnail_url,
                )

                logger.info(f"Scene {scene.index} saved with id={scene_id}")
                scenes_processed += 1

            logger.info(
                f"Scene processing complete: {scenes_processed} processed, "
                f"{scenes_skipped} skipped (already existed)"
            )

            # Step 7: Upload video thumbnail (use first scene's thumbnail)
            if scenes:
                first_scene = scenes[0]
                thumbnail_path = work_dir / f"scene_{first_scene.index}_frame_0.jpg"
                if thumbnail_path.exists():
                    thumbnail_storage_path = f"{owner_id}/{video_id}/thumbnail.jpg"
                    thumbnail_url = storage.upload_file(
                        thumbnail_path,
                        thumbnail_storage_path,
                        content_type="image/jpeg",
                    )
                    db.update_video_metadata(video_id=video_id, thumbnail_url=thumbnail_url)

            # Mark as READY
            db.update_video_status(video_id, VideoStatus.READY)
            logger.info(f"Video processing complete for video_id={video_id}")

        except Exception as e:
            logger.error(f"Video processing failed for video_id={video_id}: {e}", exc_info=True)
            # Mark as FAILED with error message
            db.update_video_status(
                video_id,
                VideoStatus.FAILED,
                error_message=str(e)[:500],  # Truncate error message
            )
            raise

        finally:
            # Clean up working directory
            if work_dir.exists():
                logger.info(f"Cleaning up working directory: {work_dir}")
                shutil.rmtree(work_dir, ignore_errors=True)


# Global video processor instance
video_processor = VideoProcessor()
