"""Scene export endpoints for YouTube Shorts feature."""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, status, Depends
from pydantic import BaseModel, Field

from ..auth import get_current_user, User
from ..adapters.database import db
from ..domain.models import AspectRatioStrategy, OutputQuality, ExportStatus
from ..exceptions import (
    SceneNotFoundException,
    VideoNotFoundException,
    ExportLimitExceededException,
    ExportExpiredException,
    SceneTooLongException,
    InvalidInputException,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# YouTube Shorts maximum duration (180 seconds = 3 minutes)
MAX_SHORTS_DURATION_S = 180
DAILY_EXPORT_LIMIT = 10


# ============================================================================
# Request/Response Schemas
# ============================================================================


class CreateExportRequest(BaseModel):
    """Request body for creating a scene export."""

    aspect_ratio_strategy: AspectRatioStrategy = Field(
        default=AspectRatioStrategy.CENTER_CROP,
        description="How to handle aspect ratio conversion to 9:16",
    )
    output_quality: OutputQuality = Field(
        default=OutputQuality.HIGH,
        description="Video quality preset",
    )


class ExportResponse(BaseModel):
    """Response model for export requests."""

    export_id: str
    scene_id: str
    status: ExportStatus
    aspect_ratio_strategy: AspectRatioStrategy
    output_quality: OutputQuality
    download_url: str | None = Field(None, description="Presigned download URL (valid for 1 hour)")
    file_size_bytes: int | None = None
    duration_s: float | None = None
    resolution: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    expires_at: datetime


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/scenes/{scene_id}/export-short", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_scene_export(
    scene_id: UUID,
    request: CreateExportRequest,
    user: User = Depends(get_current_user),
):
    """
    Create a new YouTube Shorts export for a scene.

    Rate limited to 10 exports per day per user.
    Scene duration must be ≤ 180 seconds.

    Args:
        scene_id: UUID of the scene to export.
        request: Export configuration (aspect ratio strategy, quality).
        user: Authenticated user.

    Returns:
        ExportResponse: Export status and metadata (202 Accepted).

    Raises:
        SceneNotFoundException: Scene not found.
        VideoNotFoundException: Parent video not found.
        SceneTooLongException: Scene duration > 180 seconds.
        ExportLimitExceededException: User exceeded daily limit (10/day).
    """
    user_id = UUID(user.user_id)

    # Check rate limit (10 exports per day)
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    export_count = db.count_user_exports_since(user_id, since)

    if export_count >= DAILY_EXPORT_LIMIT:
        # Calculate hours until reset
        oldest_export = db.get_oldest_user_export_today(user_id)
        if oldest_export and oldest_export.created_at:
            hours_until_reset = int((oldest_export.created_at + timedelta(hours=24) - now).total_seconds() / 3600) + 1
        else:
            hours_until_reset = 24

        raise ExportLimitExceededException(
            message=f"Daily export limit reached ({DAILY_EXPORT_LIMIT}/day). Try again in {hours_until_reset} hours.",
            current_count=export_count,
            limit=DAILY_EXPORT_LIMIT,
            hours_until_reset=hours_until_reset,
        )

    # Get scene and validate
    scene = db.get_scene(scene_id)
    if not scene:
        raise SceneNotFoundException(str(scene_id))

    # Get parent video to verify ownership and status
    video = db.get_video(scene.video_id)
    if not video:
        raise VideoNotFoundException(str(scene.video_id))

    # Verify user owns the video
    if video.owner_id != user_id:
        raise SceneNotFoundException(str(scene_id))  # Don't leak that scene exists

    # Validate scene duration (YouTube Shorts max 180 seconds)
    scene_duration = scene.end_s - scene.start_s
    if scene_duration > MAX_SHORTS_DURATION_S:
        raise SceneTooLongException(
            scene_duration_s=scene_duration,
            max_duration_s=MAX_SHORTS_DURATION_S,
        )

    # Validate aspect ratio strategy
    if request.aspect_ratio_strategy == AspectRatioStrategy.SMART_CROP:
        raise InvalidInputException(
            message="Smart crop is not yet implemented. Please use 'center_crop' or 'letterbox'.",
            details={"aspect_ratio_strategy": request.aspect_ratio_strategy.value},
        )

    # Create export record
    export = db.create_scene_export(
        scene_id=scene_id,
        user_id=user_id,
        aspect_ratio_strategy=request.aspect_ratio_strategy,
        output_quality=request.output_quality,
    )

    logger.info(
        f"Created export {export.id} for scene {scene_id} (user: {user_id})",
        extra={
            "export_id": str(export.id),
            "scene_id": str(scene_id),
            "user_id": str(user_id),
            "aspect_ratio_strategy": request.aspect_ratio_strategy.value,
            "output_quality": request.output_quality.value,
        },
    )

    # Enqueue worker task to process export
    from ..adapters.queue import task_queue
    task_queue.enqueue_scene_export(scene_id=scene_id, export_id=export.id)

    return ExportResponse(
        export_id=str(export.id),
        scene_id=str(scene_id),
        status=export.status,
        aspect_ratio_strategy=export.aspect_ratio_strategy,
        output_quality=export.output_quality,
        download_url=None,  # Not ready yet
        created_at=export.created_at or now,
        expires_at=export.expires_at or now + timedelta(hours=24),
    )


@router.get("/exports/{export_id}", response_model=ExportResponse)
async def get_export_status(
    export_id: UUID,
    user: User = Depends(get_current_user),
):
    """
    Get export status and download URL.

    If export is completed and not expired, returns presigned download URL valid for 1 hour.

    Args:
        export_id: UUID of the export.
        user: Authenticated user.

    Returns:
        ExportResponse: Export status and metadata.

    Raises:
        ExportExpiredException: Export has expired (> 24 hours old).
        ResourceNotFoundException: Export not found or not owned by user.
    """
    user_id = UUID(user.user_id)

    # Get export
    export = db.get_scene_export(export_id)
    if not export:
        raise ExportExpiredException(str(export_id))

    # Verify ownership
    if export.user_id != user_id:
        raise ExportExpiredException(str(export_id))  # Don't leak that export exists

    # Check if expired
    now = datetime.now(timezone.utc)
    if export.expires_at and export.expires_at < now:
        raise ExportExpiredException(str(export_id))

    # Generate presigned download URL if export is completed
    download_url = None
    if export.status == ExportStatus.COMPLETED and export.storage_path:
        from ..adapters.supabase import storage
        # Generate presigned URL valid for 1 hour
        download_url = storage.get_presigned_url(export.storage_path, expires_in=3600)

    return ExportResponse(
        export_id=str(export.id),
        scene_id=str(export.scene_id),
        status=export.status,
        aspect_ratio_strategy=export.aspect_ratio_strategy,
        output_quality=export.output_quality,
        download_url=download_url,
        file_size_bytes=export.file_size_bytes,
        duration_s=export.duration_s,
        resolution=export.resolution,
        error_message=export.error_message,
        created_at=export.created_at or now,
        completed_at=export.completed_at,
        expires_at=export.expires_at or now + timedelta(hours=24),
    )
