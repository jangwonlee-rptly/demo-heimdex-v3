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
    Format: {"adaptive": {...}, "content": {...}, "threshold": {...}}
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
    # Processing timing fields (Phase 2)
    queued_at: Optional[datetime] = Field(None, description="When job was enqueued")
    processing_started_at: Optional[datetime] = Field(None, description="When worker started processing")
    processing_finished_at: Optional[datetime] = Field(None, description="When processing completed")
    processing_duration_ms: Optional[int] = Field(None, description="Total processing time in milliseconds")
    processing_stage: Optional[str] = Field(None, description="Last active processing stage")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    """Schema for list of videos."""

    videos: list[VideoResponse]
    total: int


# Video Scene Schemas
class VideoSceneResponse(BaseModel):
    """Schema for video scene response.

    When returned from search results, includes scoring information.
    The 'similarity' field is kept for backward compatibility but 'score' is preferred.
    """

    id: UUID
    video_id: UUID
    video_filename: Optional[str] = Field(
        None,
        description="Filename of the video this scene belongs to. "
                    "Included in search results for display purposes."
    )
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

    # Search scoring fields (only present in search results)
    # Primary score field - the actual ranking score used
    score: Optional[float] = Field(
        None,
        description="The ranking score used for ordering results. "
                    "Scale depends on score_type: minmax_mean/dense_only/lexical_only=[0,1], rrf=[0,0.03]"
    )
    # Type of fusion/scoring method used
    score_type: Optional[str] = Field(
        None,
        description="Type of scoring: 'minmax_mean', 'rrf', 'dense_only', or 'lexical_only'"
    )

    # Legacy field for backward compatibility (deprecated, use 'score' instead)
    similarity: Optional[float] = Field(
        None,
        description="DEPRECATED: Use 'score' field instead. Kept for backward compatibility."
    )

    # Display score field (calibrated for UI, does not affect ranking)
    display_score: Optional[float] = Field(
        None,
        description="Per-query calibrated score for UI display (0..1, typically capped at 0.95-0.97). "
                    "This is derived from 'score' using exponential squashing to avoid overconfident "
                    "100% displays on mediocre matches. Only present if ENABLE_DISPLAY_SCORE_CALIBRATION=true. "
                    "Use this for displaying confidence % to users. Ranking still uses 'score'."
    )

    # Debug fields (only present when SEARCH_DEBUG=true)
    dense_score_raw: Optional[float] = Field(
        None,
        description="Raw dense (vector similarity) score before normalization. Debug only."
    )
    lexical_score_raw: Optional[float] = Field(
        None,
        description="Raw lexical (BM25) score before normalization. Debug only."
    )
    dense_score_norm: Optional[float] = Field(
        None,
        description="Min-max normalized dense score [0,1]. Debug only."
    )
    lexical_score_norm: Optional[float] = Field(
        None,
        description="Min-max normalized lexical score [0,1]. Debug only."
    )
    dense_rank: Optional[int] = Field(
        None,
        description="Rank in dense retrieval results (1-indexed). Debug only."
    )
    lexical_rank: Optional[int] = Field(
        None,
        description="Rank in lexical retrieval results (1-indexed). Debug only."
    )

    # Multi-channel debug fields (only present when SEARCH_DEBUG=true and multi_dense_enabled=true)
    channel_scores: Optional[dict] = Field(
        None,
        description="Per-channel score breakdown for multi-dense retrieval. "
                    "Each channel contains: {raw_score, norm_score, weight, contribution, rank, present}. "
                    "Debug only."
    )

    created_at: Optional[datetime] = None  # Not returned by search RPC

    model_config = {"from_attributes": True}


# Search Schemas
class SearchRequest(BaseModel):
    """Schema for search request.

    Supports optional fusion configuration overrides per request.
    If not provided, server defaults from environment variables are used.
    """

    query: str = Field(..., min_length=1, max_length=1000)
    video_id: Optional[UUID] = None  # If provided, search only in this video
    limit: int = Field(10, ge=1, le=100)
    threshold: float = Field(0.2, ge=0.0, le=1.0)

    # Fusion configuration overrides (optional)
    fusion_method: Optional[str] = Field(
        None,
        description="Fusion method: 'minmax_mean' (default) or 'rrf'. "
                    "minmax_mean normalizes and weights scores; rrf uses rank-based fusion.",
        pattern="^(minmax_mean|rrf)$",
    )

    # Legacy 2-signal mode weights (deprecated in favor of channel_weights)
    weight_dense: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="[LEGACY] Weight for dense (semantic) scores in minmax_mean fusion. "
                    "Prefer using channel_weights instead. Default: 0.7",
    )
    weight_lexical: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="[LEGACY] Weight for lexical (BM25) scores in minmax_mean fusion. "
                    "Prefer using channel_weights instead. Default: 0.3",
    )

    # Multi-channel weights (preferred over legacy weight_dense/weight_lexical)
    channel_weights: Optional[dict[str, float]] = Field(
        None,
        description="Per-channel weights for multi-dense fusion. "
                    "Keys: 'transcript' (spoken word), 'visual' (CLIP), 'summary', 'lexical' (keywords). "
                    "Weights do NOT need to sum to 1.0 - they will be normalized automatically. "
                    "All weights must be in [0, 1] and at least one must be > 0. "
                    "If provided, takes precedence over saved preferences and legacy weight_dense/weight_lexical.",
        examples=[
            {"transcript": 0.5, "visual": 0.3, "summary": 0.1, "lexical": 0.1},
            {"transcript": 0.6, "visual": 0.4, "summary": 0, "lexical": 0},  # Some can be 0
        ],
    )

    # Preferences control
    use_saved_preferences: bool = Field(
        True,
        description="Whether to use saved user preferences if no channel_weights provided. "
                    "Set to False to force system defaults.",
    )

    save_weights: bool = Field(
        False,
        description="If True, saves channel_weights as user's default preferences. "
                    "Requires channel_weights to be provided.",
    )


class SearchResponse(BaseModel):
    """Schema for search response.

    Includes fusion metadata so clients understand how scores were computed.
    """

    query: str
    results: list[VideoSceneResponse]
    total: int
    latency_ms: int

    # Fusion metadata (helps clients understand score semantics)
    fusion_method: Optional[str] = Field(
        None,
        description="Fusion method used: 'minmax_mean', 'rrf', 'dense_only', 'lexical_only', "
                    "'multi_dense_minmax_mean', 'multi_dense_rrf', 'rerank_clip'"
    )
    fusion_weights: Optional[dict] = Field(
        None,
        description="Fusion weights used (after normalization and redistribution). "
                    "Multi-channel: {'transcript': 0.45, 'visual': 0.25, 'summary': 0.1, 'lexical': 0.2}. "
                    "Legacy 2-signal: {'dense': 0.7, 'lexical': 0.3}"
    )

    # Weight resolution metadata (debug)
    weight_source: Optional[str] = Field(
        None,
        description="Source of weights used: 'request' | 'saved' | 'default'"
    )
    weights_requested: Optional[dict] = Field(
        None,
        description="Original weights requested (if different from applied)"
    )
    channels_active: Optional[list[str]] = Field(
        None,
        description="Channels that participated in fusion (had non-empty results)"
    )
    channels_empty: Optional[list[str]] = Field(
        None,
        description="Channels that returned no results (excluded from fusion)"
    )
    channel_score_ranges: Optional[dict] = Field(
        None,
        description="Score ranges per channel: {'transcript': {'min': 0.2, 'max': 0.9}, ...}"
    )
    visual_mode_used: Optional[str] = Field(
        None,
        description="Visual search mode used: 'recall' | 'rerank' | 'skip'"
    )


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
