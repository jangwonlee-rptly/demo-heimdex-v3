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
from .frame_quality import FrameQualityChecker
from ..adapters.clip_embedder import ClipEmbedder
from ..adapters import clip_inference

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
    created_at: Optional[str] = None  # ISO 8601 timestamp
    language: Optional[str] = None  # Language of input text

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "model": self.model,
            "dimensions": self.dimensions,
            "input_text_hash": self.input_text_hash,
            "input_text_length": self.input_text_length,
        }
        if self.created_at:
            result["created_at"] = self.created_at
        if self.language:
            result["language"] = self.language
        return result


@dataclass
class MultiEmbeddingMetadata:
    """
    Per-channel embedding metadata for v3-multi schema.

    Tracks metadata for each embedding channel independently:
    - transcript: embedding of transcript_segment only
    - visual: embedding of visual_description + tags
    - summary: embedding of scene/video summary (optional)
    """
    transcript: Optional[EmbeddingMetadata] = None
    visual: Optional[EmbeddingMetadata] = None
    summary: Optional[EmbeddingMetadata] = None
    legacy: Optional[EmbeddingMetadata] = None  # Original single embedding for backward compat

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {"channels": {}}
        if self.transcript:
            result["channels"]["transcript"] = self.transcript.to_dict()
        if self.visual:
            result["channels"]["visual"] = self.visual.to_dict()
        if self.summary:
            result["channels"]["summary"] = self.summary.to_dict()
        if self.legacy:
            result["legacy"] = self.legacy.to_dict()
        return result


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
        # New v3-multi fields for per-channel embeddings
        embedding_transcript: Optional[list[float]] = None,
        embedding_visual: Optional[list[float]] = None,
        embedding_summary: Optional[list[float]] = None,
        embedding_version: Optional[str] = None,
        multi_embedding_metadata: Optional[MultiEmbeddingMetadata] = None,
        # CLIP visual embedding fields
        embedding_visual_clip: Optional[list[float]] = None,
        visual_clip_metadata: Optional[dict] = None,
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

        # v3-multi fields for per-channel embeddings
        self.embedding_transcript = embedding_transcript
        self.embedding_visual = embedding_visual
        self.embedding_summary = embedding_summary
        self.embedding_version = embedding_version
        self.multi_embedding_metadata = multi_embedding_metadata

        # CLIP visual embedding fields
        self.embedding_visual_clip = embedding_visual_clip
        self.visual_clip_metadata = visual_clip_metadata

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

    def __init__(self, storage, ffmpeg, openai, clip_embedder, settings):
        """Initialize SidecarBuilder with injected dependencies.

        Args:
            storage: Supabase storage adapter
            ffmpeg: FFmpeg adapter
            openai: OpenAI client
            clip_embedder: CLIP embedder (optional)
            settings: Settings object
        """
        self.storage = storage
        self.ffmpeg = ffmpeg
        self.openai = openai
        self.clip_embedder = clip_embedder
        self.settings = settings
        # Create FrameQualityChecker with settings
        self.frame_quality_checker = FrameQualityChecker(settings)

    def _normalize_tags(self, entities: list[str], actions: list[str]) -> list[str]:
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

    def _assess_scene_meaningfulness(
        self,
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

    def _should_skip_visual_analysis(
        self,
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
        if not self.settings.visual_semantics_enabled:
            return True, "visual_semantics_disabled"

        # If no transcript, we need visual analysis for search signal
        if self.settings.visual_semantics_force_on_no_transcript and not has_meaningful_transcript:
            return False, None

        # Short scene with rich transcript - transcript is sufficient
        is_short_scene = scene_duration_s < self.settings.visual_semantics_min_duration_s
        has_rich_transcript = transcript_length >= self.settings.visual_semantics_transcript_threshold

        if is_short_scene and has_rich_transcript:
            return True, f"short_scene_rich_transcript (duration={scene_duration_s:.1f}s < {self.settings.visual_semantics_min_duration_s}s, transcript={transcript_length} chars)"

        return False, None

    def _create_scene_embedding(
        self,
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
        embedding = self.openai.create_embedding(text)

        # Create metadata for tracking
        metadata = EmbeddingMetadata(
            model=self.settings.embedding_model,
            dimensions=self.settings.embedding_dimensions,
            input_text_hash=text_hash,
            input_text_length=len(text),
        )

        logger.debug(
            f"Scene {scene_index} embedding: model={metadata.model}, "
            f"text_length={metadata.input_text_length}, hash={metadata.input_text_hash}"
        )

        return embedding, metadata

    def _create_embedding_with_retry(
        self,
        text: str,
        channel_name: str,
        scene_index: int,
        language: str,
        max_retries: Optional[int] = None,
    ) -> tuple[Optional[list[float]], Optional[EmbeddingMetadata]]:
        """
        Create embedding with retry logic and safety checks.

        Safety rules:
        1. If text is empty/whitespace → return (None, None)
        2. Retry on transient failures with exponential backoff
        3. Return None on permanent failures (log error)

        Args:
            text: Text to embed
            channel_name: Channel name for logging (transcript, visual, summary)
            scene_index: Scene index for logging
            language: Language code
            max_retries: Max retry attempts (defaults to config value)

        Returns:
            Tuple of (embedding vector or None, metadata or None)
        """
        from datetime import datetime
        import time

        # Safety: empty text → NULL embedding (do NOT synthesize fake content)
        if not text or not text.strip():
            logger.debug(
                f"Scene {scene_index} {channel_name} channel: empty text, skipping embedding"
            )
            return None, None

        # Truncate to max length for this channel (already should be done, but double-check)
        text = text.strip()

        if max_retries is None:
            max_retries = self.settings.embedding_max_retries

        # Compute hash for cache lookup
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        # Retry loop with exponential backoff
        for attempt in range(max_retries):
            try:
                # Generate embedding
                embedding = self.openai.create_embedding(text)

                # Create metadata
                metadata = EmbeddingMetadata(
                    model=self.settings.embedding_model,
                    dimensions=self.settings.embedding_dimensions,
                    input_text_hash=text_hash,
                    input_text_length=len(text),
                    created_at=datetime.utcnow().isoformat() + "Z",
                    language=language,
                )

                logger.debug(
                    f"Scene {scene_index} {channel_name} embedding: "
                    f"length={len(text)}, hash={text_hash[:8]}..."
                )

                return embedding, metadata

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = self.settings.embedding_retry_delay_s * (2 ** attempt)
                    logger.warning(
                        f"Scene {scene_index} {channel_name} embedding failed "
                        f"(attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Scene {scene_index} {channel_name} embedding failed "
                        f"after {max_retries} attempts: {e}. Returning NULL."
                    )
                    return None, None

        return None, None

    
    def _create_multi_channel_embeddings(
        self,
        transcript_segment: str,
        visual_description: str,
        tags: list[str],
        summary: Optional[str],
        scene_index: int,
        language: str,
    ) -> tuple[
        Optional[list[float]],
        Optional[list[float]],
        Optional[list[float]],
        MultiEmbeddingMetadata,
    ]:
        """
        Generate per-channel embeddings for v3-multi schema.

        Channel definitions:
        1. Transcript channel: transcript_segment only (clean ASR signal)
        2. Visual channel: visual_description + tags (space-joined)
        3. Summary channel: scene/video summary (optional, currently disabled)

        Safety:
        - Empty channels → NULL embedding (no fake content)
        - Per-channel max length enforcement
        - Independent retry per channel

        Args:
            transcript_segment: Transcript text
            visual_description: Visual description text
            tags: List of tags
            summary: Optional summary text
            scene_index: Scene index for logging
            language: Language code

        Returns:
            Tuple of (emb_transcript, emb_visual, emb_summary, multi_metadata)
        """
        multi_metadata = MultiEmbeddingMetadata()

        # Channel 1: Transcript
        transcript_text = (transcript_segment or "").strip()
        if len(transcript_text) > self.settings.embedding_transcript_max_length:
            transcript_text = self._smart_truncate(
                transcript_text, self.settings.embedding_transcript_max_length
            )

        emb_transcript, meta_transcript = self._create_embedding_with_retry(
            transcript_text, "transcript", scene_index, language
        )
        if meta_transcript:
            multi_metadata.transcript = meta_transcript

        # Channel 2: Visual (visual_description + tags)
        visual_parts = []
        if visual_description and visual_description.strip():
            visual_parts.append(visual_description.strip())

        if self.settings.embedding_visual_include_tags and tags:
            # Deduplicate tags and join
            unique_tags = list(dict.fromkeys(tags))  # Preserve order, remove dupes
            tags_text = " ".join(unique_tags)
            if tags_text:
                visual_parts.append(tags_text)

        visual_text = " ".join(visual_parts)
        if len(visual_text) > self.settings.embedding_visual_max_length:
            visual_text = self._smart_truncate(
                visual_text, self.settings.embedding_visual_max_length
            )

        emb_visual, meta_visual = self._create_embedding_with_retry(
            visual_text, "visual", scene_index, language
        )
        if meta_visual:
            multi_metadata.visual = meta_visual

        # Channel 3: Summary (optional, currently disabled by default)
        emb_summary = None
        if self.settings.embedding_summary_enabled and summary and summary.strip():
            summary_text = summary.strip()
            if len(summary_text) > self.settings.embedding_summary_max_length:
                summary_text = self._smart_truncate(
                    summary_text, self.settings.embedding_summary_max_length
                )

            emb_summary, meta_summary = self._create_embedding_with_retry(
                summary_text, "summary", scene_index, language
            )
            if meta_summary:
                multi_metadata.summary = meta_summary

        return emb_transcript, emb_visual, emb_summary, multi_metadata

    def build_sidecar(
        self,
        scene: Scene,
        video_path: Path,
        full_transcript: str,
        video_id: UUID,
        owner_id: UUID,
        work_dir: Path,
        language: str = "ko",
        video_duration_s: Optional[float] = None,
        video_filename: Optional[str] = None,
        transcript_segments: Optional[list] = None,
    ) -> SceneSidecar:
        """
        Build a complete sidecar for a scene with optimized visual semantics.

        This method implements:
        1. Frame quality pre-filtering to avoid OpenAI calls for bad frames
        2. Transcript-first strategy (prefer ASR over weak visuals)
        3. Strict JSON schema prompts for token efficiency
        4. Configurable visual semantics processing
        5. Cost-optimized visual analysis skipping
        6. Timestamp-aligned transcript extraction when segments available

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
            transcript_segments: Optional list of Whisper segments with timestamps

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

        # Extract transcript segment using timestamp-aligned method if available
        if transcript_segments:
            logger.debug(
                f"Using timestamp-aligned transcript extraction for scene {scene.index}"
            )
            transcript_segment = self._extract_transcript_segment_from_segments(
                segments=transcript_segments,
                scene_start_s=scene.start_s,
                scene_end_s=scene.end_s,
                video_duration_s=video_duration_s,
            )
        else:
            logger.debug(
                f"Falling back to proportional transcript extraction for scene {scene.index}"
            )
            transcript_segment = self._extract_transcript_segment(
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
        thumbnail_storage_path = None  # Will be set when keyframes are extracted

        # Initialize CLIP visual embedding fields
        embedding_visual_clip = None
        visual_clip_metadata = None

        # Determine if we should skip visual analysis (cost optimization)
        should_skip_visuals, skip_reason = self._should_skip_visual_analysis(
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
            keyframe_paths = self._extract_keyframes(
                video_path, scene, work_dir
            )
            stats.keyframes_extracted = len(keyframe_paths)

            if keyframe_paths:
                # Rank frames by quality (best first)
                ranked_frames = self.frame_quality_checker.rank_frames_by_quality(keyframe_paths)
                stats.best_frame_found = len(ranked_frames) > 0

                if ranked_frames:
                    # Try frames in order of quality until we get meaningful content
                    max_attempts = min(
                        len(ranked_frames),
                        self.settings.visual_semantics_max_frame_retries
                    )
                    best_frame_path = ranked_frames[0][0]  # Keep best for thumbnail

                    # Define thumbnail storage path early for CLIP embedding
                    thumbnail_storage_path = (
                        f"{owner_id}/{video_id}/thumbnails/scene_{scene.index}.jpg"
                    )

                    # Generate CLIP visual embedding from best frame (if enabled)
                    if self.settings.clip_enabled and best_frame_path:
                        logger.info(
                            f"Scene {scene.index}: Generating CLIP embedding from best frame "
                            f"(backend={self.settings.clip_inference_backend})"
                        )
                        try:
                            # Route to appropriate backend
                            if self.settings.clip_inference_backend in ("runpod", "runpod_pod", "runpod_serverless"):
                                # RunPod GPU backend: upload thumbnail first, then call endpoint
                                embedding_visual_clip, visual_clip_metadata = self._generate_clip_embedding_runpod(
                                    best_frame_path=best_frame_path,
                                    thumbnail_storage_path=thumbnail_storage_path,
                                    scene_index=scene.index,
                                    frame_quality_score=ranked_frames[0][1],
                                )
                            elif self.settings.clip_inference_backend == "local":
                                # Local CPU backend: existing ClipEmbedder
                                embedding_visual_clip, visual_clip_metadata = self._generate_clip_embedding_local(
                                    best_frame_path=best_frame_path,
                                    scene_index=scene.index,
                                    frame_quality_score=ranked_frames[0][1],
                                )
                            elif self.settings.clip_inference_backend == "off":
                                logger.info(f"Scene {scene.index}: CLIP inference disabled (backend=off)")
                                embedding_visual_clip = None
                                visual_clip_metadata = None
                            else:
                                logger.warning(
                                    f"Scene {scene.index}: Unknown CLIP backend '{self.settings.clip_inference_backend}', "
                                    f"falling back to local"
                                )
                                embedding_visual_clip, visual_clip_metadata = self._generate_clip_embedding_local(
                                    best_frame_path=best_frame_path,
                                    scene_index=scene.index,
                                    frame_quality_score=ranked_frames[0][1],
                                )

                            if embedding_visual_clip:
                                logger.info(
                                    f"Scene {scene.index}: CLIP embedding created "
                                    f"(dim={len(embedding_visual_clip)}, "
                                    f"time={visual_clip_metadata.get('inference_time_ms', 0) if visual_clip_metadata else 'N/A'}ms)"
                                )
                            elif visual_clip_metadata and visual_clip_metadata.get("error"):
                                logger.warning(
                                    f"Scene {scene.index}: CLIP embedding failed: {visual_clip_metadata['error']}"
                                )
                        except Exception as e:
                            logger.error(
                                f"Scene {scene.index}: Unexpected CLIP error: {e}",
                                exc_info=True
                            )
                            # Continue processing - CLIP failure should not break pipeline
                            visual_clip_metadata = {
                                "error": str(e),
                                "backend": self.settings.clip_inference_backend,
                            }

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
                        visual_result = self.openai.analyze_scene_visuals_optimized(
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
                            if not self.settings.visual_semantics_retry_on_no_content or attempt >= max_attempts - 1:
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
                        if self.settings.visual_semantics_include_entities:
                            visual_entities = visual_result.get("main_entities", [])
                            logger.info(f"Extracted {len(visual_entities)} entities")

                        if self.settings.visual_semantics_include_actions:
                            visual_actions = visual_result.get("actions", [])
                            logger.info(f"Extracted {len(visual_actions)} actions")

                        # Normalize tags from entities and actions
                        tags = self._normalize_tags(visual_entities, visual_actions)
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
                # thumbnail_storage_path already defined above (line 773)
                thumbnail_url = self.storage.upload_file(
                    thumbnail_frame,
                    thumbnail_storage_path,
                    content_type="image/jpeg",
                )
            else:
                logger.warning(f"No keyframes extracted for scene {scene.index}")
                stats.visual_analysis_skipped_reason = "no_keyframes"
        else:
            # Still extract thumbnail even if skipping visual analysis
            keyframe_paths = self._extract_keyframes(
                video_path, scene, work_dir
            )
            stats.keyframes_extracted = len(keyframe_paths)
            if keyframe_paths:
                thumbnail_frame = keyframe_paths[0]
                thumbnail_storage_path = (
                    f"{owner_id}/{video_id}/thumbnails/scene_{scene.index}.jpg"
                )
                thumbnail_url = self.storage.upload_file(
                    thumbnail_frame,
                    thumbnail_storage_path,
                    content_type="image/jpeg",
                )

        # Assess scene meaningfulness and enhance visual description if needed
        # This ensures scenes with ANY visual signal get meaningful descriptions
        has_informative_frame = best_frame_path is not None
        enhanced_visual_description = self._assess_scene_meaningfulness(
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
        search_text = self._build_search_text(
            transcript_segment,
            visual_description or visual_summary,
            language=language,
        )
        stats.search_text_length = len(search_text)

        # Build combined text for backward compatibility (includes metadata)
        combined_text = self._build_combined_text(
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

        # Generate embedding using the search-optimized text (legacy single embedding)
        embedding, embedding_metadata = self._create_scene_embedding(
            search_text, scene.index
        )

        # Generate multi-channel embeddings if enabled (v3-multi)
        embedding_transcript = None
        embedding_visual = None
        embedding_summary = None
        multi_embedding_metadata = None
        embedding_version_value = None

        if self.settings.multi_embedding_enabled:
            logger.info(f"Scene {scene.index}: Generating multi-channel embeddings")
            (
                embedding_transcript,
                embedding_visual,
                embedding_summary,
                multi_embedding_metadata,
            ) = self._create_multi_channel_embeddings(
                transcript_segment=transcript_segment,
                visual_description=visual_description or "",
                tags=tags,
                summary=None,  # Summary field not yet implemented
                scene_index=scene.index,
                language=language,
            )

            # Store legacy embedding metadata in multi_embedding_metadata
            if multi_embedding_metadata and embedding_metadata:
                multi_embedding_metadata.legacy = embedding_metadata

            embedding_version_value = self.settings.embedding_version

            logger.info(
                f"Scene {scene.index} multi-embeddings: "
                f"transcript={'✓' if embedding_transcript else '✗'}, "
                f"visual={'✓' if embedding_visual else '✗'}, "
                f"summary={'✓' if embedding_summary else '✗'}"
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
            sidecar_version=self.settings.sidecar_schema_version,
            search_text=search_text,
            embedding_metadata=embedding_metadata,
            needs_reprocess=False,
            processing_stats=stats.to_dict(),
            # v3-multi fields
            embedding_transcript=embedding_transcript,
            embedding_visual=embedding_visual,
            embedding_summary=embedding_summary,
            embedding_version=embedding_version_value,
            multi_embedding_metadata=multi_embedding_metadata,
            # CLIP visual embedding fields
            embedding_visual_clip=embedding_visual_clip,
            visual_clip_metadata=visual_clip_metadata,
        )

    def _extract_transcript_segment_from_segments(
        self,
        segments: list,
        scene_start_s: float,
        scene_end_s: float,
        video_duration_s: float,
        context_pad_s: float = 3.0,
        min_chars: int = 200,
    ) -> str:
        """
        Extract transcript segment using Whisper's timestamp-aligned segments.

        This is the preferred method as it uses actual word-level timestamps
        from Whisper rather than assuming uniform speech rate.

        Args:
            segments: List of segment dicts with 'start', 'end', 'text' keys
            scene_start_s: Scene start time in seconds
            scene_end_s: Scene end time in seconds
            video_duration_s: Total video duration in seconds
            context_pad_s: Seconds to expand window if segment is too short
            min_chars: Minimum character count before expanding context

        Returns:
            Transcript segment for the scene (timestamp-aligned)
        """
        if not segments:
            return ""

        # Sort segments by start time (defensive - they should already be sorted)
        # Handle both dict and object formats (for backward compatibility)
        sorted_segments = sorted(
            segments,
            key=lambda s: s.get("start", 0.0) if isinstance(s, dict) else getattr(s, "start", 0.0)
        )

        def get_text_for_window(start: float, end: float) -> str:
            """Helper to extract text for a time window."""
            matching_segs = []
            for seg in sorted_segments:
                # Handle both dict and object formats
                if isinstance(seg, dict):
                    seg_start = seg.get("start", 0.0)
                    seg_end = seg.get("end", 0.0)
                    seg_text = seg.get("text", "")
                else:
                    seg_start = getattr(seg, "start", 0.0)
                    seg_end = getattr(seg, "end", 0.0)
                    seg_text = getattr(seg, "text", "")

                # Include segment if it overlaps with the window
                # Use strict inequalities to exclude segments that just touch at boundaries
                if seg_end > start and seg_start < end:
                    matching_segs.append(seg_text)

            # Join and normalize whitespace
            text = " ".join(matching_segs)
            text = " ".join(text.split())  # Normalize whitespace
            return text.strip()

        # Initial extraction for scene time window
        text = get_text_for_window(scene_start_s, scene_end_s)

        # If too short, expand the window with context padding
        if len(text) < min_chars:
            expanded_start = max(0.0, scene_start_s - context_pad_s)
            expanded_end = min(video_duration_s, scene_end_s + context_pad_s)
            text = get_text_for_window(expanded_start, expanded_end)

        return text

    def _extract_transcript_segment(
        self,
        full_transcript: str,
        scene: Scene,
        total_duration_s: float,
    ) -> str:
        """
        Extract transcript segment for a scene using proportional character slicing.

        DEPRECATED: This is a fallback method for videos without timestamp segments.
        Use _extract_transcript_segment_from_segments() when segments are available.

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

    def _extract_keyframes(
        self,
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
            self.settings.max_keyframes_per_scene,
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
                self.ffmpeg.extract_frame(video_path, timestamp, frame_path)
                keyframe_paths.append(frame_path)
            except Exception as e:
                logger.warning(f"Failed to extract frame at {timestamp}s: {e}")

        logger.info(f"Extracted {len(keyframe_paths)} keyframes for scene {scene.index}")
        return keyframe_paths

    def _build_search_text(
        self,
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
        max_length = self.settings.search_text_max_length

        # Calculate target lengths based on weight
        # Transcript gets more space since it typically has higher signal
        transcript_target = int(max_length * self.settings.search_text_transcript_weight)
        visual_target = max_length - transcript_target

        # Add transcript first (primary search signal)
        if transcript and transcript.strip():
            truncated_transcript = transcript.strip()
            if len(truncated_transcript) > transcript_target:
                # Smart truncation: try to end at sentence boundary
                truncated_transcript = self._smart_truncate(
                    truncated_transcript, transcript_target
                )
            parts.append(truncated_transcript)

        # Add visual description second (supplementary signal)
        if visual_description and visual_description.strip():
            truncated_visual = visual_description.strip()
            if len(truncated_visual) > visual_target:
                truncated_visual = self._smart_truncate(
                    truncated_visual, visual_target
                )
            parts.append(truncated_visual)

        # Join with simple separator
        return " ".join(parts)

    def _smart_truncate(self, text: str, max_length: int) -> str:
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

    def _build_combined_text(
        self,
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
        max_length = self.settings.search_text_max_length
        if len(combined) > max_length:
            combined = combined[:max_length] + "..."

        return combined

    def _generate_clip_embedding_runpod(
        self,
        best_frame_path: str,
        thumbnail_storage_path: str,
        scene_index: int,
        frame_quality_score: float,
    ) -> tuple[Optional[list[float]], Optional[dict]]:
        """
        Generate CLIP embedding using RunPod GPU backend.

        Args:
            best_frame_path: Local path to the best quality frame
            thumbnail_storage_path: Storage path where thumbnail will be uploaded
            scene_index: Scene index for logging
            frame_quality_score: Quality score of the frame

        Returns:
            Tuple of (embedding_list, metadata_dict)
        """
        import time
        from ..adapters import clip_inference

        start_time = time.time()

        try:
            # Step 1: Upload thumbnail to storage (if not already uploaded)
            logger.debug(f"Scene {scene_index}: Uploading thumbnail to {thumbnail_storage_path}")
            public_url = self.storage.upload_file(
                Path(best_frame_path),
                thumbnail_storage_path,
                content_type="image/jpeg",
            )

            # Step 2: Generate signed URL for RunPod (short-lived, more secure than public URL)
            logger.debug(f"Scene {scene_index}: Creating signed URL for RunPod access")
            signed_url = self.storage.create_signed_url(
                thumbnail_storage_path,
                expires_in=300,  # 5 minutes - enough for RunPod to download
            )

            # Step 3: Call RunPod CLIP endpoint
            request_id = f"scene-{scene_index}"
            logger.info(
                f"🎬 Scene {scene_index}: Calling RunPod GPU for CLIP embedding "
                f"(backend={self.settings.clip_inference_backend})"
            )

            result = clip_inference.embed_image_url(
                image_url=signed_url,
                request_id=request_id,
            )

            # Step 4: Extract embedding and metadata
            embedding = result.get("embedding")
            if not embedding:
                error_msg = "No embedding in RunPod response"
                logger.error(f"Scene {scene_index}: {error_msg}")
                return None, {"error": error_msg, "backend": "runpod"}

            # Build metadata
            total_time_ms = (time.time() - start_time) * 1000
            runpod_timings = result.get("timings", {})

            metadata = {
                "model_name": result.get("model", "ViT-B-32"),
                "pretrained": result.get("pretrained", "openai"),
                "embed_dim": result.get("dim", len(embedding)),
                "normalized": result.get("normalized", True),
                "device": "gpu",  # RunPod uses GPU
                "backend": "runpod",
                "frame_path": str(best_frame_path),  # Convert PosixPath to string
                "frame_quality": {"quality_score": frame_quality_score},
                "inference_time_ms": runpod_timings.get("inference_ms", 0),
                "download_time_ms": runpod_timings.get("download_ms", 0),
                "total_time_ms": round(total_time_ms, 2),
                "created_at": result.get("created_at", ""),
                "error": None,
            }

            logger.info(
                f"✅ Scene {scene_index}: RunPod GPU embedding complete! "
                f"device={metadata.get('device', 'gpu')}, "
                f"dim={len(embedding)}, "
                f"inference={metadata['inference_time_ms']:.1f}ms, "
                f"total={metadata['total_time_ms']:.1f}ms"
            )

            return embedding, metadata

        except clip_inference.ClipInferenceAuthError as e:
            logger.error(f"Scene {scene_index}: RunPod authentication error: {e}")
            return None, {
                "error": f"Authentication error: {e}",
                "backend": "runpod",
                "inference_time_ms": 0,
            }
        except clip_inference.ClipInferenceTimeoutError as e:
            logger.error(f"Scene {scene_index}: RunPod timeout: {e}")
            return None, {
                "error": f"Timeout: {e}",
                "backend": "runpod",
                "inference_time_ms": 0,
            }
        except clip_inference.ClipInferenceError as e:
            logger.error(f"Scene {scene_index}: RunPod inference error: {e}")
            return None, {
                "error": f"Inference error: {e}",
                "backend": "runpod",
                "inference_time_ms": 0,
            }
        except Exception as e:
            logger.error(f"Scene {scene_index}: Unexpected RunPod error: {e}", exc_info=True)
            return None, {
                "error": f"Unexpected error: {e}",
                "backend": "runpod",
                "inference_time_ms": 0,
            }

    def _generate_clip_embedding_local(
        self,
        best_frame_path: str,
        scene_index: int,
        frame_quality_score: float,
    ) -> tuple[Optional[list[float]], Optional[dict]]:
        """
        Generate CLIP embedding using local CPU backend (existing ClipEmbedder).

        Args:
            best_frame_path: Local path to the best quality frame
            scene_index: Scene index for logging
            frame_quality_score: Quality score of the frame

        Returns:
            Tuple of (embedding_list, metadata_dict)
        """
        try:
            best_frame_quality = {
                "quality_score": frame_quality_score,
            }
            embedding_visual_clip, clip_metadata_obj = self.clip_embedder.create_visual_embedding(
                image_path=Path(best_frame_path),
                quality_info=best_frame_quality,
                timeout_s=self.settings.clip_timeout_s,
            )

            if clip_metadata_obj:
                visual_clip_metadata = clip_metadata_obj.to_dict()
                # Add backend info
                visual_clip_metadata["backend"] = "local"
            else:
                visual_clip_metadata = None

            return embedding_visual_clip, visual_clip_metadata

        except Exception as e:
            logger.error(f"Scene {scene_index}: Local CLIP error: {e}", exc_info=True)
            return None, {
                "error": str(e),
                "backend": "local",
                "inference_time_ms": 0,
            }


# SidecarBuilder instances should be created with injected dependencies
# No module-level singleton - use dependency injection instead
