"""Main video processing pipeline."""
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Semaphore
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

    # API rate limiting semaphore (configurable via settings)
    _api_semaphore = Semaphore(settings.max_api_concurrency)

    @staticmethod
    def _process_single_scene(
        scene,
        video_path: Path,
        full_transcript: str,
        video_id: UUID,
        owner_id: UUID,
        work_dir: Path,
        language: str,
        total_scenes: int,
        video_duration_s: float,
    ) -> tuple[bool, str, int]:
        """
        Process a single scene (used for parallel execution).

        Args:
            scene: Scene object to process
            video_path: Path to video file
            full_transcript: Full video transcript
            video_id: Video ID
            owner_id: Owner ID
            work_dir: Working directory
            language: Language for processing
            total_scenes: Total number of scenes (for logging)
            video_duration_s: Video duration in seconds

        Returns:
            Tuple of (success, scene_id or error_message, scene_index)
        """
        try:
            logger.info(f"Processing scene {scene.index + 1}/{total_scenes}")

            # Acquire semaphore to limit concurrent API calls
            with VideoProcessor._api_semaphore:
                # Build sidecar with user's preferred language
                sidecar = sidecar_builder.build_sidecar(
                    scene=scene,
                    video_path=video_path,
                    full_transcript=full_transcript,
                    video_id=video_id,
                    owner_id=owner_id,
                    work_dir=work_dir,
                    language=language,
                    video_duration_s=video_duration_s,
                )

            # Save to database (outside semaphore to reduce lock time)
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
            return (True, str(scene_id), scene.index)

        except Exception as e:
            logger.error(f"Failed to process scene {scene.index}: {e}", exc_info=True)
            return (False, str(e), scene.index)

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
            scenes = scene_detector.detect_scenes(
                video_path,
                video_duration_s=metadata.duration_s,
                fps=metadata.frame_rate,
            )

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

            # Step 6: Process each scene in parallel (skip already processed scenes for idempotency)
            logger.info(f"Processing {len(scenes)} scenes in parallel")

            # Get set of scene indices that have already been processed
            existing_scene_indices = db.get_existing_scene_indices(video_id)
            if existing_scene_indices:
                logger.info(f"Found {len(existing_scene_indices)} already processed scenes, skipping them")

            # Filter out already processed scenes
            scenes_to_process = [s for s in scenes if s.index not in existing_scene_indices]
            scenes_skipped = len(scenes) - len(scenes_to_process)

            if scenes_skipped > 0:
                logger.info(f"Skipping {scenes_skipped} already processed scenes")

            scenes_processed = 0
            failed_scenes = []

            # Process scenes in parallel using ThreadPoolExecutor
            if scenes_to_process:
                max_workers = min(settings.max_scene_workers, len(scenes_to_process))
                logger.info(f"Using {max_workers} parallel workers for scene processing")

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all scene processing tasks
                    future_to_scene = {
                        executor.submit(
                            VideoProcessor._process_single_scene,
                            scene,
                            video_path,
                            full_transcript,
                            video_id,
                            owner_id,
                            work_dir,
                            language,
                            len(scenes),
                            metadata.duration_s,
                        ): scene
                        for scene in scenes_to_process
                    }

                    # Collect results as they complete
                    for future in as_completed(future_to_scene):
                        scene = future_to_scene[future]
                        try:
                            success, result, scene_index = future.result()
                            if success:
                                scenes_processed += 1
                            else:
                                failed_scenes.append((scene_index, result))
                                logger.error(f"Scene {scene_index} failed: {result}")
                        except Exception as e:
                            failed_scenes.append((scene.index, str(e)))
                            logger.error(f"Exception processing scene {scene.index}: {e}", exc_info=True)

            logger.info(
                f"Scene processing complete: {scenes_processed} processed, "
                f"{scenes_skipped} skipped (already existed), "
                f"{len(failed_scenes)} failed"
            )

            # If any scenes failed, log them but continue (partial success is OK)
            if failed_scenes:
                logger.warning(f"Failed scenes: {failed_scenes}")
                # Don't raise exception - partial processing is acceptable

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
