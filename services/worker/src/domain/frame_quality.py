"""Frame quality checks for visual semantics optimization.

This module provides utilities to pre-filter frames before calling OpenAI,
avoiding expensive API calls for low-information scenes (black, blurry, etc.).
"""
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FrameQualityResult:
    """Result of frame quality assessment."""

    def __init__(
        self,
        is_informative: bool,
        brightness: float,
        blur_score: float,
        reason: Optional[str] = None,
    ):
        """Initialize FrameQualityResult.

        Args:
            is_informative: Whether the frame is considered informative.
            brightness: Average brightness of the frame (0-255).
            blur_score: Laplacian variance blur score (higher is sharper).
            reason: Reason why the frame is not informative (optional).
        """
        self.is_informative = is_informative
        self.brightness = brightness
        self.blur_score = blur_score
        self.reason = reason


class FrameQualityChecker:
    """Checks frame quality to determine if visual semantics analysis is worthwhile."""

    def __init__(self, settings):
        """Initialize FrameQualityChecker with settings.

        Args:
            settings: Settings object with visual quality thresholds
        """
        self.settings = settings

    def check_frame(self, frame_path: Path) -> FrameQualityResult:
        """
        Check if a frame is visually informative.

        Args:
            frame_path: Path to frame image

        Returns:
            FrameQualityResult with assessment details
        """
        try:
            # Read image
            image = cv2.imread(str(frame_path))
            if image is None:
                logger.warning(f"Failed to read frame: {frame_path}")
                return FrameQualityResult(
                    is_informative=False,
                    brightness=0.0,
                    blur_score=0.0,
                    reason="Failed to read image",
                )

            # Check brightness
            brightness = self._calculate_brightness(image)
            is_too_dark = brightness < self.settings.visual_brightness_threshold

            # Check blur
            blur_score = self._calculate_blur_score(image)
            is_too_blurry = blur_score < self.settings.visual_blur_threshold

            # Determine if informative
            is_informative = not (is_too_dark or is_too_blurry)

            # Build reason if not informative
            reason = None
            if not is_informative:
                reasons = []
                if is_too_dark:
                    reasons.append(
                        f"too dark (brightness={brightness:.1f} < {self.settings.visual_brightness_threshold})"
                    )
                if is_too_blurry:
                    reasons.append(
                        f"too blurry (blur={blur_score:.1f} < {self.settings.visual_blur_threshold})"
                    )
                reason = ", ".join(reasons)

            logger.debug(
                f"Frame quality: brightness={brightness:.1f}, blur={blur_score:.1f}, "
                f"informative={is_informative}"
            )

            return FrameQualityResult(
                is_informative=is_informative,
                brightness=brightness,
                blur_score=blur_score,
                reason=reason,
            )

        except Exception as e:
            logger.error(f"Error checking frame quality: {e}", exc_info=True)
            return FrameQualityResult(
                is_informative=False,
                brightness=0.0,
                blur_score=0.0,
                reason=f"Error: {str(e)}",
            )

    def _calculate_brightness(self, image: np.ndarray) -> float:
        """
        Calculate average brightness of an image.

        Args:
            image: Image array (BGR format)

        Returns:
            Average brightness (0-255)
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Calculate mean intensity
        return float(np.mean(gray))

    def _calculate_blur_score(self, image: np.ndarray) -> float:
        """
        Calculate blur score using Laplacian variance.

        Higher values indicate sharper images.

        Args:
            image: Image array (BGR format)

        Returns:
            Blur score (higher = sharper)
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Calculate Laplacian variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = float(laplacian.var())

        return variance

    def find_best_frame(self, frame_paths: list[Path]) -> Optional[Path]:
        """
        Find the best (most informative) frame from a list.

        Args:
            frame_paths: List of frame paths to evaluate

        Returns:
            Path to best frame, or None if all frames are uninformative
        """
        if not frame_paths:
            return None

        best_frame = None
        best_score = -1

        for frame_path in frame_paths:
            result = self.check_frame(frame_path)

            if result.is_informative:
                # Score based on brightness and blur
                # Normalize brightness to 0-1 range, prefer mid-range brightness
                brightness_score = 1.0 - abs(result.brightness - 127.5) / 127.5

                # Normalize blur score (cap at reasonable max)
                blur_score = min(result.blur_score / 1000.0, 1.0)

                # Combined score
                combined_score = brightness_score * 0.4 + blur_score * 0.6

                if combined_score > best_score:
                    best_score = combined_score
                    best_frame = frame_path

        if best_frame:
            logger.info(f"Best frame selected: {best_frame.name} (score={best_score:.2f})")
        else:
            logger.warning("No informative frames found in candidate set")

        return best_frame

    def rank_frames_by_quality(self, frame_paths: list[Path]) -> list[tuple[Path, float]]:
        """
        Rank all frames by quality score (highest first).

        Args:
            frame_paths: List of frame paths to evaluate

        Returns:
            List of (frame_path, quality_score) tuples, sorted by score descending.
            Only includes frames that pass quality checks.
        """
        if not frame_paths:
            return []

        scored_frames = []

        for frame_path in frame_paths:
            result = self.check_frame(frame_path)

            if result.is_informative:
                # Score based on brightness and blur
                # Normalize brightness to 0-1 range, prefer mid-range brightness
                brightness_score = 1.0 - abs(result.brightness - 127.5) / 127.5

                # Normalize blur score (cap at reasonable max)
                blur_score = min(result.blur_score / 1000.0, 1.0)

                # Combined score
                combined_score = brightness_score * 0.4 + blur_score * 0.6

                scored_frames.append((frame_path, combined_score))

        # Sort by score descending
        scored_frames.sort(key=lambda x: x[1], reverse=True)

        if scored_frames:
            logger.info(f"Ranked {len(scored_frames)} informative frames (best score: {scored_frames[0][1]:.2f})")
        else:
            logger.warning("No informative frames found in candidate set")

        return scored_frames


# Module-level singleton removed - FrameQualityChecker now requires settings via DI
frame_quality_checker = None  # Placeholder for backward compatibility
