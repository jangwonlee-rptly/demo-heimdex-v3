"""Main video processing pipeline."""
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Semaphore
from typing import Optional
from uuid import UUID

from .scene_detector import scene_detector, DetectorPreferences
from .sidecar_builder import SidecarBuilder
from ..adapters.database import VideoStatus

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Orchestrates the complete video processing pipeline."""

    def __init__(self, db, storage, opensearch, openai, clip_embedder, ffmpeg, settings):
        """Initialize VideoProcessor with injected dependencies.

        Args:
            db: Database adapter
            storage: Supabase storage adapter
            opensearch: OpenSearch client (optional)
            openai: OpenAI client
            clip_embedder: CLIP embedder (optional)
            ffmpeg: FFmpeg adapter
            settings: Settings object
        """
        self.db = db
        self.storage = storage
        self.opensearch = opensearch
        self.openai = openai
        self.clip_embedder = clip_embedder
        self.ffmpeg = ffmpeg
        self.settings = settings
        # API rate limiting semaphore (configurable via settings)
        self._api_semaphore = Semaphore(settings.max_api_concurrency)
        # Create SidecarBuilder with injected dependencies
        self.sidecar_builder = SidecarBuilder(
            storage=storage,
            ffmpeg=ffmpeg,
            openai=openai,
            clip_embedder=clip_embedder,
            settings=settings,
        )

    def _process_single_scene(
        self,
        scene,
        video_path: Path,
        full_transcript: str,
        video_id: UUID,
        owner_id: UUID,
        work_dir: Path,
        language: str,
        total_scenes: int,
        video_duration_s: float,
        video_filename: Optional[str] = None,
        transcript_segments: Optional[list] = None,
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
            video_filename: Optional video filename for metadata inclusion
            transcript_segments: Optional list of Whisper segments with timestamps

        Returns:
            tuple[bool, str, int]: Tuple of (success, scene_id or error_message, scene_index)
        """
        try:
            logger.info(f"Processing scene {scene.index + 1}/{total_scenes}")

            # Acquire semaphore to limit concurrent API calls
            with self._api_semaphore:
                # Build sidecar with user's preferred language
                sidecar = self.sidecar_builder.build_sidecar(
                    scene=scene,
                    video_path=video_path,
                    full_transcript=full_transcript,
                    video_id=video_id,
                    owner_id=owner_id,
                    work_dir=work_dir,
                    language=language,
                    video_duration_s=video_duration_s,
                    video_filename=video_filename,
                    transcript_segments=transcript_segments,
                )

            # Save to database (outside semaphore to reduce lock time)
            scene_id = self.db.create_scene(
                video_id=video_id,
                index=sidecar.index,
                start_s=sidecar.start_s,
                end_s=sidecar.end_s,
                transcript_segment=sidecar.transcript_segment,
                visual_summary=sidecar.visual_summary,
                combined_text=sidecar.combined_text,
                embedding=sidecar.embedding,
                thumbnail_url=sidecar.thumbnail_url,
                visual_description=sidecar.visual_description,
                visual_entities=sidecar.visual_entities,
                visual_actions=sidecar.visual_actions,
                tags=sidecar.tags,
                # Sidecar v2 metadata fields
                sidecar_version=sidecar.sidecar_version,
                search_text=sidecar.search_text,
                embedding_metadata=sidecar.embedding_metadata.to_dict() if sidecar.embedding_metadata else None,
                needs_reprocess=sidecar.needs_reprocess,
                processing_stats=sidecar.processing_stats,
                # v3-multi embedding fields
                embedding_transcript=sidecar.embedding_transcript,
                embedding_visual=sidecar.embedding_visual,
                embedding_summary=sidecar.embedding_summary,
                embedding_version=sidecar.embedding_version,
                multi_embedding_metadata=sidecar.multi_embedding_metadata.to_dict() if sidecar.multi_embedding_metadata else None,
                # CLIP visual embedding fields
                embedding_visual_clip=sidecar.embedding_visual_clip,
                visual_clip_metadata=sidecar.visual_clip_metadata,
            )

            logger.info(f"Scene {scene.index} saved with id={scene_id}")
            return (True, str(scene_id), scene.index)

        except Exception as e:
            logger.error(f"Failed to process scene {scene.index}: {e}", exc_info=True)
            return (False, str(e), scene.index)

    def process_video(self, video_id: UUID) -> None:
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

        Returns:
            None: This function does not return a value.

        Raises:
            Exception: If processing fails
        """
        logger.info(f"Starting video processing for video_id={video_id}")

        # Phase 2: Record processing start time
        processing_started_at = datetime.utcnow()
        self.db.update_video_processing_start(video_id, processing_started_at)

        # Create working directory
        work_dir = Path(self.settings.temp_dir) / str(video_id)
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: Fetch video record
            logger.info("Fetching video record from database")
            self.db.update_video_processing_stage(video_id, "downloading")
            video = self.db.get_video(video_id)
            if not video:
                raise ValueError(f"Video {video_id} not found")

            owner_id = UUID(video["owner_id"])
            storage_path = video["storage_path"]
            filename = video.get("filename")  # Extract filename for metadata-aware search

            # Get transcript language override (set during reprocess)
            # This forces Whisper to use a specific language instead of auto-detect
            transcript_language = video.get("transcript_language")
            if transcript_language:
                logger.info(f"Using forced transcript language: {transcript_language}")
            else:
                logger.info("Using auto-detect for transcript language")

            # Fetch user's preferred language and scene detector preferences
            user_profile = self.db.get_user_profile(owner_id)
            language = user_profile.get("preferred_language", "ko") if user_profile else "ko"
            logger.info(f"Processing video with output language: {language}")

            # Get user's scene detector preferences (if any)
            detector_prefs_raw = user_profile.get("scene_detector_preferences") if user_profile else None
            detector_preferences = DetectorPreferences.from_dict(detector_prefs_raw)

            # Update status to PROCESSING
            self.db.update_video_status(video_id, VideoStatus.PROCESSING)

            # Step 2: Download video file
            logger.info(f"Downloading video from storage: {storage_path}")
            video_path = work_dir / "video.mp4"
            self.storage.download_file(storage_path, video_path)

            # Step 3: Extract metadata
            logger.info("Extracting video metadata")
            self.db.update_video_processing_stage(video_id, "metadata")
            try:
                metadata = self.ffmpeg.probe_video(video_path)
                logger.info(
                    f"Extracted metadata: duration={metadata.duration_s:.2f}s, "
                    f"resolution={metadata.width}x{metadata.height}, "
                    f"fps={metadata.frame_rate:.2f}"
                )

                # Prepare EXIF metadata for storage
                exif_metadata = None
                location_latitude = None
                location_longitude = None
                location_name = None
                camera_make = None
                camera_model = None

                if metadata.exif:
                    exif = metadata.exif
                    exif_metadata = exif.to_dict() or None

                    # Denormalized fields for efficient queries
                    if exif.has_location():
                        location_latitude = exif.latitude
                        location_longitude = exif.longitude
                        location_name = exif.location_name  # Will be None initially

                    camera_make = exif.camera_make
                    camera_model = exif.camera_model

                    if exif.has_location():
                        logger.info(
                            f"EXIF GPS: lat={location_latitude}, lon={location_longitude}"
                        )
                    if camera_make or camera_model:
                        logger.info(f"EXIF Camera: {camera_make} {camera_model}")

                self.db.update_video_metadata(
                    video_id=video_id,
                    duration_s=metadata.duration_s,
                    frame_rate=metadata.frame_rate,
                    width=metadata.width,
                    height=metadata.height,
                    video_created_at=metadata.created_at,
                    exif_metadata=exif_metadata,
                    location_latitude=location_latitude,
                    location_longitude=location_longitude,
                    location_name=location_name,
                    camera_make=camera_make,
                    camera_model=camera_model,
                )
                logger.info("Video metadata updated successfully")
            except Exception as e:
                logger.error(f"Failed to extract or update video metadata: {e}", exc_info=True)
                # Don't fail the entire processing - continue without metadata
                # But log the error for debugging
                raise

            # Step 4: Detect scenes using best-of-all-detectors approach
            logger.info("Detecting scenes using multi-detector approach")
            self.db.update_video_processing_stage(video_id, "scene_detection")
            scenes, detection_result = scene_detector.detect_scenes_with_preferences(
                video_path,
                self.settings,
                video_duration_s=metadata.duration_s,
                fps=metadata.frame_rate,
                preferences=detector_preferences,
                use_best=True,  # Try all detectors, pick the one with most scenes
            )

            logger.info(
                f"Detected {len(scenes)} scenes using {detection_result.strategy.value} detector"
            )

            # Step 5: Extract audio and transcribe (with caching for idempotency)
            logger.info("Checking for cached transcript")
            self.db.update_video_processing_stage(video_id, "transcription")
            full_transcript, transcript_segments = self.db.get_cached_transcript(video_id)

            if full_transcript:
                if transcript_segments:
                    logger.info(
                        f"Using cached transcript ({len(full_transcript)} characters, "
                        f"{len(transcript_segments)} segments)"
                    )
                else:
                    logger.info(
                        f"Using cached transcript ({len(full_transcript)} characters, "
                        "no segments - will use fallback extraction)"
                    )
            else:
                logger.info("No cached transcript found, checking for audio stream")
                full_transcript = ""
                transcript_segments = None

                if self.ffmpeg.has_audio_stream(video_path):
                    logger.info("Extracting and transcribing audio (this may take a while...)")
                    audio_path = work_dir / "audio.mp3"
                    self.ffmpeg.extract_audio(video_path, audio_path)

                    # Pass transcript_language to Whisper if set (from reprocess request)
                    # Use quality-aware transcription to filter out music/noise
                    transcription_result = self.openai.transcribe_audio_with_quality(
                        audio_path,
                        language=transcript_language,
                    )

                    if transcription_result.has_speech:
                        full_transcript = transcription_result.text
                        transcript_segments = transcription_result.segments
                        logger.info(
                            f"Transcription accepted: {len(full_transcript)} characters, "
                            f"{len(transcript_segments) if transcript_segments else 0} segments"
                        )
                    else:
                        full_transcript = ""
                        transcript_segments = None
                        logger.info(
                            f"Video {video_id}: no meaningful speech detected "
                            f"(reason={transcription_result.reason}), skipping transcript"
                        )

                    # Save transcript and segments as checkpoint for future retries
                    # (empty string/None if no speech detected)
                    self.db.save_transcript(video_id, full_transcript, transcript_segments)
                else:
                    logger.warning("No audio stream found, skipping transcription")

            # Step 6: Process each scene in parallel (skip already processed scenes for idempotency)
            logger.info(f"Processing {len(scenes)} scenes in parallel")
            self.db.update_video_processing_stage(video_id, "scene_processing")

            # Get set of scene indices that have already been processed
            existing_scene_indices = self.db.get_existing_scene_indices(video_id)
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
                max_workers = min(self.settings.max_scene_workers, len(scenes_to_process))
                logger.info(f"Using {max_workers} parallel workers for scene processing")

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all scene processing tasks
                    future_to_scene = {
                        executor.submit(
                            self._process_single_scene,
                            scene,
                            video_path,
                            full_transcript,
                            video_id,
                            owner_id,
                            work_dir,
                            language,
                            len(scenes),
                            metadata.duration_s,
                            filename,
                            transcript_segments,
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
                    thumbnail_url = self.storage.upload_file(
                        thumbnail_path,
                        thumbnail_storage_path,
                        content_type="image/jpeg",
                    )
                    self.db.update_video_metadata(video_id=video_id, thumbnail_url=thumbnail_url)

            # Step 7.5: Generate scene person embeddings for person-aware search (Phase 7)
            logger.info("Generating scene person embeddings (Phase 7)")
            try:
                self._generate_scene_person_embeddings(owner_id, video_id)
            except Exception as e:
                # Log but don't fail - person search is a best-effort feature
                logger.error(f"Scene person embedding generation failed: {e}", exc_info=True)

            # Step 8: Generate video-level summary from scene descriptions (v2)
            logger.info("Generating video-level summary from scene descriptions")
            try:
                scene_descriptions = self.db.get_scene_descriptions(video_id)

                if scene_descriptions:
                    logger.info(f"Found {len(scene_descriptions)} scene descriptions for video summary")
                    video_summary = self.openai.summarize_video_from_scenes(
                        scene_descriptions,
                        transcript_language=language,
                    )

                    if video_summary:
                        logger.info(f"Generated video summary: {video_summary[:100]}...")
                        self.db.update_video_metadata(
                            video_id=video_id,
                            video_summary=video_summary,
                            has_rich_semantics=True,
                        )
                    else:
                        logger.warning("Failed to generate video summary")
                        # Still mark as having rich semantics even if summary failed
                        self.db.update_video_metadata(video_id=video_id, has_rich_semantics=True)
                else:
                    logger.warning("No scene descriptions found for video summary")
                    # Mark as having rich semantics even without summary (scenes have tags)
                    self.db.update_video_metadata(video_id=video_id, has_rich_semantics=True)

            except Exception as e:
                logger.error(f"Failed to generate video summary: {e}", exc_info=True)
                # Continue processing - summary generation failure shouldn't fail the entire job
                # Still mark as having rich semantics (scenes have the new fields)
                self.db.update_video_metadata(video_id=video_id, has_rich_semantics=True)

            # Mark as READY
            self.db.update_video_processing_stage(video_id, "finalizing")
            self.db.update_video_status(video_id, VideoStatus.READY)

            # Phase 2: Record completion time and duration
            processing_finished_at = datetime.utcnow()
            processing_duration_ms = int((processing_finished_at - processing_started_at).total_seconds() * 1000)
            self.db.update_video_processing_finish(
                video_id,
                processing_finished_at,
                processing_duration_ms,
                "completed"
            )

            logger.info(
                f"Video processing complete for video_id={video_id}, "
                f"duration={processing_duration_ms}ms ({processing_duration_ms/1000:.1f}s)"
            )

        except Exception as e:
            logger.error(f"Video processing failed for video_id={video_id}: {e}", exc_info=True)
            # Mark as FAILED with error message
            self.db.update_video_status(
                video_id,
                VideoStatus.FAILED,
                error_message=str(e)[:500],  # Truncate error message
            )

            # Phase 2: Record failure time and duration
            processing_finished_at = datetime.utcnow()
            processing_duration_ms = int((processing_finished_at - processing_started_at).total_seconds() * 1000)
            self.db.update_video_processing_finish(
                video_id,
                processing_finished_at,
                processing_duration_ms,
                "failed"
            )

            raise

        finally:
            # Clean up working directory
            if work_dir.exists():
                logger.info(f"Cleaning up working directory: {work_dir}")
                shutil.rmtree(work_dir, ignore_errors=True)

    def _generate_scene_person_embeddings(
        self,
        owner_id: UUID,
        video_id: UUID,
    ) -> None:
        """Generate person embeddings for scenes (idempotent, Phase 7).

        Generates CLIP embeddings from scene thumbnails for person-aware search.
        Called after scene processing completes and thumbnails are uploaded.

        Args:
            owner_id: UUID of the video owner
            video_id: UUID of the video

        Note:
            Failures are logged but do not block video processing.
            This ensures person search feature never breaks existing pipeline.
        """
        # Skip if CLIP not available
        if not self.clip_embedder:
            logger.debug("CLIP embedder not available, skipping scene person embeddings")
            return

        logger.info(f"Generating scene person embeddings for video {video_id}")

        try:
            # Get all scenes for video (need scene IDs + indices)
            response = (
                self.db.client.table("video_scenes")
                .select("id,index")
                .eq("video_id", str(video_id))
                .order("index")
                .execute()
            )

            scenes = response.data
            if not scenes:
                logger.warning(f"No scenes found for video {video_id}")
                return

            logger.info(f"Processing {len(scenes)} scenes for person embeddings")

            processed_count = 0
            skipped_count = 0
            failed_count = 0

            for scene in scenes:
                scene_id = UUID(scene["id"])
                scene_index = scene["index"]

                try:
                    # Idempotency check
                    existing = self.db.get_scene_person_embedding(
                        scene_id=scene_id,
                        kind="thumbnail",
                        ordinal=0,
                    )

                    if existing:
                        skipped_count += 1
                        continue

                    # Compute deterministic thumbnail storage path
                    # Pattern: {owner_id}/{video_id}/thumbnails/scene_{index}.jpg
                    thumbnail_storage_path = (
                        f"{owner_id}/{video_id}/thumbnails/scene_{scene_index}.jpg"
                    )

                    # Download thumbnail to temporary location
                    from tempfile import TemporaryDirectory
                    with TemporaryDirectory() as tmpdir:
                        local_path = Path(tmpdir) / f"scene_{scene_index}.jpg"

                        # Download from storage
                        thumbnail_data = self.storage.download_file(thumbnail_storage_path)
                        local_path.write_bytes(thumbnail_data)

                        # Generate CLIP embedding
                        embedding, metadata = self.clip_embedder.create_visual_embedding(
                            image_path=local_path,
                            timeout_s=3.0,
                        )

                        if not embedding:
                            error_msg = metadata.error if metadata and metadata.error else "CLIP failed"
                            logger.warning(
                                f"Failed to generate embedding for scene {scene_index}: {error_msg}"
                            )
                            failed_count += 1
                            continue

                        # Validate dimension
                        if len(embedding) != 512:
                            logger.warning(
                                f"Invalid embedding dimension for scene {scene_index}: {len(embedding)}"
                            )
                            failed_count += 1
                            continue

                        # Normalize embedding if needed
                        import numpy as np
                        embedding_array = np.array(embedding)
                        norm = np.linalg.norm(embedding_array)
                        if abs(norm - 1.0) > 0.01:
                            embedding_array = embedding_array / norm
                            embedding = embedding_array.tolist()

                        # Store embedding (UPSERT on unique constraint)
                        self.db.create_scene_person_embedding(
                            owner_id=owner_id,
                            video_id=video_id,
                            scene_id=scene_id,
                            embedding=embedding,
                            kind="thumbnail",
                            ordinal=0,
                        )

                        processed_count += 1

                except Exception as e:
                    # Log but continue processing other scenes
                    logger.warning(
                        f"Failed to process scene {scene_index} for person embeddings: {e}"
                    )
                    failed_count += 1
                    continue

            logger.info(
                f"Scene person embeddings: processed={processed_count}, "
                f"skipped={skipped_count}, failed={failed_count}"
            )

        except Exception as e:
            # Log error but don't raise - this is a best-effort feature
            logger.error(f"Failed to generate scene person embeddings: {e}", exc_info=True)
