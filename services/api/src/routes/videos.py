"""Video management endpoints."""
import logging
import re
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status, Query

from ..auth import get_current_user, User
from ..domain.schemas import (
    VideoUploadUrlResponse,
    VideoUploadedRequest,
    VideoResponse,
    VideoListResponse,
    VideoDetailsResponse,
    VideoSceneResponse,
)
from ..adapters.database import db
from ..adapters.supabase import storage
from ..adapters.queue import task_queue

logger = logging.getLogger(__name__)

router = APIRouter()


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename to prevent issues with special characters.

    - Preserves Unicode characters (Korean, etc.)
    - Removes or replaces problematic characters
    - Truncates to max length

    Args:
        filename: Original filename
        max_length: Maximum allowed length

    Returns:
        Sanitized filename
    """
    # Remove null bytes
    filename = filename.replace('\x00', '')

    # Replace problematic characters that can cause issues in storage/filesystem
    # But preserve most Unicode including Korean characters
    problematic_chars = {
        '\n': ' ',
        '\r': ' ',
        '\t': ' ',
        '|': '-',
        '<': '-',
        '>': '-',
        ':': '-',
        '"': "'",
        '\\': '-',
        '/': '-',
        '?': '',
        '*': '',
        '\0': '',
    }

    for old_char, new_char in problematic_chars.items():
        filename = filename.replace(old_char, new_char)

    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)

    # Trim whitespace
    filename = filename.strip()

    # Truncate to max length (accounting for multibyte UTF-8 characters)
    if len(filename.encode('utf-8')) > max_length:
        # Truncate by bytes, then decode
        filename_bytes = filename.encode('utf-8')[:max_length]
        # Remove incomplete multibyte sequences at the end
        filename = filename_bytes.decode('utf-8', errors='ignore')

    # Ensure filename is not empty
    if not filename or filename == '':
        filename = 'untitled'

    return filename


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

    Args:
        file_extension: The file extension of the video (default: "mp4").
        filename: The original filename of the video.
        current_user: The authenticated user (injected).

    Returns:
        VideoUploadUrlResponse: Contains the video ID and storage path.

    Raises:
        HTTPException: If creating the upload URL or video record fails.
    """
    try:
        user_id = UUID(current_user.user_id)

        # Sanitize filename to handle Unicode and special characters
        sanitized_filename = sanitize_filename(filename)

        if sanitized_filename != filename:
            logger.info(
                f"Filename was sanitized: original length={len(filename)}, "
                f"sanitized length={len(sanitized_filename)}"
            )

        # Generate storage path (user_id/video_id.extension)
        video_id = uuid4()
        storage_path = f"{user_id}/{video_id}.{file_extension}"

        # Create video record in database with sanitized filename
        video = db.create_video(
            owner_id=user_id,
            storage_path=storage_path,
            filename=sanitized_filename
        )

        logger.info(
            f"Created video {video.id} for user {user_id}, "
            f"storage_path={storage_path}"
        )

        return VideoUploadUrlResponse(
            video_id=video.id,
            storage_path=storage_path,
        )

    except Exception as e:
        logger.error(
            f"Failed to create upload URL for user {current_user.user_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create upload URL: {str(e)}"
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

    Args:
        video_id: The UUID of the video.
        request: The request body (empty).
        current_user: The authenticated user (injected).

    Returns:
        dict: Status message indicating the video was queued.

    Raises:
        HTTPException:
            - 404: If the video is not found.
            - 403: If the user is not authorized to access the video.
            - 500: If enqueuing the task fails.
    """
    try:
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

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(
            f"Failed to enqueue video {video_id} for processing: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue video for processing: {str(e)}"
        )


@router.post("/videos/{video_id}/process", status_code=status.HTTP_202_ACCEPTED)
async def trigger_video_processing(
    video_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger processing for a pending video.

    Useful for retrying failed uploads or processing videos that got stuck.

    Args:
        video_id: The UUID of the video.
        current_user: The authenticated user (injected).

    Returns:
        dict: Status message indicating the video was queued.

    Raises:
        HTTPException:
            - 404: If the video is not found.
            - 403: If the user is not authorized to access the video.
            - 500: If enqueuing the task fails.
    """
    try:
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

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(
            f"Failed to trigger processing for video {video_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger video processing: {str(e)}"
        )


@router.get("/videos", response_model=VideoListResponse)
async def list_videos(current_user: User = Depends(get_current_user)):
    """List all videos for the current user.

    Args:
        current_user: The authenticated user (injected).

    Returns:
        VideoListResponse: A list of videos and the total count.
    """
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
    """Get details for a specific video.

    Args:
        video_id: The UUID of the video.
        current_user: The authenticated user (injected).

    Returns:
        VideoResponse: The video details.

    Raises:
        HTTPException:
            - 404: If the video is not found.
            - 403: If the user is not authorized to access the video.
    """
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


@router.get("/videos/{video_id}/details", response_model=VideoDetailsResponse)
async def get_video_details(
    video_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information for a specific video, including all scenes.

    This endpoint returns comprehensive video data for the details page:
    - Video metadata (filename, duration, resolution, etc.)
    - Full transcript (if available)
    - All scenes with their summaries, transcripts, and thumbnails

    Args:
        video_id: The UUID of the video.
        current_user: The authenticated user (injected).

    Returns:
        VideoDetailsResponse: Detailed video information including all scenes.

    Raises:
        HTTPException:
            - 404: If the video is not found.
            - 403: If the user is not authorized to access the video.
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

    # Get all scenes for the video
    scenes = db.get_video_scenes(video_id)

    return VideoDetailsResponse(
        video=VideoResponse(
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
        ),
        full_transcript=video.full_transcript,
        scenes=[
            VideoSceneResponse(
                id=scene.id,
                video_id=scene.video_id,
                index=scene.index,
                start_s=scene.start_s,
                end_s=scene.end_s,
                transcript_segment=scene.transcript_segment,
                visual_summary=scene.visual_summary,
                combined_text=scene.combined_text,
                thumbnail_url=scene.thumbnail_url,
                created_at=scene.created_at,
            )
            for scene in scenes
        ],
        total_scenes=len(scenes),
    )
