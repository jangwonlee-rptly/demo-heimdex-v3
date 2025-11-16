"""FFmpeg/FFprobe adapter for video processing."""
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VideoMetadata:
    """Video metadata extracted from ffprobe."""

    def __init__(
        self,
        duration_s: float,
        width: int,
        height: int,
        frame_rate: float,
        created_at: Optional[datetime] = None,
    ):
        self.duration_s = duration_s
        self.width = width
        self.height = height
        self.frame_rate = frame_rate
        self.created_at = created_at


class FFmpegAdapter:
    """Wrapper for FFmpeg and FFprobe operations."""

    @staticmethod
    def probe_video(video_path: Path) -> VideoMetadata:
        """
        Extract video metadata using ffprobe.

        Args:
            video_path: Path to video file

        Returns:
            VideoMetadata object

        Raises:
            subprocess.CalledProcessError: If ffprobe fails
        """
        logger.info(f"Probing video metadata from {video_path}")

        # Run ffprobe to get JSON metadata
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)

        # Extract video stream info
        video_stream = next(
            (s for s in data.get("streams", []) if s["codec_type"] == "video"),
            None,
        )

        if not video_stream:
            raise ValueError("No video stream found in file")

        # Extract metadata
        duration_s = float(data["format"].get("duration", 0))
        width = int(video_stream["width"])
        height = int(video_stream["height"])

        # Parse frame rate (can be in format like "30/1")
        frame_rate_str = video_stream.get("r_frame_rate", "30/1")
        if "/" in frame_rate_str:
            num, denom = frame_rate_str.split("/")
            frame_rate = float(num) / float(denom)
        else:
            frame_rate = float(frame_rate_str)

        # Try to extract creation time
        created_at = None
        tags = data["format"].get("tags", {})
        for key in ["creation_time", "date", "DATE"]:
            if key in tags:
                try:
                    created_at = datetime.fromisoformat(
                        tags[key].replace("Z", "+00:00")
                    )
                    break
                except Exception as e:
                    logger.warning(f"Failed to parse creation time: {e}")

        logger.info(
            f"Video metadata: {duration_s:.2f}s, {width}x{height}, "
            f"{frame_rate:.2f}fps"
        )

        return VideoMetadata(
            duration_s=duration_s,
            width=width,
            height=height,
            frame_rate=frame_rate,
            created_at=created_at,
        )

    @staticmethod
    def has_audio_stream(video_path: Path) -> bool:
        """
        Check if video file has an audio stream.

        Args:
            video_path: Path to video file

        Returns:
            True if video has audio stream, False otherwise
        """
        logger.info(f"Checking for audio stream in {video_path}")

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_streams",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            data = json.loads(result.stdout)

            # Check if there's an audio stream
            audio_stream = next(
                (s for s in data.get("streams", []) if s["codec_type"] == "audio"),
                None,
            )

            has_audio = audio_stream is not None
            logger.info(f"Audio stream {'found' if has_audio else 'not found'}")
            return has_audio

        except Exception as e:
            logger.warning(f"Failed to check for audio stream: {e}")
            return False

    @staticmethod
    def extract_audio(video_path: Path, output_path: Path) -> None:
        """
        Extract audio track from video.

        Args:
            video_path: Path to video file
            output_path: Path to save extracted audio (e.g., .mp3, .wav)

        Raises:
            subprocess.CalledProcessError: If ffmpeg fails
        """
        logger.info(f"Extracting audio from {video_path} to {output_path}")

        subprocess.run(
            [
                "ffmpeg",
                "-i", str(video_path),
                "-vn",  # No video
                "-acodec", "libmp3lame",  # MP3 codec
                "-q:a", "2",  # Quality level
                "-y",  # Overwrite output file
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )

        logger.info(f"Audio extracted to {output_path}")

    @staticmethod
    def extract_frame(
        video_path: Path,
        timestamp_s: float,
        output_path: Path,
    ) -> None:
        """
        Extract a single frame from video at given timestamp.

        Args:
            video_path: Path to video file
            timestamp_s: Timestamp in seconds
            output_path: Path to save frame image

        Raises:
            subprocess.CalledProcessError: If ffmpeg fails
        """
        logger.debug(f"Extracting frame at {timestamp_s}s to {output_path}")

        subprocess.run(
            [
                "ffmpeg",
                "-ss", str(timestamp_s),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",  # Quality level
                "-y",  # Overwrite output file
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )


# Global ffmpeg adapter instance
ffmpeg = FFmpegAdapter()
