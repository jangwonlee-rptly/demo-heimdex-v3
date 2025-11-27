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
        """Initialize VideoMetadata.

        Args:
            duration_s: Duration of the video in seconds.
            width: Width of the video resolution.
            height: Height of the video resolution.
            frame_rate: Frame rate of the video.
            created_at: Creation timestamp from video metadata.
        """
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
    def get_audio_streams(video_path: Path) -> list[dict]:
        """
        Get information about all audio streams in a video file.

        Args:
            video_path: Path to video file

        Returns:
            List of audio stream info dicts with keys:
            - index: absolute stream index (for use with -map 0:{index})
            - audio_index: audio-relative index (for use with -map 0:a:{audio_index})
            - codec: audio codec name
            - channels: number of audio channels
            - sample_rate: sample rate in Hz
            - bit_rate: bit rate (if available)
            - language: language tag (if available)
            - title: stream title (if available, often contains description like "commentary")
        """
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
            audio_streams = []
            audio_index = 0  # Track audio-relative index

            for stream in data.get("streams", []):
                if stream.get("codec_type") != "audio":
                    continue

                tags = stream.get("tags", {})
                stream_info = {
                    "index": stream.get("index"),  # Absolute stream index
                    "audio_index": audio_index,  # Audio-relative index
                    "codec": stream.get("codec_name"),
                    "channels": stream.get("channels", 0),
                    "sample_rate": int(stream.get("sample_rate", 0)),
                    "bit_rate": int(stream.get("bit_rate", 0)) if stream.get("bit_rate") else 0,
                    "language": tags.get("language", tags.get("LANGUAGE", "")),
                    "title": tags.get("title", tags.get("TITLE", "")),
                }
                audio_streams.append(stream_info)
                audio_index += 1

            return audio_streams

        except Exception as e:
            logger.warning(f"Failed to get audio streams: {e}")
            return []

    @staticmethod
    def get_best_audio_stream_index(video_path: Path) -> Optional[int]:
        """
        Determine the best audio stream to use for transcription.

        Selection criteria (in order of priority):
        1. Skip streams with titles containing "commentary", "description", "subtitle", "narrat"
        2. Prefer streams with more channels (stereo > mono)
        3. Prefer streams with higher bit rate
        4. Fall back to first audio stream if no better option

        Args:
            video_path: Path to video file

        Returns:
            Audio-relative stream index (for use with -map 0:a:{index}), or None if no audio
        """
        audio_streams = FFmpegAdapter.get_audio_streams(video_path)

        if not audio_streams:
            return None

        logger.info(f"Found {len(audio_streams)} audio stream(s)")
        for stream in audio_streams:
            logger.info(
                f"  Audio stream {stream['audio_index']} (absolute: {stream['index']}): "
                f"{stream['codec']}, {stream['channels']}ch, {stream['sample_rate']}Hz, "
                f"bitrate={stream['bit_rate']}, lang={stream['language']}, "
                f"title='{stream['title']}'"
            )

        # Filter out commentary/description/subtitle tracks
        excluded_keywords = ["commentary", "description", "subtitle", "narrat", "자막", "caption", "uptitle"]
        filtered_streams = [
            s for s in audio_streams
            if not any(kw in s["title"].lower() for kw in excluded_keywords)
        ]

        # If all streams were filtered out, use original list
        if not filtered_streams:
            logger.warning("All audio streams appear to be commentary/subtitle tracks, using first stream")
            filtered_streams = audio_streams

        # Sort by channels (descending), then by bit_rate (descending)
        sorted_streams = sorted(
            filtered_streams,
            key=lambda s: (s["channels"], s["bit_rate"]),
            reverse=True,
        )

        best_stream = sorted_streams[0]
        logger.info(f"Selected audio stream {best_stream['audio_index']} (absolute: {best_stream['index']}) as best option")
        return best_stream["audio_index"]

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
        audio_streams = FFmpegAdapter.get_audio_streams(video_path)
        has_audio = len(audio_streams) > 0
        logger.info(f"Audio stream {'found' if has_audio else 'not found'}")
        return has_audio

    @staticmethod
    def extract_audio(video_path: Path, output_path: Path, audio_stream_index: Optional[int] = None) -> None:
        """
        Extract audio track from video.

        Args:
            video_path: Path to video file
            output_path: Path to save extracted audio (e.g., .mp3, .wav)
            audio_stream_index: Audio-relative stream index to extract (0, 1, 2...).
                               If None, automatically selects the best audio stream
                               based on channels, bitrate, and title metadata.

        Raises:
            subprocess.CalledProcessError: If ffmpeg fails
            ValueError: If no audio stream found
        """
        # Auto-select best audio stream if not specified
        if audio_stream_index is None:
            audio_stream_index = FFmpegAdapter.get_best_audio_stream_index(video_path)
            if audio_stream_index is None:
                raise ValueError("No audio stream found in video")

        logger.info(f"Extracting audio stream 0:a:{audio_stream_index} from {video_path} to {output_path}")

        subprocess.run(
            [
                "ffmpeg",
                "-i", str(video_path),
                "-map", f"0:a:{audio_stream_index}",  # Select specific audio stream
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
