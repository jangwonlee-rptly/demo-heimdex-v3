"""Sidecar builder for scene metadata."""
import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

from .scene_detector import Scene
from ..adapters.openai_client import openai_client
from ..adapters.ffmpeg import ffmpeg
from ..adapters.supabase import storage
from ..config import settings

logger = logging.getLogger(__name__)


class SceneSidecar:
    """Scene sidecar metadata."""

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
    ):
        self.index = index
        self.start_s = start_s
        self.end_s = end_s
        self.transcript_segment = transcript_segment
        self.visual_summary = visual_summary
        self.combined_text = combined_text
        self.embedding = embedding
        self.thumbnail_url = thumbnail_url


class SidecarBuilder:
    """Builds scene sidecars with transcripts, visuals, and embeddings."""

    @staticmethod
    def build_sidecar(
        scene: Scene,
        video_path: Path,
        full_transcript: str,
        video_id: UUID,
        owner_id: UUID,
        work_dir: Path,
        language: str = "ko",
    ) -> SceneSidecar:
        """
        Build a complete sidecar for a scene.

        Args:
            scene: Scene object with time boundaries
            video_path: Path to video file
            full_transcript: Full video transcript
            video_id: Video ID for thumbnail path
            owner_id: Owner ID for thumbnail path
            work_dir: Working directory for temporary files
            language: Language for summaries and embeddings ('ko' or 'en')

        Returns:
            SceneSidecar object
        """
        logger.info(f"Building sidecar for {scene} in language: {language}")

        # Extract transcript segment (simple time-based slicing)
        # This is a rough approximation - ideally we'd use word-level timestamps
        transcript_segment = SidecarBuilder._extract_transcript_segment(
            full_transcript, scene, 60.0  # Assume 60s total duration for now
        )

        # Extract keyframes
        keyframe_paths = SidecarBuilder._extract_keyframes(
            video_path, scene, work_dir
        )

        # Analyze visuals with GPT-4o in the specified language
        visual_summary = openai_client.analyze_scene_visuals(
            keyframe_paths, transcript_segment, language=language
        )

        # Build combined text for embedding in the specified language
        combined_text = SidecarBuilder._build_combined_text(
            visual_summary, transcript_segment, language=language
        )

        # Generate embedding
        embedding = openai_client.create_embedding(combined_text)

        # Upload thumbnail (first keyframe)
        thumbnail_url = None
        if keyframe_paths:
            thumbnail_storage_path = (
                f"{owner_id}/{video_id}/thumbnails/scene_{scene.index}.jpg"
            )
            thumbnail_url = storage.upload_file(
                keyframe_paths[0],
                thumbnail_storage_path,
                content_type="image/jpeg",
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
    def _build_combined_text(visual_summary: str, transcript: str, language: str = "ko") -> str:
        """
        Build combined text optimized for search.

        Args:
            visual_summary: Visual description of the scene
            transcript: Transcript segment
            language: Language for the labels ('ko' or 'en')

        Returns:
            Combined text for embedding
        """
        parts = []

        # Language-specific labels
        labels = {
            "ko": {"visual": "시각", "audio": "오디오"},
            "en": {"visual": "Visual", "audio": "Audio"},
        }
        lang_labels = labels.get(language, labels["ko"])

        if visual_summary:
            parts.append(f"{lang_labels['visual']}: {visual_summary}")

        if transcript:
            parts.append(f"{lang_labels['audio']}: {transcript}")

        combined = " | ".join(parts)

        # Truncate if too long (embedding models have limits)
        max_length = 8000
        if len(combined) > max_length:
            combined = combined[:max_length] + "..."

        return combined


# Global sidecar builder instance
sidecar_builder = SidecarBuilder()
