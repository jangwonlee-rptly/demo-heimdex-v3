"""Video management endpoints."""
import logging
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status, Query

from ..auth import get_current_user, User
from ..domain.schemas import (
    VideoUploadUrlResponse,
    VideoUploadedRequest,
    VideoResponse,
    VideoListResponse,
)
from ..adapters.database import db
from ..adapters.supabase import storage
from ..adapters.queue import task_queue

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/videos/upload-url", response_model=VideoUploadUrlResponse, status_code=status.HTTP_201_CREATED)
async def create_upload_url(
    file_extension: str = Query("mp4", description="File extension (e.g., mp4, mov)"),
    filename: str = Query(..., description="Original filename"),
    current_user: User = Depends(get_current_user),
):
    """
    Create a video record and return storage path for client-side upload.

    The client should upload the video file using Supabase client library,
    then call POST /videos/{video_id}/uploaded to trigger processing.
    """
    user_id = UUID(current_user.user_id)

    # Generate storage path (user_id/video_id.extension)
    video_id = uuid4()
    storage_path = f"{user_id}/{video_id}.{file_extension}"

    # Create video record in database with filename
    video = db.create_video(owner_id=user_id, storage_path=storage_path, filename=filename)

    logger.info(f"Created video {video.id} for user {user_id}, filename={filename}, storage_path={storage_path}")

    return VideoUploadUrlResponse(
        video_id=video.id,
        storage_path=storage_path,
    )


@router.post("/videos/{video_id}/uploaded", status_code=status.HTTP_202_ACCEPTED)
async def mark_video_uploaded(
    video_id: UUID,
    request: VideoUploadedRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Mark a video as uploaded and enqueue it for processing.

    This should be called after the client has successfully uploaded
    the video file to the upload URL.
    """
    user_id = UUID(current_user.user_id)

    # Get video and verify ownership
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    if video.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this video",
        )

    # Enqueue processing job
    task_queue.enqueue_video_processing(video_id)

    logger.info(f"Enqueued processing for video {video_id}")

    return {"status": "accepted", "message": "Video queued for processing"}


@router.post("/videos/{video_id}/process", status_code=status.HTTP_202_ACCEPTED)
async def trigger_video_processing(
    video_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger processing for a pending video.

    Useful for retrying failed uploads or processing videos that got stuck.
    """
    user_id = UUID(current_user.user_id)

    # Get video and verify ownership
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    if video.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this video",
        )

    # Enqueue processing job
    task_queue.enqueue_video_processing(video_id)

    logger.info(f"Manually triggered processing for video {video_id}")

    return {"status": "accepted", "message": "Video queued for processing"}


@router.get("/videos", response_model=VideoListResponse)
async def list_videos(current_user: User = Depends(get_current_user)):
    """List all videos for the current user."""
    user_id = UUID(current_user.user_id)
    videos = db.list_videos(user_id)

    return VideoListResponse(
        videos=[
            VideoResponse(
                id=v.id,
                owner_id=v.owner_id,
                storage_path=v.storage_path,
                status=v.status,
                filename=v.filename,
                duration_s=v.duration_s,
                frame_rate=v.frame_rate,
                width=v.width,
                height=v.height,
                video_created_at=v.video_created_at,
                thumbnail_url=v.thumbnail_url,
                error_message=v.error_message,
                created_at=v.created_at,
                updated_at=v.updated_at,
            )
            for v in videos
        ],
        total=len(videos),
    )


@router.get("/videos/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """Get details for a specific video."""
    user_id = UUID(current_user.user_id)

    video = db.get_video(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    if video.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this video",
        )

    return VideoResponse(
        id=video.id,
        owner_id=video.owner_id,
        storage_path=video.storage_path,
        status=video.status,
        filename=video.filename,
        duration_s=video.duration_s,
        frame_rate=video.frame_rate,
        width=video.width,
        height=video.height,
        video_created_at=video.video_created_at,
        thumbnail_url=video.thumbnail_url,
        error_message=video.error_message,
        created_at=video.created_at,
        updated_at=video.updated_at,
    )
