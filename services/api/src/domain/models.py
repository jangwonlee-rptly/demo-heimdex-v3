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
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.user_id = user_id
        self.full_name = full_name
        self.industry = industry
        self.job_title = job_title
        self.preferred_language = preferred_language
        self.marketing_consent = marketing_consent
        self.marketing_consent_at = marketing_consent_at
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
        error_message: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
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
        self.error_message = error_message
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
        similarity: Optional[float] = None,  # For search results
        created_at: Optional[datetime] = None,
    ):
        self.id = id
        self.video_id = video_id
        self.index = index
        self.start_s = start_s
        self.end_s = end_s
        self.transcript_segment = transcript_segment
        self.visual_summary = visual_summary
        self.combined_text = combined_text
        self.thumbnail_url = thumbnail_url
        self.similarity = similarity
        self.created_at = created_at
