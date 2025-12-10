"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from .models import VideoStatus


# Scene Detector Preferences Schema
class SceneDetectorPreferences(BaseModel):
    """Schema for user's scene detector preferences.

    Each detector type can have custom threshold settings.
    Format: {"adaptive": {...}, "content": {...}, "threshold": {...}, "hash": {...}}
    """

    adaptive: Optional[dict] = Field(
        None,
        description="AdaptiveDetector settings: {threshold: float, window_width: int, min_content_val: float}"
    )
    content: Optional[dict] = Field(
        None,
        description="ContentDetector settings: {threshold: float}"
    )
    threshold: Optional[dict] = Field(
        None,
        description="ThresholdDetector settings: {threshold: float, method: str}"
    )
    hash: Optional[dict] = Field(
        None,
        description="HashDetector settings: {threshold: float, size: int, lowpass: int}"
    )


# EXIF Metadata Schemas
class ExifGpsMetadata(BaseModel):
    """GPS location metadata from video EXIF."""

    latitude: Optional[float] = Field(None, description="GPS latitude in decimal degrees")
    longitude: Optional[float] = Field(None, description="GPS longitude in decimal degrees")
    altitude: Optional[float] = Field(None, description="GPS altitude in meters")
    location_name: Optional[str] = Field(None, description="Reverse-geocoded location name (city, country)")


class ExifCameraMetadata(BaseModel):
    """Camera/device metadata from video EXIF."""

    make: Optional[str] = Field(None, description="Camera manufacturer (Apple, Samsung, Sony, etc.)")
    model: Optional[str] = Field(None, description="Camera model (iPhone 15 Pro, Galaxy S24, etc.)")
    software: Optional[str] = Field(None, description="Software version used to record")


class ExifRecordingMetadata(BaseModel):
    """Recording settings metadata from video EXIF."""

    iso: Optional[int] = Field(None, description="ISO speed")
    focal_length: Optional[float] = Field(None, description="Focal length in mm")
    aperture: Optional[float] = Field(None, description="Aperture (f-stop)")
    white_balance: Optional[str] = Field(None, description="White balance setting")


class ExifMetadataResponse(BaseModel):
    """Full EXIF metadata response schema."""

    gps: Optional[ExifGpsMetadata] = None
    camera: Optional[ExifCameraMetadata] = None
    recording: Optional[ExifRecordingMetadata] = None
    other: Optional[dict] = Field(None, description="Other metadata fields (artist, copyright, etc.)")


# User Profile Schemas
class UserProfileCreate(BaseModel):
    """Schema for creating a user profile."""

    full_name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    preferred_language: str = Field("ko", pattern="^(ko|en)$")
    marketing_consent: bool = False
    scene_detector_preferences: Optional[SceneDetectorPreferences] = None


class UserProfileUpdate(BaseModel):
    """Schema for updating a user profile."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    industry: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    preferred_language: Optional[str] = Field(None, pattern="^(ko|en)$")
    marketing_consent: Optional[bool] = None
    scene_detector_preferences: Optional[SceneDetectorPreferences] = None


class UserProfileResponse(BaseModel):
    """Schema for user profile response."""

    user_id: UUID
    full_name: str
    industry: Optional[str]
    job_title: Optional[str]
    preferred_language: str
    marketing_consent: bool
    marketing_consent_at: Optional[datetime]
    scene_detector_preferences: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Video Schemas
class VideoUploadUrlResponse(BaseModel):
    """Schema for video upload URL response."""

    video_id: UUID
    storage_path: str
    upload_url: Optional[str] = None  # Deprecated: client now uploads directly using Supabase client


class VideoUploadedRequest(BaseModel):
    """Schema for marking video as uploaded.

    This schema is currently empty as no additional data is required
    when marking a video as uploaded.
    """

    pass  # No additional fields needed


class VideoReprocessRequest(BaseModel):
    """Schema for reprocessing a video with optional language override.

    When a user notices the transcript came out in the wrong language
    (e.g., Whisper detected Russian when the video is Korean),
    they can request reprocessing with an explicit language hint.
    """

    transcript_language: Optional[str] = Field(
        None,
        description="ISO-639-1 language code (e.g., 'ko', 'en', 'ja', 'zh', 'es'). "
                    "If provided, forces Whisper to transcribe in this language. "
                    "If null/omitted, uses auto-detection (default behavior).",
        pattern="^[a-z]{2}$",
        examples=["ko", "en", "ja", "zh", "es", "fr", "de", "ru"],
    )


class VideoResponse(BaseModel):
    """Schema for video response."""

    id: UUID
    owner_id: UUID
    storage_path: str
    status: VideoStatus
    filename: Optional[str] = None
    duration_s: Optional[float] = None
    frame_rate: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    video_created_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    video_summary: Optional[str] = None
    has_rich_semantics: Optional[bool] = None
    error_message: Optional[str] = None
    # EXIF metadata fields (denormalized for quick access)
    exif_metadata: Optional[dict] = Field(None, description="Full EXIF metadata as JSON")
    location_latitude: Optional[float] = Field(None, description="GPS latitude")
    location_longitude: Optional[float] = Field(None, description="GPS longitude")
    location_name: Optional[str] = Field(None, description="Reverse-geocoded location name")
    camera_make: Optional[str] = Field(None, description="Camera manufacturer")
    camera_model: Optional[str] = Field(None, description="Camera model")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    """Schema for list of videos."""

    videos: list[VideoResponse]
    total: int


# Video Scene Schemas
class VideoSceneResponse(BaseModel):
    """Schema for video scene response."""

    id: UUID
    video_id: UUID
    index: int
    start_s: float
    end_s: float
    transcript_segment: Optional[str] = None
    visual_summary: Optional[str] = None
    combined_text: Optional[str] = None
    thumbnail_url: Optional[str] = None
    visual_description: Optional[str] = None
    visual_entities: Optional[list[str]] = None
    visual_actions: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    similarity: Optional[float] = None  # Only present in search results
    created_at: Optional[datetime] = None  # Not returned by search RPC

    model_config = {"from_attributes": True}


# Search Schemas
class SearchRequest(BaseModel):
    """Schema for search request."""

    query: str = Field(..., min_length=1, max_length=1000)
    video_id: Optional[UUID] = None  # If provided, search only in this video
    limit: int = Field(10, ge=1, le=100)
    threshold: float = Field(0.2, ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    """Schema for search response."""

    query: str
    results: list[VideoSceneResponse]
    total: int
    latency_ms: int


class VideoDetailsResponse(BaseModel):
    """Schema for detailed video information with all scenes."""

    video: VideoResponse
    full_transcript: Optional[str]
    scenes: list[VideoSceneResponse]
    total_scenes: int
    reprocess_hint: Optional[str] = None


# User Info Schemas
class UserInfoResponse(BaseModel):
    """Schema for basic user info from JWT."""

    user_id: str
    email: Optional[str]
    role: str


# Health Schema
class HealthResponse(BaseModel):
    """Schema for health check response."""

    status: str
    timestamp: datetime


class DependencyHealth(BaseModel):
    """Schema for individual dependency health status."""

    status: str = Field(..., description="Health status: healthy, degraded, or unhealthy")
    latency_ms: Optional[int] = Field(None, description="Response latency in milliseconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class DetailedHealthResponse(BaseModel):
    """Schema for detailed health check with dependency status."""

    status: str = Field(..., description="Overall health: healthy, degraded, or unhealthy")
    timestamp: datetime
    dependencies: dict[str, DependencyHealth] = Field(
        ...,
        description="Health status of each dependency (database, redis, storage)"
    )
