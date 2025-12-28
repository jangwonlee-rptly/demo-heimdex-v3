"""Admin metrics endpoints."""
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.middleware import require_admin, User
from ..adapters.database import db
from ..adapters.queue import task_queue
from ..domain.models import VideoStatus
from ..domain.admin_schemas import (
    AdminOverviewResponse,
    ThroughputTimeSeriesResponse,
    ThroughputDataPoint,
    SearchTimeSeriesResponse,
    SearchDataPoint,
    UsersListResponse,
    UserListItem,
    UserDetailResponse,
    VideoItem,
    SearchItem,
    # Phase 2 schemas
    ProcessingLatencyResponse,
    RTFDistributionResponse,
    QueueAnalysisResponse,
    FailuresByStageResponse,
    FailureByStageItem,
    EnhancedThroughputTimeSeriesResponse,
    EnhancedThroughputDataPoint,
    # Admin actions
    ReprocessAllResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_overview(admin: User = Depends(require_admin)):
    """
    Get admin dashboard overview metrics.

    Returns top-level KPIs including:
    - Total videos processed (ready/failed/total)
    - Failure rate percentage
    - Total hours processed
    - Search volume and latency (7d and 30d windows)

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} requesting overview metrics")

    try:
        metrics = db.get_admin_overview_metrics()
        return AdminOverviewResponse(**metrics)
    except Exception as e:
        logger.error(f"Failed to fetch admin overview metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch overview metrics")


@router.get("/timeseries/throughput", response_model=ThroughputTimeSeriesResponse)
async def get_throughput_timeseries(
    range: str = Query("30d", description="Time range (e.g., '30d')"),
    bucket: str = Query("day", description="Time bucket (only 'day' supported in Phase 1)"),
    admin: User = Depends(require_admin)
):
    """
    Get video processing throughput time series.

    Returns daily aggregates of:
    - Number of videos completed
    - Hours of video processed

    Note: Uses videos.updated_at as completion time proxy for Phase 1.

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} requesting throughput timeseries (range={range})")

    # Parse range (simple parsing for Phase 1)
    if not range.endswith("d"):
        raise HTTPException(status_code=400, detail="Range must be in format '30d'")

    try:
        days = int(range[:-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid range format")

    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Range must be between 1d and 365d")

    if bucket != "day":
        raise HTTPException(status_code=400, detail="Only 'day' bucket supported in Phase 1")

    try:
        data = db.get_throughput_timeseries(days=days)
        data_points = [ThroughputDataPoint(**point) for point in data]
        return ThroughputTimeSeriesResponse(data=data_points)
    except Exception as e:
        logger.error(f"Failed to fetch throughput timeseries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch throughput data")


@router.get("/timeseries/search", response_model=SearchTimeSeriesResponse)
async def get_search_timeseries(
    range: str = Query("30d", description="Time range (e.g., '30d')"),
    bucket: str = Query("day", description="Time bucket (only 'day' supported in Phase 1)"),
    admin: User = Depends(require_admin)
):
    """
    Get search volume and latency time series.

    Returns daily aggregates of:
    - Number of searches
    - Average search latency (ms)

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} requesting search timeseries (range={range})")

    # Parse range
    if not range.endswith("d"):
        raise HTTPException(status_code=400, detail="Range must be in format '30d'")

    try:
        days = int(range[:-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid range format")

    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Range must be between 1d and 365d")

    if bucket != "day":
        raise HTTPException(status_code=400, detail="Only 'day' bucket supported in Phase 1")

    try:
        data = db.get_search_timeseries(days=days)
        data_points = [SearchDataPoint(**point) for point in data]
        return SearchTimeSeriesResponse(data=data_points)
    except Exception as e:
        logger.error(f"Failed to fetch search timeseries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch search data")


@router.get("/users", response_model=UsersListResponse)
async def get_users_list(
    range: str = Query("7d", description="Time range for recent metrics (e.g., '7d')"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    sort: str = Query("last_activity", description="Sort column: last_activity, hours_ready, videos_ready, searches_7d"),
    admin: User = Depends(require_admin)
):
    """
    Get paginated list of users with usage metrics.

    Returns per-user aggregates:
    - Total videos and hours processed
    - Recent search activity
    - Last activity timestamp

    Supports sorting and pagination.

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} requesting users list (page={page}, sort={sort})")

    # Parse range
    if not range.endswith("d"):
        raise HTTPException(status_code=400, detail="Range must be in format '7d'")

    try:
        days = int(range[:-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid range format")

    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Range must be between 1d and 365d")

    # Validate sort column
    valid_sorts = ["last_activity", "hours_ready", "videos_ready", "searches_7d"]
    if sort not in valid_sorts:
        raise HTTPException(status_code=400, detail=f"Invalid sort column. Must be one of: {', '.join(valid_sorts)}")

    try:
        result = db.get_admin_users_list(
            days=days,
            page=page,
            page_size=page_size,
            sort_by=sort
        )

        items = [UserListItem(**item) for item in result["items"]]

        return UsersListResponse(
            items=items,
            page=result["page"],
            page_size=result["page_size"],
            total_users=result.get("total_users")
        )
    except Exception as e:
        logger.error(f"Failed to fetch users list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch users list")


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: str,
    admin: User = Depends(require_admin)
):
    """
    Get detailed user information with recent videos and searches.

    Returns:
    - User summary metrics
    - Last 20 videos with status and metadata
    - Last 50 searches with query and latency

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} requesting detail for user {user_id}")

    # Validate UUID format
    try:
        UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    try:
        detail = db.get_admin_user_detail(UUID(user_id), days=7)

        if not detail:
            raise HTTPException(status_code=404, detail="User not found")

        # Parse JSONB arrays from response
        recent_videos = [VideoItem(**v) for v in detail.get("recent_videos", [])]
        recent_searches = [SearchItem(**s) for s in detail.get("recent_searches", [])]

        return UserDetailResponse(
            user_id=detail["user_id"],
            full_name=detail["full_name"],
            videos_total=detail["videos_total"],
            videos_ready=detail["videos_ready"],
            hours_ready=detail["hours_ready"],
            last_activity=detail.get("last_activity"),
            searches_7d=detail["searches_7d"],
            avg_latency_ms_7d=detail.get("avg_latency_ms_7d"),
            recent_videos=recent_videos,
            recent_searches=recent_searches
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user detail for {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch user detail")


# ============================================
# Phase 2: Performance Metrics Endpoints
# ============================================


@router.get("/performance/latency", response_model=ProcessingLatencyResponse)
async def get_processing_latency(
    range: str = Query("30d", description="Time range (e.g., '7d', '30d')"),
    admin: User = Depends(require_admin)
):
    """
    Get processing latency percentiles and queue time (Phase 2).

    Returns:
    - p50/p95/p99 processing time
    - Average queue time
    - Average total time (queue + processing)

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} requesting processing latency (range={range})")

    # Parse range
    if not range.endswith("d"):
        raise HTTPException(status_code=400, detail="Range must be in format '30d'")

    try:
        days = int(range[:-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid range format")

    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Range must be between 1d and 365d")

    try:
        metrics = db.get_admin_processing_latency(days=days)
        return ProcessingLatencyResponse(**metrics)
    except Exception as e:
        logger.error(f"Failed to fetch processing latency: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch processing latency")


@router.get("/performance/rtf", response_model=RTFDistributionResponse)
async def get_rtf_distribution(
    range: str = Query("30d", description="Time range (e.g., '7d', '30d')"),
    admin: User = Depends(require_admin)
):
    """
    Get RTF (Real-Time Factor) distribution (Phase 2).

    RTF = processing_duration / video_duration
    Shows how many seconds of processing per second of video.

    Returns p50/p95/p99 RTF and average durations.

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} requesting RTF distribution (range={range})")

    # Parse range
    if not range.endswith("d"):
        raise HTTPException(status_code=400, detail="Range must be in format '30d'")

    try:
        days = int(range[:-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid range format")

    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Range must be between 1d and 365d")

    try:
        metrics = db.get_admin_rtf_distribution(days=days)
        return RTFDistributionResponse(**metrics)
    except Exception as e:
        logger.error(f"Failed to fetch RTF distribution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch RTF distribution")


@router.get("/performance/queue", response_model=QueueAnalysisResponse)
async def get_queue_analysis(
    range: str = Query("30d", description="Time range (e.g., '7d', '30d')"),
    admin: User = Depends(require_admin)
):
    """
    Get queue vs processing time analysis (Phase 2).

    Separates time waiting in queue from actual processing time.
    Useful for capacity planning and worker scaling decisions.

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} requesting queue analysis (range={range})")

    # Parse range
    if not range.endswith("d"):
        raise HTTPException(status_code=400, detail="Range must be in format '30d'")

    try:
        days = int(range[:-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid range format")

    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Range must be between 1d and 365d")

    try:
        metrics = db.get_admin_queue_analysis(days=days)
        return QueueAnalysisResponse(**metrics)
    except Exception as e:
        logger.error(f"Failed to fetch queue analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch queue analysis")


@router.get("/failures/by-stage", response_model=FailuresByStageResponse)
async def get_failures_by_stage(
    range: str = Query("30d", description="Time range (e.g., '7d', '30d')"),
    admin: User = Depends(require_admin)
):
    """
    Get failures grouped by processing stage (Phase 2).

    Shows which stage failures occur at most frequently.
    Enables failure attribution for reliability analysis.

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} requesting failures by stage (range={range})")

    # Parse range
    if not range.endswith("d"):
        raise HTTPException(status_code=400, detail="Range must be in format '30d'")

    try:
        days = int(range[:-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid range format")

    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Range must be between 1d and 365d")

    try:
        data = db.get_admin_failures_by_stage(days=days)
        items = [FailureByStageItem(**item) for item in data]
        return FailuresByStageResponse(data=items)
    except Exception as e:
        logger.error(f"Failed to fetch failures by stage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch failures by stage")


@router.get("/timeseries/throughput-v2", response_model=EnhancedThroughputTimeSeriesResponse)
async def get_throughput_timeseries_v2(
    range: str = Query("30d", description="Time range (e.g., '7d', '30d')"),
    admin: User = Depends(require_admin)
):
    """
    Get enhanced throughput time series with Phase 2 metrics.

    Uses processing_finished_at for precise timing (replaces updated_at proxy).
    Includes average processing time and RTF per day.

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} requesting enhanced throughput timeseries (range={range})")

    # Parse range
    if not range.endswith("d"):
        raise HTTPException(status_code=400, detail="Range must be in format '30d'")

    try:
        days = int(range[:-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid range format")

    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Range must be between 1d and 365d")

    try:
        data = db.get_admin_throughput_timeseries_v2(days=days)

        # Convert date objects to ISO strings
        data_points = [
            EnhancedThroughputDataPoint(
                day=str(item["day"]),
                videos_ready=item["videos_ready"],
                videos_failed=item["videos_failed"],
                hours_ready=item["hours_ready"],
                avg_processing_s=item.get("avg_processing_s"),
                avg_rtf=item.get("avg_rtf")
            )
            for item in data
        ]

        return EnhancedThroughputTimeSeriesResponse(data=data_points)
    except Exception as e:
        logger.error(f"Failed to fetch enhanced throughput timeseries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch enhanced throughput timeseries")


# ============================================
# Admin Actions Endpoints
# ============================================


@router.post("/reprocess-all", response_model=ReprocessAllResponse, status_code=202)
async def reprocess_all_videos(
    admin: User = Depends(require_admin)
):
    """
    Reprocess all videos in the system.

    This admin-only endpoint will:
    1. Fetch all videos that are not currently being processed
    2. Clear their cached data (transcript, summary, etc.)
    3. Delete existing scenes
    4. Re-enqueue them for processing

    Use this for system-wide reprocessing after algorithm updates or
    to recover from batch failures.

    Returns count of videos queued and skipped.

    Requires admin privileges.
    """
    logger.info(f"Admin {admin.user_id} triggered reprocess-all operation")

    try:
        # Get all videos that are not currently processing
        videos = db.get_all_videos_for_reprocess()

        videos_queued = 0
        videos_skipped = 0

        for video in videos:
            try:
                # Skip if somehow still processing (defensive check)
                if video.status == VideoStatus.PROCESSING:
                    videos_skipped += 1
                    continue

                # Delete existing scenes
                db.delete_scenes_for_video(video.id)

                # Clear video data for reprocess (keeps original language setting)
                db.clear_video_for_reprocess(
                    video_id=video.id,
                    transcript_language=video.transcript_language,
                )

                # Enqueue processing job
                task_queue.enqueue_video_processing(video.id)
                videos_queued += 1

            except Exception as e:
                logger.error(f"Failed to queue video {video.id} for reprocessing: {e}")
                videos_skipped += 1

        logger.info(
            f"Reprocess-all completed: {videos_queued} queued, {videos_skipped} skipped"
        )

        return ReprocessAllResponse(
            status="accepted",
            videos_queued=videos_queued,
            videos_skipped=videos_skipped,
            message=f"Queued {videos_queued} videos for reprocessing, skipped {videos_skipped}",
        )

    except Exception as e:
        logger.error(f"Failed to execute reprocess-all: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to execute reprocess-all operation")
