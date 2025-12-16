"""Scene detection using PySceneDetect with configurable detectors.

This module provides scene detection functionality with support for multiple
detection strategies:
- AdaptiveDetector: Better for videos with varying content
- ContentDetector: Traditional content-based detection
- ThresholdDetector: Based on brightness/fades

The module supports a "best-of-all" strategy that runs all detectors
and selects the one that produces the most scenes, optimizing for
accurate scene separation across different video categories.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from scenedetect import detect, VideoStream, open_video
from scenedetect.detectors import AdaptiveDetector, ContentDetector, ThresholdDetector
from scenedetect.scene_detector import SceneDetector as PySceneDetector

from ..config import settings

logger = logging.getLogger(__name__)


class SceneDetectionStrategy(str, Enum):
    """Supported scene detection strategies."""

    ADAPTIVE = "adaptive"
    CONTENT = "content"
    THRESHOLD = "threshold"
    BEST = "best"  # Try all and pick the one with most scenes


@dataclass
class DetectorConfig:
    """Configuration for a specific detector type."""

    # AdaptiveDetector parameters
    adaptive_threshold: float = 3.0
    adaptive_window_width: int = 2
    adaptive_min_content_val: float = 15.0

    # ContentDetector parameters
    content_threshold: float = 27.0

    # ThresholdDetector parameters
    threshold_threshold: float = 12.0
    threshold_method: str = "FLOOR"  # FLOOR, CEILING, or BOTH


@dataclass
class DetectorPreferences:
    """User-specific detector preferences with custom thresholds per algorithm."""

    adaptive: Optional[dict] = None
    content: Optional[dict] = None
    threshold: Optional[dict] = None

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "DetectorPreferences":
        """Create DetectorPreferences from a dictionary (e.g., from database)."""
        if not data:
            return cls()
        return cls(
            adaptive=data.get("adaptive"),
            content=data.get("content"),
            threshold=data.get("threshold"),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        result = {}
        if self.adaptive:
            result["adaptive"] = self.adaptive
        if self.content:
            result["content"] = self.content
        if self.threshold:
            result["threshold"] = self.threshold
        return result

    def get_config_for_detector(self, detector_type: SceneDetectionStrategy) -> DetectorConfig:
        """Get detector config with user preferences merged over defaults."""
        config = DetectorConfig()

        if detector_type == SceneDetectionStrategy.ADAPTIVE and self.adaptive:
            if "threshold" in self.adaptive:
                config.adaptive_threshold = self.adaptive["threshold"]
            if "window_width" in self.adaptive:
                config.adaptive_window_width = self.adaptive["window_width"]
            if "min_content_val" in self.adaptive:
                config.adaptive_min_content_val = self.adaptive["min_content_val"]

        elif detector_type == SceneDetectionStrategy.CONTENT and self.content:
            if "threshold" in self.content:
                config.content_threshold = self.content["threshold"]

        elif detector_type == SceneDetectionStrategy.THRESHOLD and self.threshold:
            if "threshold" in self.threshold:
                config.threshold_threshold = self.threshold["threshold"]
            if "method" in self.threshold:
                config.threshold_method = self.threshold["method"]

        return config


@dataclass
class DetectionResult:
    """Result from a scene detection run."""

    strategy: SceneDetectionStrategy
    scenes: list["Scene"]
    config_used: dict = field(default_factory=dict)


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


def create_detector(
    strategy: SceneDetectionStrategy,
    fps: float,
    min_scene_len_seconds: float,
    config: DetectorConfig,
) -> PySceneDetector:
    """
    Factory function to create a scene detector based on strategy and config.

    Args:
        strategy: The detection strategy to use
        fps: Video frame rate (used to convert min_scene_len from seconds to frames)
        min_scene_len_seconds: Minimum scene length in seconds
        config: Detector configuration with thresholds

    Returns:
        Configured PySceneDetect detector instance

    Raises:
        ValueError: If an unknown detector strategy is specified
    """
    # Calculate minimum scene length in frames
    min_scene_len_frames = max(1, int(round(min_scene_len_seconds * fps)))

    if strategy == SceneDetectionStrategy.ADAPTIVE:
        logger.info(
            f"Creating AdaptiveDetector with threshold={config.adaptive_threshold}, "
            f"window_width={config.adaptive_window_width}, "
            f"min_content_val={config.adaptive_min_content_val}, "
            f"min_scene_len={min_scene_len_frames} frames ({min_scene_len_seconds}s)"
        )
        return AdaptiveDetector(
            adaptive_threshold=config.adaptive_threshold,
            window_width=config.adaptive_window_width,
            min_content_val=config.adaptive_min_content_val,
            min_scene_len=min_scene_len_frames,
        )

    elif strategy == SceneDetectionStrategy.CONTENT:
        logger.info(
            f"Creating ContentDetector with threshold={config.content_threshold}, "
            f"min_scene_len={min_scene_len_frames} frames ({min_scene_len_seconds}s)"
        )
        return ContentDetector(
            threshold=config.content_threshold,
            min_scene_len=min_scene_len_frames,
        )

    elif strategy == SceneDetectionStrategy.THRESHOLD:
        logger.info(
            f"Creating ThresholdDetector with threshold={config.threshold_threshold}, "
            f"method={config.threshold_method}, "
            f"min_scene_len={min_scene_len_frames} frames ({min_scene_len_seconds}s)"
        )
        return ThresholdDetector(
            threshold=config.threshold_threshold,
            min_scene_len=min_scene_len_frames,
        )

    else:
        raise ValueError(f"Unknown detector strategy: {strategy}")


def get_scene_detector(fps: float = 30.0) -> PySceneDetector:
    """
    Factory function to create a scene detector based on configuration.

    This is a backwards-compatible function that uses global settings.

    Args:
        fps: Video frame rate (used to convert min_scene_len from seconds to frames)

    Returns:
        Configured PySceneDetect detector instance
    """
    strategy = settings.scene_detector.lower()

    # Create default config from settings
    config = DetectorConfig(
        adaptive_threshold=settings.scene_adaptive_threshold,
        adaptive_window_width=settings.scene_adaptive_window_width,
        adaptive_min_content_val=settings.scene_adaptive_min_content_val,
        content_threshold=settings.scene_content_threshold,
    )

    try:
        strategy_enum = SceneDetectionStrategy(strategy)
    except ValueError:
        logger.warning(f"Unknown scene detector strategy '{strategy}', falling back to AdaptiveDetector")
        strategy_enum = SceneDetectionStrategy.ADAPTIVE

    # Don't create BEST strategy detector directly - it's handled separately
    if strategy_enum == SceneDetectionStrategy.BEST:
        strategy_enum = SceneDetectionStrategy.ADAPTIVE

    return create_detector(
        strategy=strategy_enum,
        fps=fps,
        min_scene_len_seconds=settings.scene_min_len_seconds,
        config=config,
    )


def _run_single_detector(
    video_path: Path,
    strategy: SceneDetectionStrategy,
    fps: float,
    min_scene_len_seconds: float,
    config: DetectorConfig,
) -> DetectionResult:
    """
    Run a single detector on a video and return results.

    Args:
        video_path: Path to video file
        strategy: Detection strategy to use
        fps: Video frame rate
        min_scene_len_seconds: Minimum scene length in seconds
        config: Detector configuration

    Returns:
        DetectionResult with scenes and metadata
    """
    logger.info(f"Running {strategy.value} detector on {video_path.name}")

    try:
        detector = create_detector(
            strategy=strategy,
            fps=fps,
            min_scene_len_seconds=min_scene_len_seconds,
            config=config,
        )

        scene_list = detect(str(video_path), detector)

        # Convert scene list to Scene objects
        scenes = []
        for idx, (start_time, end_time) in enumerate(scene_list):
            scene = Scene(
                index=idx,
                start_s=start_time.get_seconds(),
                end_s=end_time.get_seconds(),
            )
            scenes.append(scene)

        logger.info(f"{strategy.value} detector found {len(scenes)} scenes")

        return DetectionResult(
            strategy=strategy,
            scenes=scenes,
            config_used={
                "strategy": strategy.value,
                "min_scene_len_seconds": min_scene_len_seconds,
            },
        )

    except Exception as e:
        logger.error(f"Error running {strategy.value} detector: {e}")
        return DetectionResult(
            strategy=strategy,
            scenes=[],
            config_used={"error": str(e)},
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

        This method uses the detector specified in settings.scene_detector.
        This is a backwards-compatible method that uses global settings.

        Args:
            video_path: Path to video file
            video_duration_s: Optional video duration in seconds. If provided and no scenes
                            are detected, this will be used for the fallback scene.
            fps: Optional video frame rate. If not provided, uses a default of 30.0 fps.

        Returns:
            List of Scene objects
        """
        logger.info(
            f"Detecting scenes in {video_path} using '{settings.scene_detector}' detector"
        )

        effective_fps = fps if fps is not None else 30.0
        detector = get_scene_detector(fps=effective_fps)

        scene_list = detect(str(video_path), detector)

        if not scene_list:
            logger.warning("No scenes detected, treating entire video as one scene")
            fallback_duration = video_duration_s if video_duration_s is not None else 60.0
            logger.info(f"Using fallback duration: {fallback_duration}s")
            return [Scene(index=0, start_s=0.0, end_s=fallback_duration)]

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

    @staticmethod
    def detect_scenes_best(
        video_path: Path,
        video_duration_s: Optional[float] = None,
        fps: Optional[float] = None,
        preferences: Optional[DetectorPreferences] = None,
    ) -> tuple[list[Scene], DetectionResult]:
        """
        Detect scenes using all available detectors and select the best result.

        "Best" is defined as the detector that produces the most scenes,
        which typically indicates more accurate scene separation.

        Args:
            video_path: Path to video file
            video_duration_s: Optional video duration in seconds
            fps: Optional video frame rate
            preferences: Optional user-specific detector preferences

        Returns:
            Tuple of (list of Scene objects, DetectionResult with metadata about which detector was used)
        """
        effective_fps = fps if fps is not None else 30.0
        min_scene_len = settings.scene_min_len_seconds
        prefs = preferences or DetectorPreferences()

        logger.info(f"Running all detectors to find best scene separation for {video_path.name}")

        # Detectors to try (in order)
        strategies_to_try = [
            SceneDetectionStrategy.ADAPTIVE,
            SceneDetectionStrategy.CONTENT,
            SceneDetectionStrategy.THRESHOLD,
        ]

        results: list[DetectionResult] = []

        for strategy in strategies_to_try:
            config = prefs.get_config_for_detector(strategy)
            # Also merge in system defaults from settings
            if strategy == SceneDetectionStrategy.ADAPTIVE:
                if not prefs.adaptive:
                    config.adaptive_threshold = settings.scene_adaptive_threshold
                    config.adaptive_window_width = settings.scene_adaptive_window_width
                    config.adaptive_min_content_val = settings.scene_adaptive_min_content_val
            elif strategy == SceneDetectionStrategy.CONTENT:
                if not prefs.content:
                    config.content_threshold = settings.scene_content_threshold

            result = _run_single_detector(
                video_path=video_path,
                strategy=strategy,
                fps=effective_fps,
                min_scene_len_seconds=min_scene_len,
                config=config,
            )
            results.append(result)

        # Find the result with the most scenes
        best_result = max(results, key=lambda r: len(r.scenes))

        logger.info(
            f"Best detector: {best_result.strategy.value} with {len(best_result.scenes)} scenes. "
            f"Results: {[(r.strategy.value, len(r.scenes)) for r in results]}"
        )

        # If no scenes were found by any detector, treat whole video as one scene
        if not best_result.scenes:
            logger.warning("No scenes detected by any detector, treating entire video as one scene")
            fallback_duration = video_duration_s if video_duration_s is not None else 60.0
            best_result = DetectionResult(
                strategy=SceneDetectionStrategy.ADAPTIVE,
                scenes=[Scene(index=0, start_s=0.0, end_s=fallback_duration)],
                config_used={"fallback": True},
            )

        return best_result.scenes, best_result

    @staticmethod
    def detect_scenes_with_preferences(
        video_path: Path,
        video_duration_s: Optional[float] = None,
        fps: Optional[float] = None,
        preferences: Optional[DetectorPreferences] = None,
        use_best: bool = True,
    ) -> tuple[list[Scene], DetectionResult]:
        """
        Detect scenes with user-specific preferences.

        Args:
            video_path: Path to video file
            video_duration_s: Optional video duration in seconds
            fps: Optional video frame rate
            preferences: Optional user-specific detector preferences
            use_best: If True, try all detectors and pick the best one

        Returns:
            Tuple of (list of Scene objects, DetectionResult)
        """
        if use_best:
            return SceneDetector.detect_scenes_best(
                video_path=video_path,
                video_duration_s=video_duration_s,
                fps=fps,
                preferences=preferences,
            )

        # Use single detector (default to adaptive)
        effective_fps = fps if fps is not None else 30.0
        min_scene_len = settings.scene_min_len_seconds
        prefs = preferences or DetectorPreferences()

        strategy = SceneDetectionStrategy.ADAPTIVE
        config = prefs.get_config_for_detector(strategy)

        # Merge system defaults
        if not prefs.adaptive:
            config.adaptive_threshold = settings.scene_adaptive_threshold
            config.adaptive_window_width = settings.scene_adaptive_window_width
            config.adaptive_min_content_val = settings.scene_adaptive_min_content_val

        result = _run_single_detector(
            video_path=video_path,
            strategy=strategy,
            fps=effective_fps,
            min_scene_len_seconds=min_scene_len,
            config=config,
        )

        if not result.scenes:
            fallback_duration = video_duration_s if video_duration_s is not None else 60.0
            result.scenes = [Scene(index=0, start_s=0.0, end_s=fallback_duration)]

        return result.scenes, result


# Global scene detector instance
scene_detector = SceneDetector()
