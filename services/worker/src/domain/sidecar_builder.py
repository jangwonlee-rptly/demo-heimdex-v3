"""
Sidecar builder for scene metadata.

This module builds rich scene sidecars for video search indexing. Key design decisions:

1. VERSIONING: All sidecars include a `sidecar_version` field to support future schema
   migrations. When processing logic changes significantly, bump the version so we can
   identify scenes that may benefit from reprocessing.

2. SEARCH TEXT: Transcript content is prioritized in search_text since ASR often carries
   the highest semantic signal for search queries. Visual descriptions supplement this.

3. MODULAR EMBEDDINGS: Embedding generation is isolated in `_create_scene_embedding()` to
   make it easy to swap models, add caching, or generate multiple embeddings in the future.

4. COST CONTROLS: Visual analysis can be skipped based on scene duration and transcript
   quality to reduce API costs while maintaining search quality.
"""
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from uuid import UUID

from .scene_detector import Scene
from .frame_quality import frame_quality_checker
from ..adapters.openai_client import openai_client
from ..adapters.ffmpeg import ffmpeg
from ..adapters.supabase import storage
from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingMetadata:
    """
    Metadata about how an embedding was generated.

    Useful for debugging, cost tracking, and future model migrations.
    This allows us to identify which embeddings might benefit from
    regeneration when we upgrade models.
    """
    model: str
    dimensions: int
    input_text_hash: str  # SHA-256 hash of input text for cache lookup
    input_text_length: int

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "model": self.model,
            "dimensions": self.dimensions,
            "input_text_hash": self.input_text_hash,
            "input_text_length": self.input_text_length,
        }


class SceneSidecar:
    """
    Scene sidecar metadata for search indexing.

    Design notes:
    - `sidecar_version` enables future schema migrations and reprocessing identification
    - `search_text` is the optimized text specifically for embedding (transcript-first)
    - `combined_text` remains for backward compatibility
    - Placeholder fields for future multi-embedding support are documented but not yet populated
    """

    # Current sidecar schema version. Bump this when making significant changes to
    # how sidecars are built (e.g., new fields, changed embedding strategy).
    CURRENT_VERSION = "v2"

    def __init__(
        self,
        index: int,
        start_s: float,
        end_s: float,
        transcript_segment: str,
        visual_summary: str,
        combined_text: str,
        embedding: list[float],
        thumbnail_url: Optional[str] = None,
        visual_description: Optional[str] = None,
        visual_entities: Optional[list[str]] = None,
        visual_actions: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        # New v2 fields for future-proofing
        sidecar_version: Optional[str] = None,
        search_text: Optional[str] = None,
        embedding_metadata: Optional[EmbeddingMetadata] = None,
        needs_reprocess: bool = False,
        processing_stats: Optional[dict] = None,
    ):
        """Initialize SceneSidecar.

        Args:
            index: The scene index.
            start_s: Start time in seconds.
            end_s: End time in seconds.
            transcript_segment: The transcript segment for the scene.
            visual_summary: The visual summary of the scene.
            combined_text: The combined text for embedding (backward compat).
            embedding: The embedding vector.
            thumbnail_url: The URL of the scene thumbnail (optional).
            visual_description: Richer 1-2 sentence description (v2).
            visual_entities: List of main entities detected (v2).
            visual_actions: List of actions detected (v2).
            tags: Normalized tags for filtering (v2).
            sidecar_version: Schema version for migration tracking (v2).
            search_text: Optimized text for embedding generation (v2).
            embedding_metadata: Info about embedding model/generation (v2).
            needs_reprocess: Flag indicating this sidecar may benefit from reprocessing (v2).
            processing_stats: Debug stats about sidecar generation (v2).
        """
        self.index = index
        self.start_s = start_s
        self.end_s = end_s
        self.transcript_segment = transcript_segment
        self.visual_summary = visual_summary
        self.combined_text = combined_text
        self.embedding = embedding
        self.thumbnail_url = thumbnail_url
        self.visual_description = visual_description
        self.visual_entities = visual_entities or []
        self.visual_actions = visual_actions or []
        self.tags = tags or []

        # v2 fields with sensible defaults
        self.sidecar_version = sidecar_version or self.CURRENT_VERSION
        self.search_text = search_text or combined_text
        self.embedding_metadata = embedding_metadata
        self.needs_reprocess = needs_reprocess
        self.processing_stats = processing_stats or {}

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "index": self.index,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "transcript_segment": self.transcript_segment,
            "visual_summary": self.visual_summary,
            "combined_text": self.combined_text,
            "thumbnail_url": self.thumbnail_url,
            "visual_description": self.visual_description,
            "visual_entities": self.visual_entities,
            "visual_actions": self.visual_actions,
            "tags": self.tags,
            "sidecar_version": self.sidecar_version,
            "search_text": self.search_text,
            "needs_reprocess": self.needs_reprocess,
        }
        if self.embedding_metadata:
            result["embedding_metadata"] = self.embedding_metadata.to_dict()
        if self.processing_stats:
            result["processing_stats"] = self.processing_stats
        return result


@dataclass
class ProcessingStats:
    """
    Statistics collected during sidecar building for cost/quality analysis.

    These stats help with:
    - Understanding API cost distribution
    - Debugging search quality issues
    - Tuning cost optimization thresholds
    """
    scene_duration_s: float = 0.0
    transcript_length: int = 0
    visual_analysis_called: bool = False
    visual_analysis_skipped_reason: Optional[str] = None
    search_text_length: int = 0
    combined_text_length: int = 0
    keyframes_extracted: int = 0
    best_frame_found: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "scene_duration_s": self.scene_duration_s,
            "transcript_length": self.transcript_length,
            "visual_analysis_called": self.visual_analysis_called,
            "visual_analysis_skipped_reason": self.visual_analysis_skipped_reason,
            "search_text_length": self.search_text_length,
            "combined_text_length": self.combined_text_length,
            "keyframes_extracted": self.keyframes_extracted,
            "best_frame_found": self.best_frame_found,
        }


class SidecarBuilder:
    """Builds scene sidecars with transcripts, visuals, and embeddings."""

    @staticmethod
    def _normalize_tags(entities: list[str], actions: list[str]) -> list[str]:
        """
        Normalize and combine entities and actions into tags.

        Normalization:
        - Trim whitespace
        - Convert to lowercase
        - Remove duplicates
        - Filter empty strings
        - Limit length to 40 characters per tag (increased to support detailed entity descriptions)

        Args:
            entities: List of entity strings
            actions: List of action strings

        Returns:
            List of normalized, deduplicated tags
        """
        all_tags = entities + actions

        # Normalize each tag
        normalized = []
        for tag in all_tags:
            if not tag:
                continue

            # Trim and lowercase
            tag = tag.strip().lower()

            # Skip empty or too long
            if not tag or len(tag) > 40:
                continue

            normalized.append(tag)

        # Deduplicate while preserving order
        seen = set()
        deduplicated = []
        for tag in normalized:
            if tag not in seen:
                seen.add(tag)
                deduplicated.append(tag)

        return deduplicated

    @staticmethod
    def _assess_scene_meaningfulness(
        transcript_segment: str,
        visual_description: str,
        visual_entities: list[str],
        visual_actions: list[str],
        tags: list[str],
        has_informative_frame: bool,
        scene_duration_s: float,
        language: str = "ko",
    ) -> str:
        """
        Assess scene meaningfulness and ensure we always return content.

        This method implements a multi-tier approach to scene assessment:
        - Tier 1: Strong signals (transcript, visual description)
        - Tier 2: Moderate signals (entities/actions, tags)
        - Tier 3: Fallback (frame passed quality, generic description)

        Args:
            transcript_segment: Transcript text
            visual_description: Description from OpenAI
            visual_entities: Extracted entities
            visual_actions: Extracted actions
            tags: Normalized tags
            has_informative_frame: Whether frame passed quality checks
            scene_duration_s: Scene duration
            language: Language code

        Returns:
            Enhanced visual description (never empty if ANY signal exists)
        """
        # Tier 1: If we have a strong visual description, use it
        if visual_description and visual_description.strip():
            return visual_description

        # Tier 2a: Build description from entities and actions
        if visual_entities or visual_actions:
            parts = []
            if language == "ko":
                if visual_entities:
                    parts.append(", ".join(visual_entities[:3]))
                if visual_actions:
                    parts.append(", ".join(visual_actions[:3]))
                description = " - ".join(parts) if parts else ""
            else:
                if visual_entities:
                    parts.append(", ".join(visual_entities[:3]))
                if visual_actions:
                    parts.append(", ".join(visual_actions[:3]))
                description = " - ".join(parts) if parts else ""

            if description:
                logger.info(
                    f"Built visual description from entities/actions: {description[:50]}..."
                )
                return description

        # Tier 2b: Build description from tags
        if tags:
            if language == "ko":
                description = f"시각적 장면: {', '.join(tags[:3])}"
            else:
                description = f"Visual scene: {', '.join(tags[:3])}"
            logger.info(f"Built visual description from tags: {description}")
            return description

        # Tier 3: Frame passed quality checks, use generic fallback
        if has_informative_frame:
            # Scene had visual content good enough for analysis
            if scene_duration_s > 3.0:
                if language == "ko":
                    description = "의미 있는 시각적 장면"
                else:
                    description = "Meaningful visual scene"
            else:
                if language == "ko":
                    description = "시각적 장면"
                else:
                    description = "Visual scene"

            logger.info(
                f"Using fallback visual description (frame passed quality): {description}"
            )
            return description

        # No visual signal at all, return empty
        return ""

    @staticmethod
    def _should_skip_visual_analysis(
        scene_duration_s: float,
        transcript_length: int,
        has_meaningful_transcript: bool,
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if visual analysis should be skipped based on cost optimization rules.

        Cost optimization logic:
        1. If visual semantics is disabled globally, skip
        2. If scene is very short AND transcript is rich, skip (transcript is sufficient)
        3. If transcript is empty/short, always analyze visuals (need visual signal)

        Args:
            scene_duration_s: Duration of the scene in seconds
            transcript_length: Length of transcript segment in characters
            has_meaningful_transcript: Whether transcript has meaningful content

        Returns:
            Tuple of (should_skip: bool, reason: Optional[str])
        """
        # Global disable check
        if not settings.visual_semantics_enabled:
            return True, "visual_semantics_disabled"

        # If no transcript, we need visual analysis for search signal
        if settings.visual_semantics_force_on_no_transcript and not has_meaningful_transcript:
            return False, None

        # Short scene with rich transcript - transcript is sufficient
        is_short_scene = scene_duration_s < settings.visual_semantics_min_duration_s
        has_rich_transcript = transcript_length >= settings.visual_semantics_transcript_threshold

        if is_short_scene and has_rich_transcript:
            return True, f"short_scene_rich_transcript (duration={scene_duration_s:.1f}s < {settings.visual_semantics_min_duration_s}s, transcript={transcript_length} chars)"

        return False, None

    @staticmethod
    def _create_scene_embedding(
        text: str,
        scene_index: int,
    ) -> tuple[list[float], EmbeddingMetadata]:
        """
        Create embedding for scene text with metadata tracking.

        This method is isolated to make it easy to:
        1. Swap embedding models in the future
        2. Add caching based on text hash
        3. Generate multiple embeddings (e.g., asr_embedding, vision_embedding)

        Args:
            text: Text to embed
            scene_index: Scene index for logging

        Returns:
            Tuple of (embedding vector, embedding metadata)
        """
        # Compute hash for potential cache lookup in the future
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        # Generate embedding
        embedding = openai_client.create_embedding(text)

        # Create metadata for tracking
        metadata = EmbeddingMetadata(
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            input_text_hash=text_hash,
            input_text_length=len(text),
        )

        logger.debug(
            f"Scene {scene_index} embedding: model={metadata.model}, "
            f"text_length={metadata.input_text_length}, hash={metadata.input_text_hash}"
        )

        return embedding, metadata

    @staticmethod
    def build_sidecar(
        scene: Scene,
        video_path: Path,
        full_transcript: str,
        video_id: UUID,
        owner_id: UUID,
        work_dir: Path,
        language: str = "ko",
        video_duration_s: Optional[float] = None,
        video_filename: Optional[str] = None,
    ) -> SceneSidecar:
        """
        Build a complete sidecar for a scene with optimized visual semantics.

        This method implements:
        1. Frame quality pre-filtering to avoid OpenAI calls for bad frames
        2. Transcript-first strategy (prefer ASR over weak visuals)
        3. Strict JSON schema prompts for token efficiency
        4. Configurable visual semantics processing
        5. Cost-optimized visual analysis skipping

        Args:
            scene: Scene object with time boundaries
            video_path: Path to video file
            full_transcript: Full video transcript
            video_id: Video ID for thumbnail path
            owner_id: Owner ID for thumbnail path
            work_dir: Working directory for temporary files
            language: Language for summaries and embeddings ('ko' or 'en')
            video_duration_s: Optional video duration for transcript extraction
            video_filename: Optional video filename for metadata inclusion

        Returns:
            SceneSidecar object
        """
        logger.info(f"Building sidecar for {scene} in language: {language}")

        # Initialize processing stats for cost/quality analysis
        scene_duration = scene.end_s - scene.start_s
        stats = ProcessingStats(scene_duration_s=scene_duration)

        # Use scene end time as fallback for video duration
        if video_duration_s is None:
            video_duration_s = scene.end_s

        # Extract transcript segment (simple time-based slicing)
        transcript_segment = SidecarBuilder._extract_transcript_segment(
            full_transcript, scene, video_duration_s
        )
        stats.transcript_length = len(transcript_segment) if transcript_segment else 0

        # Check if transcript is meaningful
        has_meaningful_transcript = (
            transcript_segment and len(transcript_segment.strip()) > 20
        )

        # Initialize visual semantics fields
        visual_summary = ""
        visual_description = None
        visual_entities = []
        visual_actions = []
        tags = []
        thumbnail_url = None
        best_frame_path = None

        # Determine if we should skip visual analysis (cost optimization)
        should_skip_visuals, skip_reason = SidecarBuilder._should_skip_visual_analysis(
            scene_duration,
            stats.transcript_length,
            has_meaningful_transcript,
        )

        if should_skip_visuals:
            stats.visual_analysis_skipped_reason = skip_reason
            logger.info(
                f"Scene {scene.index}: Skipping visual analysis - {skip_reason}"
            )

        # Process visual semantics if not skipped
        if not should_skip_visuals:
            # Extract keyframes
            keyframe_paths = SidecarBuilder._extract_keyframes(
                video_path, scene, work_dir
            )
            stats.keyframes_extracted = len(keyframe_paths)

            if keyframe_paths:
                # Rank frames by quality (best first)
                ranked_frames = frame_quality_checker.rank_frames_by_quality(keyframe_paths)
                stats.best_frame_found = len(ranked_frames) > 0

                if ranked_frames:
                    # Try frames in order of quality until we get meaningful content
                    max_attempts = min(
                        len(ranked_frames),
                        settings.visual_semantics_max_frame_retries
                    )
                    best_frame_path = ranked_frames[0][0]  # Keep best for thumbnail

                    visual_result = None
                    for attempt in range(max_attempts):
                        frame_path, frame_score = ranked_frames[attempt]

                        logger.info(
                            f"Scene {scene.index}: Analyzing frame {attempt + 1}/{max_attempts} "
                            f"(quality score: {frame_score:.2f})"
                        )
                        stats.visual_analysis_called = True

                        # Call optimized visual analysis (single frame, strict JSON)
                        # NOTE: Not passing transcript - visual analysis is now completely independent
                        visual_result = openai_client.analyze_scene_visuals_optimized(
                            frame_path,
                            language=language,
                        )

                        # Check if we got meaningful content
                        if visual_result and visual_result.get("status") == "ok":
                            logger.info(
                                f"Scene {scene.index}: Got meaningful content on attempt {attempt + 1}"
                            )
                            break
                        else:
                            logger.info(
                                f"Scene {scene.index}: Frame {attempt + 1} returned no_content"
                            )

                            # If retry is disabled or this is the last frame, stop
                            if not settings.visual_semantics_retry_on_no_content or attempt >= max_attempts - 1:
                                logger.info(
                                    f"Scene {scene.index}: No more frames to try"
                                )
                                break

                    # Process result if we got meaningful content
                    if visual_result and visual_result.get("status") == "ok":
                        # Extract richer description (v2)
                        description = visual_result.get("description", "")
                        if description:
                            visual_description = description
                            logger.info(f"Visual description: {visual_description[:100]}...")

                        # Extract entities and actions (v2)
                        if settings.visual_semantics_include_entities:
                            visual_entities = visual_result.get("main_entities", [])
                            logger.info(f"Extracted {len(visual_entities)} entities")

                        if settings.visual_semantics_include_actions:
                            visual_actions = visual_result.get("actions", [])
                            logger.info(f"Extracted {len(visual_actions)} actions")

                        # Normalize tags from entities and actions
                        tags = SidecarBuilder._normalize_tags(visual_entities, visual_actions)
                        logger.info(f"Normalized to {len(tags)} tags: {tags[:5]}")

                        # Build visual summary for backward compatibility
                        parts = []
                        if description:
                            parts.append(description)

                        if visual_entities:
                            if language == "ko":
                                parts.append(f"주요 대상: {', '.join(visual_entities)}")
                            else:
                                parts.append(f"Main entities: {', '.join(visual_entities)}")

                        if visual_actions:
                            if language == "ko":
                                parts.append(f"행동: {', '.join(visual_actions)}")
                            else:
                                parts.append(f"Actions: {', '.join(visual_actions)}")

                        visual_summary = ". ".join(parts)
                    else:
                        logger.warning(
                            f"Scene {scene.index}: All {max_attempts} frame(s) returned no_content"
                        )
                else:
                    logger.info(
                        f"No informative frames found for scene {scene.index}, "
                        f"skipping OpenAI call (saved tokens)"
                    )
                    stats.visual_analysis_skipped_reason = "no_informative_frames"

                # Upload thumbnail (use best frame if available, otherwise first)
                thumbnail_frame = best_frame_path or keyframe_paths[0]
                thumbnail_storage_path = (
                    f"{owner_id}/{video_id}/thumbnails/scene_{scene.index}.jpg"
                )
                thumbnail_url = storage.upload_file(
                    thumbnail_frame,
                    thumbnail_storage_path,
                    content_type="image/jpeg",
                )
            else:
                logger.warning(f"No keyframes extracted for scene {scene.index}")
                stats.visual_analysis_skipped_reason = "no_keyframes"
        else:
            # Still extract thumbnail even if skipping visual analysis
            keyframe_paths = SidecarBuilder._extract_keyframes(
                video_path, scene, work_dir
            )
            stats.keyframes_extracted = len(keyframe_paths)
            if keyframe_paths:
                thumbnail_frame = keyframe_paths[0]
                thumbnail_storage_path = (
                    f"{owner_id}/{video_id}/thumbnails/scene_{scene.index}.jpg"
                )
                thumbnail_url = storage.upload_file(
                    thumbnail_frame,
                    thumbnail_storage_path,
                    content_type="image/jpeg",
                )

        # Assess scene meaningfulness and enhance visual description if needed
        # This ensures scenes with ANY visual signal get meaningful descriptions
        has_informative_frame = best_frame_path is not None
        enhanced_visual_description = SidecarBuilder._assess_scene_meaningfulness(
            transcript_segment=transcript_segment,
            visual_description=visual_description or "",
            visual_entities=visual_entities,
            visual_actions=visual_actions,
            tags=tags,
            has_informative_frame=has_informative_frame,
            scene_duration_s=scene_duration,
            language=language,
        )

        # Use enhanced description if we got one
        if enhanced_visual_description and not visual_description:
            visual_description = enhanced_visual_description
            # Also update visual_summary if it's empty
            if not visual_summary:
                visual_summary = enhanced_visual_description

        # Build search-optimized text (transcript-first for better semantic matching)
        search_text = SidecarBuilder._build_search_text(
            transcript_segment,
            visual_description or visual_summary,
            language=language,
        )
        stats.search_text_length = len(search_text)

        # Build combined text for backward compatibility (includes metadata)
        combined_text = SidecarBuilder._build_combined_text(
            visual_summary, transcript_segment, language=language, video_filename=video_filename
        )
        stats.combined_text_length = len(combined_text)

        # If search text is empty or too short, use a placeholder
        if len(search_text.strip()) < 10:
            if language == "ko":
                search_text = "내용 없음"
            else:
                search_text = "No content"
            # Only warn if we truly have no signals at all
            if not has_meaningful_transcript and not has_informative_frame and not tags:
                logger.warning(
                    f"Scene {scene.index} has no meaningful content "
                    f"(no transcript, no informative frames, no tags)"
                )
            else:
                logger.info(
                    f"Scene {scene.index} has minimal searchable text but has other signals "
                    f"(transcript={has_meaningful_transcript}, frame={has_informative_frame}, "
                    f"tags={len(tags)})"
                )

        # Similarly for combined_text
        if len(combined_text.strip()) < 10:
            combined_text = search_text

        # Generate embedding using the search-optimized text
        embedding, embedding_metadata = SidecarBuilder._create_scene_embedding(
            search_text, scene.index
        )

        # Log processing stats for cost analysis
        logger.info(
            f"Scene {scene.index} stats: duration={stats.scene_duration_s:.1f}s, "
            f"transcript={stats.transcript_length} chars, "
            f"visual_called={stats.visual_analysis_called}, "
            f"search_text={stats.search_text_length} chars"
        )

        logger.info(f"Sidecar built for scene {scene.index}")

        return SceneSidecar(
            index=scene.index,
            start_s=scene.start_s,
            end_s=scene.end_s,
            transcript_segment=transcript_segment,
            visual_summary=visual_summary,
            combined_text=combined_text,
            embedding=embedding,
            thumbnail_url=thumbnail_url,
            visual_description=visual_description,
            visual_entities=visual_entities,
            visual_actions=visual_actions,
            tags=tags,
            # v2 fields
            sidecar_version=settings.sidecar_schema_version,
            search_text=search_text,
            embedding_metadata=embedding_metadata,
            needs_reprocess=False,
            processing_stats=stats.to_dict(),
        )

    @staticmethod
    def _extract_transcript_segment(
        full_transcript: str,
        scene: Scene,
        total_duration_s: float,
    ) -> str:
        """
        Extract transcript segment for a scene.

        This is a simple time-based slicing. Ideally we'd use word-level timestamps.

        Args:
            full_transcript: Full video transcript
            scene: Scene object
            total_duration_s: Total video duration in seconds

        Returns:
            Transcript segment for the scene
        """
        if not full_transcript:
            return ""

        # Calculate proportional character positions
        total_chars = len(full_transcript)
        start_ratio = scene.start_s / total_duration_s
        end_ratio = scene.end_s / total_duration_s

        start_char = int(start_ratio * total_chars)
        end_char = int(end_ratio * total_chars)

        # Extract segment and clean up
        segment = full_transcript[start_char:end_char].strip()

        # If segment is too short, expand it a bit
        if len(segment) < 50 and total_chars > 0:
            # Take a bit more context
            start_char = max(0, start_char - 50)
            end_char = min(total_chars, end_char + 50)
            segment = full_transcript[start_char:end_char].strip()

        return segment

    @staticmethod
    def _extract_keyframes(
        video_path: Path,
        scene: Scene,
        work_dir: Path,
    ) -> list[Path]:
        """
        Extract keyframes from a scene.

        Args:
            video_path: Path to video file
            scene: Scene object
            work_dir: Working directory for frames

        Returns:
            List of paths to extracted keyframe images
        """
        keyframe_paths = []
        scene_duration = scene.end_s - scene.start_s

        # Determine number of keyframes to extract
        num_keyframes = min(
            settings.max_keyframes_per_scene,
            max(1, int(scene_duration / 2)),  # At least one every 2 seconds
        )

        # Extract evenly spaced keyframes
        for i in range(num_keyframes):
            # Calculate timestamp
            if num_keyframes == 1:
                timestamp = scene.start_s + scene_duration / 2
            else:
                timestamp = scene.start_s + (scene_duration * i / (num_keyframes - 1))

            # Extract frame
            frame_path = work_dir / f"scene_{scene.index}_frame_{i}.jpg"
            try:
                ffmpeg.extract_frame(video_path, timestamp, frame_path)
                keyframe_paths.append(frame_path)
            except Exception as e:
                logger.warning(f"Failed to extract frame at {timestamp}s: {e}")

        logger.info(f"Extracted {len(keyframe_paths)} keyframes for scene {scene.index}")
        return keyframe_paths

    @staticmethod
    def _build_search_text(
        transcript: str,
        visual_description: str,
        language: str = "ko",
    ) -> str:
        """
        Build search-optimized text for embedding generation.

        This text is specifically optimized for semantic search:
        1. Transcript comes FIRST (higher semantic signal for most queries)
        2. Visual description supplements the transcript
        3. No metadata labels to avoid polluting the embedding space
        4. Intelligently truncated to respect model limits

        Args:
            transcript: Transcript segment
            visual_description: Visual description of the scene
            language: Language ('ko' or 'en')

        Returns:
            Search-optimized text for embedding
        """
        parts = []
        max_length = settings.search_text_max_length

        # Calculate target lengths based on weight
        # Transcript gets more space since it typically has higher signal
        transcript_target = int(max_length * settings.search_text_transcript_weight)
        visual_target = max_length - transcript_target

        # Add transcript first (primary search signal)
        if transcript and transcript.strip():
            truncated_transcript = transcript.strip()
            if len(truncated_transcript) > transcript_target:
                # Smart truncation: try to end at sentence boundary
                truncated_transcript = SidecarBuilder._smart_truncate(
                    truncated_transcript, transcript_target
                )
            parts.append(truncated_transcript)

        # Add visual description second (supplementary signal)
        if visual_description and visual_description.strip():
            truncated_visual = visual_description.strip()
            if len(truncated_visual) > visual_target:
                truncated_visual = SidecarBuilder._smart_truncate(
                    truncated_visual, visual_target
                )
            parts.append(truncated_visual)

        # Join with simple separator
        return " ".join(parts)

    @staticmethod
    def _smart_truncate(text: str, max_length: int) -> str:
        """
        Truncate text intelligently at sentence or word boundary.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text

        # Try to end at sentence boundary
        truncated = text[:max_length]

        # Look for sentence ending (., !, ?, 。)
        for punct in [". ", "! ", "? ", "。"]:
            last_punct = truncated.rfind(punct)
            if last_punct > max_length * 0.5:  # Only if we keep at least 50%
                return truncated[:last_punct + 1].strip()

        # Fall back to word boundary
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.7:  # Only if we keep at least 70%
            return truncated[:last_space].strip() + "..."

        return truncated + "..."

    @staticmethod
    def _build_combined_text(
        visual_summary: str,
        transcript: str,
        language: str = "ko",
        video_filename: Optional[str] = None,
    ) -> str:
        """
        Build combined text for backward compatibility.

        This method is kept for backward compatibility with existing consumers.
        For new search functionality, prefer using search_text which is
        specifically optimized for embedding generation.

        Args:
            visual_summary: Visual description of the scene
            transcript: Transcript segment
            language: Language for the labels ('ko' or 'en')
            video_filename: Optional video filename for metadata inclusion

        Returns:
            Combined text for embedding
        """
        parts = []

        # Language-specific labels
        labels = {
            "ko": {"visual": "시각", "audio": "오디오", "metadata": "메타데이터", "filename": "파일명"},
            "en": {"visual": "Visual", "audio": "Audio", "metadata": "Metadata", "filename": "Filename"},
        }
        lang_labels = labels.get(language, labels["ko"])

        # Audio/transcript first for search optimization (higher signal)
        if transcript:
            parts.append(f"{lang_labels['audio']}: {transcript}")

        # Visual second
        if visual_summary:
            parts.append(f"{lang_labels['visual']}: {visual_summary}")

        # Add metadata section with filename last
        if video_filename:
            parts.append(f"{lang_labels['metadata']}: {lang_labels['filename']}: {video_filename}")

        combined = " | ".join(parts)

        # Truncate if too long (embedding models have limits)
        max_length = settings.search_text_max_length
        if len(combined) > max_length:
            combined = combined[:max_length] + "..."

        return combined


# Global sidecar builder instance
sidecar_builder = SidecarBuilder()
