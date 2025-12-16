"""Database models."""
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class VideoStatus(str, Enum):
    """Video processing status."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class ExportStatus(str, Enum):
    """Scene export processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AspectRatioStrategy(str, Enum):
    """Aspect ratio conversion strategy for exports."""

    CENTER_CROP = "center_crop"
    LETTERBOX = "letterbox"
    SMART_CROP = "smart_crop"


class OutputQuality(str, Enum):
    """Export output quality preset."""

    HIGH = "high"
    MEDIUM = "medium"


class UserProfile:
    """User profile model."""

    def __init__(
        self,
        user_id: UUID,
        full_name: str,
        industry: Optional[str] = None,
        job_title: Optional[str] = None,
        preferred_language: str = "ko",
        marketing_consent: bool = False,
        marketing_consent_at: Optional[datetime] = None,
        scene_detector_preferences: Optional[dict] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        """Initialize UserProfile.

        Args:
            user_id: UUID of the user.
            full_name: Full name of the user.
            industry: Industry of the user (optional).
            job_title: Job title of the user (optional).
            preferred_language: Preferred language of the user.
            marketing_consent: Whether the user has consented to marketing.
            marketing_consent_at: Timestamp when marketing consent was given.
            scene_detector_preferences: User's custom thresholds for scene detectors (optional).
            created_at: Timestamp when the profile was created.
            updated_at: Timestamp when the profile was last updated.
        """
        self.user_id = user_id
        self.full_name = full_name
        self.industry = industry
        self.job_title = job_title
        self.preferred_language = preferred_language
        self.marketing_consent = marketing_consent
        self.marketing_consent_at = marketing_consent_at
        self.scene_detector_preferences = scene_detector_preferences
        self.created_at = created_at
        self.updated_at = updated_at


class Video:
    """Video model."""

    def __init__(
        self,
        id: UUID,
        owner_id: UUID,
        storage_path: str,
        status: VideoStatus,
        filename: Optional[str] = None,
        duration_s: Optional[float] = None,
        frame_rate: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        video_created_at: Optional[datetime] = None,
        thumbnail_url: Optional[str] = None,
        full_transcript: Optional[str] = None,
        transcript_segments: Optional[list] = None,
        video_summary: Optional[str] = None,
        has_rich_semantics: Optional[bool] = None,
        transcript_language: Optional[str] = None,
        error_message: Optional[str] = None,
        # EXIF metadata fields
        exif_metadata: Optional[dict] = None,
        location_latitude: Optional[float] = None,
        location_longitude: Optional[float] = None,
        location_name: Optional[str] = None,
        camera_make: Optional[str] = None,
        camera_model: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        """Initialize Video.

        Args:
            id: UUID of the video.
            owner_id: UUID of the user who owns the video.
            storage_path: Path to the video file in storage.
            status: Current processing status of the video.
            filename: Original filename of the uploaded video (optional).
            duration_s: Duration of the video in seconds (optional).
            frame_rate: Frame rate of the video (optional).
            width: Width of the video resolution (optional).
            height: Height of the video resolution (optional).
            video_created_at: Creation timestamp from video metadata (optional).
            thumbnail_url: URL to the video thumbnail (optional).
            full_transcript: Full transcript of the video (optional).
            transcript_segments: Whisper segments with timestamps (optional).
            video_summary: AI-generated video summary (v2, optional).
            has_rich_semantics: Flag indicating rich semantics processing (v2, optional).
            transcript_language: ISO-639-1 language code for forced transcription (optional).
            error_message: Error message if processing failed (optional).
            exif_metadata: JSONB EXIF metadata (GPS, camera, recording settings).
            location_latitude: GPS latitude (denormalized for queries).
            location_longitude: GPS longitude (denormalized for queries).
            location_name: Reverse-geocoded location name.
            camera_make: Camera manufacturer.
            camera_model: Camera model.
            created_at: Timestamp when the video record was created.
            updated_at: Timestamp when the video record was last updated.
        """
        self.id = id
        self.owner_id = owner_id
        self.storage_path = storage_path
        self.status = status
        self.filename = filename
        self.duration_s = duration_s
        self.frame_rate = frame_rate
        self.width = width
        self.height = height
        self.video_created_at = video_created_at
        self.thumbnail_url = thumbnail_url
        self.full_transcript = full_transcript
        self.transcript_segments = transcript_segments
        self.video_summary = video_summary
        self.has_rich_semantics = has_rich_semantics
        self.transcript_language = transcript_language
        self.error_message = error_message
        self.exif_metadata = exif_metadata
        self.location_latitude = location_latitude
        self.location_longitude = location_longitude
        self.location_name = location_name
        self.camera_make = camera_make
        self.camera_model = camera_model
        self.created_at = created_at
        self.updated_at = updated_at


class VideoScene:
    """Video scene model."""

    def __init__(
        self,
        id: UUID,
        video_id: UUID,
        index: int,
        start_s: float,
        end_s: float,
        transcript_segment: Optional[str] = None,
        visual_summary: Optional[str] = None,
        combined_text: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        visual_description: Optional[str] = None,
        visual_entities: Optional[list[str]] = None,
        visual_actions: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        similarity: Optional[float] = None,  # For search results
        created_at: Optional[datetime] = None,
    ):
        """Initialize VideoScene.

        Args:
            id: UUID of the scene.
            video_id: UUID of the parent video.
            index: Sequential index of the scene in the video.
            start_s: Start time of the scene in seconds.
            end_s: End time of the scene in seconds.
            transcript_segment: Transcript text for this scene (optional).
            visual_summary: Visual description of this scene (optional).
            combined_text: Combined text used for embedding generation (optional).
            thumbnail_url: URL to the scene thumbnail (optional).
            visual_description: Richer 1-2 sentence description (v2, optional).
            visual_entities: List of main entities detected (v2, optional).
            visual_actions: List of actions detected (v2, optional).
            tags: Normalized tags for filtering (v2, optional).
            similarity: Similarity score for search results (optional).
            created_at: Timestamp when the scene was created.
        """
        self.id = id
        self.video_id = video_id
        self.index = index
        self.start_s = start_s
        self.end_s = end_s
        self.transcript_segment = transcript_segment
        self.visual_summary = visual_summary
        self.combined_text = combined_text
        self.thumbnail_url = thumbnail_url
        self.visual_description = visual_description
        self.visual_entities = visual_entities or []
        self.visual_actions = visual_actions or []
        self.tags = tags or []
        self.similarity = similarity
        self.created_at = created_at


class SceneExport:
    """Scene export model for YouTube Shorts feature."""

    def __init__(
        self,
        id: UUID,
        scene_id: UUID,
        user_id: UUID,
        aspect_ratio_strategy: AspectRatioStrategy,
        output_quality: OutputQuality,
        status: ExportStatus = ExportStatus.PENDING,
        error_message: Optional[str] = None,
        storage_path: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        duration_s: Optional[float] = None,
        resolution: Optional[str] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
    ):
        """Initialize SceneExport.

        Args:
            id: UUID of the export.
            scene_id: UUID of the scene being exported.
            user_id: UUID of the user who created the export.
            aspect_ratio_strategy: How to handle aspect ratio conversion.
            output_quality: Video quality preset (high or medium).
            status: Current processing status (default: pending).
            error_message: Error message if export failed (optional).
            storage_path: Path to exported file in storage (optional).
            file_size_bytes: Size of exported file in bytes (optional).
            duration_s: Duration of exported video in seconds (optional).
            resolution: Video resolution (e.g., "1080x1920") (optional).
            created_at: Timestamp when export was created.
            completed_at: Timestamp when export completed (optional).
            expires_at: Timestamp when export expires (created_at + 24 hours).
        """
        self.id = id
        self.scene_id = scene_id
        self.user_id = user_id
        self.aspect_ratio_strategy = aspect_ratio_strategy
        self.output_quality = output_quality
        self.status = status
        self.error_message = error_message
        self.storage_path = storage_path
        self.file_size_bytes = file_size_bytes
        self.duration_s = duration_s
        self.resolution = resolution
        self.created_at = created_at
        self.completed_at = completed_at
        self.expires_at = expires_at
