"""Scene detection using PySceneDetect."""
import logging
from pathlib import Path
from scenedetect import detect, ContentDetector, split_video_ffmpeg

from ..config import settings

logger = logging.getLogger(__name__)


class Scene:
    """Represents a detected scene."""

    def __init__(self, index: int, start_s: float, end_s: float):
        self.index = index
        self.start_s = start_s
        self.end_s = end_s

    def __repr__(self):
        return f"Scene({self.index}, {self.start_s:.2f}s-{self.end_s:.2f}s)"


class SceneDetector:
    """Scene detection handler."""

    @staticmethod
    def detect_scenes(video_path: Path) -> list[Scene]:
        """
        Detect scenes in a video using content-based detection.

        Args:
            video_path: Path to video file

        Returns:
            List of Scene objects

        Raises:
            Exception: If scene detection fails
        """
        logger.info(f"Detecting scenes in {video_path}")

        # Use PySceneDetect to find scene boundaries
        scene_list = detect(
            str(video_path),
            ContentDetector(threshold=settings.scene_detection_threshold),
        )

        if not scene_list:
            logger.warning("No scenes detected, treating entire video as one scene")
            # If no scenes detected, treat the whole video as one scene
            # We'll need to get the duration somehow - for now use a default
            return [Scene(index=0, start_s=0.0, end_s=60.0)]

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

        logger.info(f"Detected {len(scenes)} scenes")
        return scenes


# Global scene detector instance
scene_detector = SceneDetector()
