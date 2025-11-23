"""Scene detection using PySceneDetect with configurable detectors.

This module provides scene detection functionality with support for multiple
detection strategies:
- AdaptiveDetector (default): Better for videos with varying content
- ContentDetector: Traditional content-based detection

The detector strategy is configurable via environment variables.
"""
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from scenedetect import detect, VideoStream
from scenedetect.detectors import AdaptiveDetector, ContentDetector
from scenedetect.scene_detector import SceneDetector as PySceneDetector

from ..config import settings

logger = logging.getLogger(__name__)


class SceneDetectionStrategy(str, Enum):
    """Supported scene detection strategies."""

    ADAPTIVE = "adaptive"
    CONTENT = "content"


class Scene:
    """Represents a detected scene."""

    def __init__(self, index: int, start_s: float, end_s: float):
        """Initialize Scene.

        Args:
            index: The scene index (0-based).
            start_s: Start time in seconds.
            end_s: End time in seconds.
        """
        self.index = index
        self.start_s = start_s
        self.end_s = end_s

    def __repr__(self):
        """Return a string representation of the Scene."""
        return f"Scene({self.index}, {self.start_s:.2f}s-{self.end_s:.2f}s)"


def get_scene_detector(fps: float = 30.0) -> PySceneDetector:
    """
    Factory function to create a scene detector based on configuration.

    Args:
        fps: Video frame rate (used to convert min_scene_len from seconds to frames)

    Returns:
        Configured PySceneDetect detector instance

    Raises:
        ValueError: If an unknown detector strategy is specified
    """
    strategy = settings.scene_detector.lower()

    # Calculate minimum scene length in frames
    min_scene_len_frames = max(1, int(round(settings.scene_min_len_seconds * fps)))

    if strategy == SceneDetectionStrategy.ADAPTIVE:
        logger.info(
            f"Creating AdaptiveDetector with threshold={settings.scene_adaptive_threshold}, "
            f"window_width={settings.scene_adaptive_window_width}, "
            f"min_content_val={settings.scene_adaptive_min_content_val}, "
            f"min_scene_len={min_scene_len_frames} frames ({settings.scene_min_len_seconds}s)"
        )
        return AdaptiveDetector(
            adaptive_threshold=settings.scene_adaptive_threshold,
            window_width=settings.scene_adaptive_window_width,
            min_content_val=settings.scene_adaptive_min_content_val,
            min_scene_len=min_scene_len_frames,
        )

    elif strategy == SceneDetectionStrategy.CONTENT:
        logger.info(
            f"Creating ContentDetector with threshold={settings.scene_content_threshold}, "
            f"min_scene_len={min_scene_len_frames} frames ({settings.scene_min_len_seconds}s)"
        )
        return ContentDetector(
            threshold=settings.scene_content_threshold,
            min_scene_len=min_scene_len_frames,
        )

    else:
        logger.warning(
            f"Unknown scene detector strategy '{strategy}', falling back to AdaptiveDetector"
        )
        return AdaptiveDetector(
            adaptive_threshold=settings.scene_adaptive_threshold,
            window_width=settings.scene_adaptive_window_width,
            min_content_val=settings.scene_adaptive_min_content_val,
            min_scene_len=min_scene_len_frames,
        )


class SceneDetector:
    """Scene detection handler using configurable detection strategies."""

    @staticmethod
    def detect_scenes(
        video_path: Path,
        video_duration_s: Optional[float] = None,
        fps: Optional[float] = None,
    ) -> list[Scene]:
        """
        Detect scenes in a video using the configured detection strategy.

        This method uses the detector specified in settings.scene_detector:
        - "adaptive" (default): Uses AdaptiveDetector for better handling of varying content
        - "content": Uses ContentDetector for traditional content-based detection

        Args:
            video_path: Path to video file
            video_duration_s: Optional video duration in seconds. If provided and no scenes
                            are detected, this will be used for the fallback scene.
                            If not provided, defaults to 60 seconds.
            fps: Optional video frame rate. If not provided, uses a default of 30.0 fps
                for detector configuration. PySceneDetect will automatically determine
                the actual FPS from the video file.

        Returns:
            List of Scene objects

        Raises:
            Exception: If scene detection fails
        """
        logger.info(
            f"Detecting scenes in {video_path} using '{settings.scene_detector}' detector"
        )

        # Use provided FPS or default to 30.0
        # This is used for min_scene_len calculation in the detector
        # PySceneDetect will determine the actual FPS from the video
        effective_fps = fps if fps is not None else 30.0

        # Create detector using factory
        detector = get_scene_detector(fps=effective_fps)

        # Use PySceneDetect to find scene boundaries
        scene_list = detect(str(video_path), detector)

        if not scene_list:
            logger.warning("No scenes detected, treating entire video as one scene")
            # If no scenes detected, treat the whole video as one scene
            # Use provided duration if available, otherwise fall back to 60 seconds
            fallback_duration = video_duration_s if video_duration_s is not None else 60.0
            logger.info(f"Using fallback duration: {fallback_duration}s")
            return [Scene(index=0, start_s=0.0, end_s=fallback_duration)]

        # Convert scene list to our Scene objects
        scenes = []
        for idx, (start_time, end_time) in enumerate(scene_list):
            scene = Scene(
                index=idx,
                start_s=start_time.get_seconds(),
                end_s=end_time.get_seconds(),
            )
            scenes.append(scene)
            logger.debug(f"Detected {scene}")

        logger.info(f"Detected {len(scenes)} scenes using {settings.scene_detector} detector")
        return scenes


# Global scene detector instance
scene_detector = SceneDetector()
