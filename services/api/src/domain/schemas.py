"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from .models import VideoStatus


# User Profile Schemas
class UserProfileCreate(BaseModel):
    """Schema for creating a user profile."""

    full_name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    preferred_language: str = Field("ko", pattern="^(ko|en)$")
    marketing_consent: bool = False


class UserProfileUpdate(BaseModel):
    """Schema for updating a user profile."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    industry: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    preferred_language: Optional[str] = Field(None, pattern="^(ko|en)$")
    marketing_consent: Optional[bool] = None


class UserProfileResponse(BaseModel):
    """Schema for user profile response."""

    user_id: UUID
    full_name: str
    industry: Optional[str]
    job_title: Optional[str]
    preferred_language: str
    marketing_consent: bool
    marketing_consent_at: Optional[datetime]
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
