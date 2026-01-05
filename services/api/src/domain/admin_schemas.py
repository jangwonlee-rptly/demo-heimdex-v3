"""Admin metrics API schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID


class AdminOverviewResponse(BaseModel):
    """Admin dashboard overview metrics."""

    videos_ready_total: int = Field(..., description="Total number of successfully processed videos")
    videos_failed_total: int = Field(..., description="Total number of failed videos")
    videos_total: int = Field(..., description="Total number of all videos")
    failure_rate_pct: float = Field(..., description="Failure rate percentage (0-100)")
    hours_ready_total: float = Field(..., description="Total hours of successfully processed video content")
    searches_7d: int = Field(..., description="Total searches in last 7 days")
    avg_search_latency_ms_7d: Optional[float] = Field(None, description="Average search latency in ms (last 7 days)")
    searches_30d: int = Field(..., description="Total searches in last 30 days")
    avg_search_latency_ms_30d: Optional[float] = Field(None, description="Average search latency in ms (last 30 days)")


class ThroughputDataPoint(BaseModel):
    """Single data point for throughput time series."""

    day: str = Field(..., description="Date in YYYY-MM-DD format")
    videos_ready: int = Field(..., description="Number of videos completed on this day")
    hours_ready: float = Field(..., description="Hours of video processed on this day")


class ThroughputTimeSeriesResponse(BaseModel):
    """Throughput time series data."""

    data: List[ThroughputDataPoint] = Field(..., description="Time series data points")


class SearchDataPoint(BaseModel):
    """Single data point for search time series."""

    day: str = Field(..., description="Date in YYYY-MM-DD format")
    searches: int = Field(..., description="Number of searches on this day")
    avg_latency_ms: Optional[float] = Field(None, description="Average search latency in ms on this day")


class SearchTimeSeriesResponse(BaseModel):
    """Search time series data."""

    data: List[SearchDataPoint] = Field(..., description="Time series data points")


class UserListItem(BaseModel):
    """Single user item in admin users list."""

    user_id: str = Field(..., description="User UUID")
    full_name: str = Field(..., description="User full name")
    videos_total: int = Field(..., description="Total videos uploaded by user")
    videos_ready: int = Field(..., description="Successfully processed videos")
    hours_ready: float = Field(..., description="Total hours processed")
    last_activity: Optional[datetime] = Field(None, description="Most recent activity timestamp")
    searches_7d: int = Field(..., description="Searches in last 7 days")
    avg_latency_ms_7d: Optional[float] = Field(None, description="Average search latency in ms (last 7 days)")


class UsersListResponse(BaseModel):
    """Paginated users list response."""

    items: List[UserListItem] = Field(..., description="List of users for this page")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_users: Optional[int] = Field(None, description="Total number of users (optional)")


class VideoItem(BaseModel):
    """Single video item for user detail."""

    id: str = Field(..., description="Video UUID")
    filename: Optional[str] = Field(None, description="Original filename")
    status: str = Field(..., description="Video status")
    duration_s: Optional[float] = Field(None, description="Video duration in seconds")
    updated_at: datetime = Field(..., description="Last update timestamp")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class SearchItem(BaseModel):
    """Single search item for user detail."""

    query_text: str = Field(..., description="Search query")
    created_at: datetime = Field(..., description="Search timestamp")
    latency_ms: Optional[int] = Field(None, description="Search latency in ms")
    results_count: Optional[int] = Field(None, description="Number of results returned")
    video_id: Optional[str] = Field(None, description="Video ID if single-video search")


class UserDetailResponse(BaseModel):
    """Detailed user information for drilldown."""

    user_id: str = Field(..., description="User UUID")
    full_name: str = Field(..., description="User full name")
    videos_total: int = Field(..., description="Total videos uploaded")
    videos_ready: int = Field(..., description="Successfully processed videos")
    hours_ready: float = Field(..., description="Total hours processed")
    last_activity: Optional[datetime] = Field(None, description="Most recent activity timestamp")
    searches_7d: int = Field(..., description="Searches in last 7 days")
    avg_latency_ms_7d: Optional[float] = Field(None, description="Average search latency in ms (last 7 days)")
    recent_videos: List[VideoItem] = Field(..., description="Last 20 videos")
    recent_searches: List[SearchItem] = Field(..., description="Last 50 searches")


# ============================================
# Phase 2: Performance Metrics Schemas
# ============================================


class ProcessingLatencyResponse(BaseModel):
    """Processing latency percentiles and queue time."""

    videos_measured: int = Field(..., description="Number of videos with timing data")
    avg_processing_ms: Optional[float] = Field(None, description="Average processing time in ms")
    p50_processing_ms: Optional[float] = Field(None, description="Median processing time in ms")
    p95_processing_ms: Optional[float] = Field(None, description="95th percentile processing time in ms")
    p99_processing_ms: Optional[float] = Field(None, description="99th percentile processing time in ms")
    avg_queue_ms: Optional[float] = Field(None, description="Average queue time in ms")
    avg_total_ms: Optional[float] = Field(None, description="Average total time (queue + processing) in ms")


class RTFDistributionResponse(BaseModel):
    """RTF (Real-Time Factor) distribution."""

    videos_measured: int = Field(..., description="Number of videos with RTF data")
    avg_rtf: Optional[float] = Field(None, description="Average RTF (processing_time / video_duration)")
    p50_rtf: Optional[float] = Field(None, description="Median RTF")
    p95_rtf: Optional[float] = Field(None, description="95th percentile RTF")
    p99_rtf: Optional[float] = Field(None, description="99th percentile RTF")
    avg_video_duration_s: Optional[float] = Field(None, description="Average video duration in seconds")
    avg_processing_duration_s: Optional[float] = Field(None, description="Average processing duration in seconds")


class QueueAnalysisResponse(BaseModel):
    """Queue vs processing time analysis."""

    videos_measured: int = Field(..., description="Number of videos with queue timing data")
    avg_queue_time_s: Optional[float] = Field(None, description="Average time waiting in queue (seconds)")
    avg_processing_time_s: Optional[float] = Field(None, description="Average processing time (seconds)")
    avg_total_time_s: Optional[float] = Field(None, description="Average total time (seconds)")
    queue_time_pct: Optional[float] = Field(None, description="Queue time as percentage of total")
    processing_time_pct: Optional[float] = Field(None, description="Processing time as percentage of total")


class FailureByStageItem(BaseModel):
    """Single failure stage data point."""

    processing_stage: str = Field(..., description="Processing stage where failure occurred")
    failure_count: int = Field(..., description="Number of failures at this stage")
    failure_pct: float = Field(..., description="Percentage of all failures at this stage")


class FailuresByStageResponse(BaseModel):
    """Failures attribution by processing stage."""

    data: List[FailureByStageItem] = Field(..., description="Failures grouped by stage")


class EnhancedThroughputDataPoint(BaseModel):
    """Enhanced throughput data point with Phase 2 metrics."""

    day: str = Field(..., description="Date in YYYY-MM-DD format")
    videos_ready: int = Field(..., description="Videos completed on this day")
    videos_failed: int = Field(..., description="Videos failed on this day")
    hours_ready: float = Field(..., description="Hours of video processed")
    avg_processing_s: Optional[float] = Field(None, description="Average processing time in seconds")
    avg_rtf: Optional[float] = Field(None, description="Average RTF for this day")


class EnhancedThroughputTimeSeriesResponse(BaseModel):
    """Enhanced throughput time series with Phase 2 metrics."""

    data: List[EnhancedThroughputDataPoint] = Field(..., description="Time series data points")


# ============================================
# Admin Actions Schemas
# ============================================


class ReprocessAllResponse(BaseModel):
    """Response for reprocess all videos operation."""

    status: str = Field(..., description="Operation status ('accepted')")
    videos_queued: int = Field(..., description="Number of videos queued for reprocessing")
    videos_skipped: int = Field(..., description="Number of videos skipped (already processing)")
    message: str = Field(..., description="Human-readable status message")


class ReprocessEmbeddingsRequest(BaseModel):
    """Request for reprocessing embeddings with latest methods."""

    scope: str = Field(..., description="Scope: 'video', 'owner', or 'all'")
    video_id: Optional[str] = Field(None, description="Video ID (required for scope='video')")
    owner_id: Optional[str] = Field(None, description="Owner ID (required for scope='owner')")
    force: bool = Field(False, description="Force regeneration even if embeddings exist")


class ReprocessEmbeddingsResponse(BaseModel):
    """Response for reprocess embeddings operation."""

    status: str = Field(..., description="Operation status ('queued')")
    spec_version: str = Field(..., description="Embedding spec version being used")
    scope: str = Field(..., description="Reprocessing scope")
    video_count: Optional[int] = Field(None, description="Estimated number of videos to reprocess")
    message: str = Field(..., description="Human-readable status message")
