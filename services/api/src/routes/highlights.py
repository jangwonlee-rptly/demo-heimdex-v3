"""Highlight reel export endpoints for combining multiple scenes into a single video."""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, status, Depends
from pydantic import BaseModel, Field, field_validator

from ..auth import get_current_user, User
from ..dependencies import get_db, get_queue, get_storage
from ..adapters.database import Database
from ..adapters.queue import TaskQueue
from ..adapters.supabase import SupabaseStorage
from ..domain.models import HighlightJobStatus
from ..exceptions import (
    SceneNotFoundException,
    VideoNotFoundException,
    InvalidInputException,
    ResourceNotFoundException,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/highlights")


# ============================================================================
# Request/Response Schemas
# ============================================================================


class HighlightSceneInput(BaseModel):
    """Input schema for a single scene in the highlight reel."""

    scene_id: str = Field(..., description="UUID of the scene")
    video_id: str = Field(..., description="UUID of the parent video (verified server-side)")
    start_s: float = Field(..., ge=0, description="Start time in seconds")
    end_s: float = Field(..., gt=0, description="End time in seconds")

    @field_validator("end_s")
    @classmethod
    def end_must_be_after_start(cls, v: float, info) -> float:
        """Validate that end_s is greater than start_s."""
        start = info.data.get("start_s", 0)
        if v <= start:
            raise ValueError("end_s must be greater than start_s")
        return v


class HighlightExportOptions(BaseModel):
    """Optional export configuration."""

    container: str = Field(default="mp4", description="Output container format")
    video_codec: str = Field(default="h264", description="Video codec")
    audio_codec: str = Field(default="aac", description="Audio codec")
    target_height: int = Field(default=720, ge=360, le=1080, description="Target video height")


class HighlightExportRequest(BaseModel):
    """Request body for creating a highlight export job."""

    scenes: list[HighlightSceneInput] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Ordered list of scenes to include in the highlight reel",
    )
    title: Optional[str] = Field(None, max_length=200, description="Optional title for the export")
    options: Optional[HighlightExportOptions] = Field(
        default_factory=HighlightExportOptions,
        description="Export configuration options",
    )


class HighlightExportEnqueueResponse(BaseModel):
    """Response for successful job creation."""

    job_id: str
    status: str = "queued"


class HighlightJobProgress(BaseModel):
    """Progress information for a running job."""

    stage: Optional[str] = None  # "cutting", "concat", "upload"
    done: int = 0
    total: int = 0


class HighlightJobOutput(BaseModel):
    """Output information for a completed job."""

    mp4_url: Optional[str] = None
    storage_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    duration_s: Optional[float] = None
    resolution: Optional[str] = None
    expires_at: Optional[datetime] = None


class HighlightJobError(BaseModel):
    """Error information for a failed job."""

    message: str
    detail: Optional[str] = None


class HighlightExportJobResponse(BaseModel):
    """Response for job status query."""

    job_id: str
    status: str
    progress: Optional[HighlightJobProgress] = None
    output: Optional[HighlightJobOutput] = None
    error: Optional[HighlightJobError] = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/export", response_model=HighlightExportEnqueueResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_highlight_export(
    request: HighlightExportRequest,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    task_queue: TaskQueue = Depends(get_queue),
):
    """
    Create a new highlight reel export job.

    Validates scene ownership, creates a job record, and enqueues
    the export task for background processing.

    Args:
        request: Export configuration with ordered scene list.
        user: Authenticated user.

    Returns:
        HighlightExportEnqueueResponse: Job ID and status (202 Accepted).

    Raises:
        InvalidInputException: Empty scenes list or invalid time ranges.
        SceneNotFoundException: Scene not found.
        VideoNotFoundException: Parent video not found or not owned by user.
    """
    user_id = UUID(user.user_id)

    if not request.scenes:
        raise InvalidInputException(
            message="At least one scene is required",
            details={"scenes": "empty"},
        )

    # Validate all scenes and their ownership
    validated_scenes = []
    total_duration = 0.0

    for idx, scene_input in enumerate(request.scenes):
        try:
            scene_uuid = UUID(scene_input.scene_id)
            video_uuid = UUID(scene_input.video_id)
        except ValueError as e:
            raise InvalidInputException(
                message=f"Invalid UUID at scene index {idx}",
                details={"index": idx, "error": str(e)},
            )

        # Get scene from database
        scene = db.get_scene(scene_uuid)
        if not scene:
            raise SceneNotFoundException(scene_input.scene_id)

        # Verify scene belongs to the claimed video
        if scene.video_id != video_uuid:
            raise InvalidInputException(
                message=f"Scene {scene_input.scene_id} does not belong to video {scene_input.video_id}",
                details={"index": idx},
            )

        # Get parent video to verify ownership
        video = db.get_video(video_uuid)
        if not video:
            raise VideoNotFoundException(scene_input.video_id)

        # Verify user owns the video
        if video.owner_id != user_id:
            # Don't leak that video exists - report as not found
            raise VideoNotFoundException(scene_input.video_id)

        # Validate time range within scene bounds
        if scene_input.start_s < scene.start_s:
            scene_input.start_s = scene.start_s
        if scene_input.end_s > scene.end_s:
            scene_input.end_s = scene.end_s

        # Ensure positive duration after clamping
        duration = scene_input.end_s - scene_input.start_s
        if duration <= 0:
            raise InvalidInputException(
                message=f"Invalid time range at scene index {idx}",
                details={
                    "index": idx,
                    "start_s": scene_input.start_s,
                    "end_s": scene_input.end_s,
                },
            )

        total_duration += duration

        validated_scenes.append({
            "scene_id": str(scene_uuid),
            "video_id": str(video_uuid),
            "video_storage_path": video.storage_path,  # Needed by worker
            "start_s": scene_input.start_s,
            "end_s": scene_input.end_s,
        })

    # Build request JSONB
    request_data = {
        "scenes": validated_scenes,
        "total_duration_s": total_duration,
        "scene_count": len(validated_scenes),
        "title": request.title,
        "options": request.options.model_dump() if request.options else {},
    }

    # Create job in database
    job = db.create_highlight_export_job(
        user_id=user_id,
        request_data=request_data,
    )

    logger.info(
        f"Created highlight export job {job.id} for user {user_id} "
        f"({len(validated_scenes)} scenes, {total_duration:.1f}s total)",
        extra={
            "job_id": str(job.id),
            "user_id": str(user_id),
            "scene_count": len(validated_scenes),
            "total_duration_s": total_duration,
        },
    )

    # Enqueue worker task
    task_queue.enqueue_highlight_export(job_id=job.id)

    return HighlightExportEnqueueResponse(
        job_id=str(job.id),
        status="queued",
    )


@router.get("/jobs/{job_id}", response_model=HighlightExportJobResponse)
async def get_highlight_job_status(
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    storage: SupabaseStorage = Depends(get_storage),
):
    """
    Get the status of a highlight export job.

    If the job is complete, includes the download URL.

    Args:
        job_id: UUID of the job.
        user: Authenticated user.

    Returns:
        HighlightExportJobResponse: Job status and metadata.

    Raises:
        ResourceNotFoundException: Job not found or not owned by user.
    """
    user_id = UUID(user.user_id)

    job = db.get_highlight_export_job(job_id)
    if not job:
        raise ResourceNotFoundException("Highlight export job", str(job_id))

    # Verify ownership
    if job.user_id != user_id:
        raise ResourceNotFoundException("Highlight export job", str(job_id))

    # Build progress response
    progress = None
    if job.progress:
        progress = HighlightJobProgress(
            stage=job.progress.get("stage"),
            done=job.progress.get("done", 0),
            total=job.progress.get("total", 0),
        )

    # Build output response with signed URL if completed
    output = None
    if job.status == HighlightJobStatus.DONE and job.output:
        mp4_url = None
        if job.output.get("storage_path"):
            # Generate presigned URL valid for 1 hour
            mp4_url = storage.get_presigned_url(job.output["storage_path"], expires_in=3600)

        output = HighlightJobOutput(
            mp4_url=mp4_url,
            storage_path=job.output.get("storage_path"),
            file_size_bytes=job.output.get("file_size_bytes"),
            duration_s=job.output.get("duration_s"),
            resolution=job.output.get("resolution"),
            expires_at=job.output.get("expires_at"),
        )

    # Build error response
    error = None
    if job.status == HighlightJobStatus.ERROR and job.error:
        error = HighlightJobError(
            message=job.error.get("message", "Unknown error"),
            detail=job.error.get("detail"),
        )

    return HighlightExportJobResponse(
        job_id=str(job.id),
        status=job.status.value,
        progress=progress,
        output=output,
        error=error,
        created_at=job.created_at or datetime.now(timezone.utc),
        updated_at=job.updated_at or datetime.now(timezone.utc),
    )
