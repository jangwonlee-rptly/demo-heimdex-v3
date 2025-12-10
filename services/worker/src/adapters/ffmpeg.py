"""FFmpeg/FFprobe adapter for video processing."""
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExifMetadata:
    """EXIF-like metadata extracted from video files."""

    # GPS/Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    location_name: Optional[str] = None  # Will be populated by reverse geocoding

    # Camera info
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    software: Optional[str] = None

    # Recording settings
    iso: Optional[int] = None
    focal_length: Optional[float] = None
    aperture: Optional[float] = None

    # Other metadata
    artist: Optional[str] = None
    copyright: Optional[str] = None
    orientation: Optional[int] = None
    content_identifier: Optional[str] = None

    # Raw metadata dict for any extra fields
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for database storage."""
        result: dict[str, Any] = {}

        # GPS section
        if self.latitude is not None or self.longitude is not None:
            result["gps"] = {}
            if self.latitude is not None:
                result["gps"]["latitude"] = self.latitude
            if self.longitude is not None:
                result["gps"]["longitude"] = self.longitude
            if self.altitude is not None:
                result["gps"]["altitude"] = self.altitude
            if self.location_name:
                result["gps"]["location_name"] = self.location_name

        # Camera section
        if self.camera_make or self.camera_model or self.software:
            result["camera"] = {}
            if self.camera_make:
                result["camera"]["make"] = self.camera_make
            if self.camera_model:
                result["camera"]["model"] = self.camera_model
            if self.software:
                result["camera"]["software"] = self.software

        # Recording section
        if self.iso or self.focal_length or self.aperture:
            result["recording"] = {}
            if self.iso:
                result["recording"]["iso"] = self.iso
            if self.focal_length:
                result["recording"]["focal_length"] = self.focal_length
            if self.aperture:
                result["recording"]["aperture"] = self.aperture

        # Other section
        other_fields = {}
        if self.artist:
            other_fields["artist"] = self.artist
        if self.copyright:
            other_fields["copyright"] = self.copyright
        if self.orientation:
            other_fields["orientation"] = self.orientation
        if self.content_identifier:
            other_fields["content_identifier"] = self.content_identifier
        if other_fields:
            result["other"] = other_fields

        return result if result else {}

    def has_location(self) -> bool:
        """Check if GPS location is available."""
        return self.latitude is not None and self.longitude is not None


class VideoMetadata:
    """Video metadata extracted from ffprobe."""

    def __init__(
        self,
        duration_s: float,
        width: int,
        height: int,
        frame_rate: float,
        created_at: Optional[datetime] = None,
        exif: Optional[ExifMetadata] = None,
    ):
        """Initialize VideoMetadata.

        Args:
            duration_s: Duration of the video in seconds.
            width: Width of the video resolution.
            height: Height of the video resolution.
            frame_rate: Frame rate of the video.
            created_at: Creation timestamp from video metadata.
            exif: EXIF-like metadata (GPS, camera, etc.).
        """
        self.duration_s = duration_s
        self.width = width
        self.height = height
        self.frame_rate = frame_rate
        self.created_at = created_at
        self.exif = exif


class FFmpegAdapter:
    """Wrapper for FFmpeg and FFprobe operations."""

    @staticmethod
    def _parse_gps_coordinate(value: str) -> Optional[float]:
        """
        Parse GPS coordinate from various formats.

        Common formats:
        - Decimal: "48.8566" or "+48.8566"
        - ISO 6709: "+48.8566+002.3522/"
        - DMS: "48°51'24.0\"N" (rarely in video metadata)

        Args:
            value: GPS coordinate string

        Returns:
            Decimal degrees as float, or None if parsing fails
        """
        if not value:
            return None

        try:
            # Try simple float parsing first (handles "+48.8566")
            return float(value.strip().rstrip("/"))
        except ValueError:
            pass

        # Try parsing ISO 6709 format: "+48.8566+002.3522/"
        # This format has latitude followed by longitude
        import re
        iso_match = re.match(r"([+-]?\d+\.?\d*)", value)
        if iso_match:
            try:
                return float(iso_match.group(1))
            except ValueError:
                pass

        logger.warning(f"Could not parse GPS coordinate: {value}")
        return None

    @staticmethod
    def _extract_exif_metadata(data: dict) -> Optional[ExifMetadata]:
        """
        Extract EXIF-like metadata from ffprobe data.

        Args:
            data: Full ffprobe JSON output

        Returns:
            ExifMetadata object, or None if no relevant metadata found
        """
        exif = ExifMetadata()
        has_any_data = False

        # Collect tags from format and all streams
        all_tags: dict[str, str] = {}

        # Format-level tags (most common location for metadata)
        format_tags = data.get("format", {}).get("tags", {})
        all_tags.update({k.lower(): v for k, v in format_tags.items()})

        # Stream-level tags
        for stream in data.get("streams", []):
            stream_tags = stream.get("tags", {})
            # Stream tags don't override format tags
            for k, v in stream_tags.items():
                key_lower = k.lower()
                if key_lower not in all_tags:
                    all_tags[key_lower] = v

        # Also check side_data_list for rotation/orientation
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                for side_data in stream.get("side_data_list", []):
                    if side_data.get("side_data_type") == "Display Matrix":
                        rotation = side_data.get("rotation")
                        if rotation is not None:
                            exif.orientation = int(rotation) % 360
                            has_any_data = True

        # Log all available tags for debugging
        if all_tags:
            logger.debug(f"Available metadata tags: {list(all_tags.keys())}")

        # GPS Location extraction
        # iPhone/Apple format: "location" tag contains ISO 6709 format
        # e.g., "+37.7749-122.4194/"
        location = all_tags.get("location", all_tags.get("com.apple.quicktime.location.iso6709", ""))
        if location:
            import re
            # Parse ISO 6709: +DD.DDDD+DDD.DDDD/ or +DD.DDDD-DDD.DDDD/
            iso_match = re.match(r"([+-]\d+\.?\d*)([+-]\d+\.?\d*)", location)
            if iso_match:
                exif.latitude = FFmpegAdapter._parse_gps_coordinate(iso_match.group(1))
                exif.longitude = FFmpegAdapter._parse_gps_coordinate(iso_match.group(2))
                if exif.latitude is not None and exif.longitude is not None:
                    has_any_data = True
                    logger.info(f"Extracted GPS: lat={exif.latitude}, lon={exif.longitude}")

        # Try individual lat/lon tags (GoPro, DJI, some Android)
        if exif.latitude is None:
            for lat_key in ["gps_latitude", "latitude", "gpslat"]:
                if lat_key in all_tags:
                    exif.latitude = FFmpegAdapter._parse_gps_coordinate(all_tags[lat_key])
                    if exif.latitude is not None:
                        has_any_data = True
                        break

        if exif.longitude is None:
            for lon_key in ["gps_longitude", "longitude", "gpslon"]:
                if lon_key in all_tags:
                    exif.longitude = FFmpegAdapter._parse_gps_coordinate(all_tags[lon_key])
                    if exif.longitude is not None:
                        has_any_data = True
                        break

        # GPS Altitude
        for alt_key in ["gps_altitude", "altitude", "gpsalt", "com.apple.quicktime.location.altitude"]:
            if alt_key in all_tags:
                try:
                    exif.altitude = float(all_tags[alt_key])
                    has_any_data = True
                    break
                except ValueError:
                    pass

        # Camera Make (manufacturer)
        for make_key in ["make", "com.apple.quicktime.make", "manufacturer"]:
            if make_key in all_tags:
                exif.camera_make = all_tags[make_key].strip()
                has_any_data = True
                break

        # Camera Model
        for model_key in ["model", "com.apple.quicktime.model", "device"]:
            if model_key in all_tags:
                exif.camera_model = all_tags[model_key].strip()
                has_any_data = True
                break

        # Software version
        for sw_key in ["software", "com.apple.quicktime.software", "encoder", "handler_name"]:
            if sw_key in all_tags:
                exif.software = all_tags[sw_key].strip()
                has_any_data = True
                break

        # Artist/Author
        for artist_key in ["artist", "author", "com.apple.quicktime.author"]:
            if artist_key in all_tags:
                exif.artist = all_tags[artist_key].strip()
                has_any_data = True
                break

        # Copyright
        if "copyright" in all_tags:
            exif.copyright = all_tags["copyright"].strip()
            has_any_data = True

        # Content Identifier (useful for deduplication)
        for id_key in ["content_identifier", "com.apple.quicktime.content.identifier", "media_id"]:
            if id_key in all_tags:
                exif.content_identifier = all_tags[id_key].strip()
                has_any_data = True
                break

        # Store raw tags for debugging/future use
        exif.raw = all_tags

        return exif if has_any_data else None

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

        # Extract EXIF-like metadata (GPS, camera info, etc.)
        exif = FFmpegAdapter._extract_exif_metadata(data)
        if exif:
            logger.info(
                f"EXIF metadata: camera={exif.camera_make} {exif.camera_model}, "
                f"has_gps={exif.has_location()}"
            )

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
            exif=exif,
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

    @staticmethod
    def extract_scene_clip_with_aspect_conversion(
        video_path: Path,
        start_s: float,
        end_s: float,
        output_path: Path,
        aspect_ratio_strategy: str = "center_crop",
        output_quality: str = "high",
    ) -> dict:
        """
        Extract a scene clip and convert to YouTube Shorts format (9:16, 1080x1920).

        Args:
            video_path: Path to source video file
            start_s: Scene start time in seconds
            end_s: Scene end time in seconds
            output_path: Path to save output MP4
            aspect_ratio_strategy: 'center_crop' or 'letterbox'
            output_quality: 'high' or 'medium'

        Returns:
            dict: Metadata about the exported video (file_size_bytes, duration_s, resolution)

        Raises:
            subprocess.CalledProcessError: If ffmpeg fails
        """
        logger.info(
            f"Extracting scene clip {start_s}s-{end_s}s with {aspect_ratio_strategy} strategy"
        )

        # Quality presets
        if output_quality == "high":
            crf = "18"  # High quality (8-10 Mbps)
            audio_bitrate = "192k"
        else:  # medium
            crf = "23"  # Medium quality (4-6 Mbps)
            audio_bitrate = "128k"

        # Build video filter for aspect ratio conversion
        if aspect_ratio_strategy == "center_crop":
            # Crop center to 9:16 aspect ratio
            # Formula: crop width to height*9/16 from center
            vf = "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos"
        elif aspect_ratio_strategy == "letterbox":
            # Scale to fit within 1080x1920, add black bars
            vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
        else:
            raise ValueError(f"Unknown aspect_ratio_strategy: {aspect_ratio_strategy}")

        # FFmpeg command
        # -ss before -i for fast seeking
        # -to for end time (more accurate than -t duration)
        # -movflags +faststart for web playback optimization
        cmd = [
            "ffmpeg",
            "-ss", str(start_s),
            "-to", str(end_s),
            "-i", str(video_path),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "slow",  # Better compression
            "-crf", crf,
            "-c:a", "aac",
            "-b:a", audio_bitrate,
            "-ar", "44100",  # Audio sample rate
            "-movflags", "+faststart",  # Enable fast start for web
            "-y",  # Overwrite output
            str(output_path),
        ]

        logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            text=True,
        )

        # Get output file metadata
        file_size_bytes = output_path.stat().st_size
        duration_s = end_s - start_s

        logger.info(
            f"Scene clip extracted: {output_path} "
            f"({file_size_bytes / 1024 / 1024:.2f} MB, {duration_s:.1f}s)"
        )

        return {
            "file_size_bytes": file_size_bytes,
            "duration_s": duration_s,
            "resolution": "1080x1920",
        }


# Global ffmpeg adapter instance
ffmpeg = FFmpegAdapter()
