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
    marketing_consent: bool = False


class UserProfileUpdate(BaseModel):
    """Schema for updating a user profile."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    industry: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    marketing_consent: Optional[bool] = None


class UserProfileResponse(BaseModel):
    """Schema for user profile response."""

    user_id: UUID
    full_name: str
    industry: Optional[str]
    job_title: Optional[str]
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
    """Schema for marking video as uploaded."""

    pass  # No additional fields needed


class VideoResponse(BaseModel):
    """Schema for video response."""

    id: UUID
    owner_id: UUID
    storage_path: str
    status: VideoStatus
    filename: Optional[str]
    duration_s: Optional[float]
    frame_rate: Optional[float]
    width: Optional[int]
    height: Optional[int]
    video_created_at: Optional[datetime]
    thumbnail_url: Optional[str]
    error_message: Optional[str]
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
    transcript_segment: Optional[str]
    visual_summary: Optional[str]
    combined_text: Optional[str]
    thumbnail_url: Optional[str]
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
