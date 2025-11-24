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
        """Initialize UserProfile.

        Args:
            user_id: UUID of the user.
            full_name: Full name of the user.
            industry: Industry of the user (optional).
            job_title: Job title of the user (optional).
            preferred_language: Preferred language of the user.
            marketing_consent: Whether the user has consented to marketing.
            marketing_consent_at: Timestamp when marketing consent was given.
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
        video_summary: Optional[str] = None,
        has_rich_semantics: Optional[bool] = None,
        error_message: Optional[str] = None,
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
            video_summary: AI-generated video summary (v2, optional).
            has_rich_semantics: Flag indicating rich semantics processing (v2, optional).
            error_message: Error message if processing failed (optional).
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
        self.video_summary = video_summary
        self.has_rich_semantics = has_rich_semantics
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
