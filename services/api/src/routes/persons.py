"""Person management endpoints for person-aware search."""
import logging
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user, User
from ..dependencies import get_db, get_storage, get_queue
from ..adapters.database import Database
from ..adapters.supabase import SupabaseStorage
from ..adapters.queue import TaskQueue
from ..domain.schemas import (
    PersonCreateRequest,
    PersonResponse,
    PersonListResponse,
    PersonDetailResponse,
    PersonPhotoUploadUrlResponse,
    PersonPhotoResponse,
)
from ..domain.models import PersonPhotoState

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_person_response(person, photo_counts: dict) -> PersonResponse:
    """Build PersonResponse with photo counts.

    Args:
        person: Person model instance
        photo_counts: Dict with 'ready' and 'total' counts

    Returns:
        PersonResponse schema
    """
    return PersonResponse(
        id=person.id,
        display_name=person.display_name,
        status=person.status,
        ready_photos_count=photo_counts.get("ready", 0),
        total_photos_count=photo_counts.get("total", 0),
        has_query_embedding=person.query_embedding is not None,
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


@router.post("/persons", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def create_person(
    request: PersonCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """
    Create a new person for person-aware search.

    Args:
        request: Person creation request with optional display_name
        current_user: The authenticated user (injected)
        db: Database adapter (injected)

    Returns:
        PersonResponse: The created person

    Raises:
        HTTPException: If person creation fails
    """
    try:
        user_id = UUID(current_user.user_id)

        # Create person
        person = db.create_person(
            owner_id=user_id,
            display_name=request.display_name,
        )

        logger.info(f"Created person {person.id} for user {user_id}")

        # Return response with zero photo counts
        return _build_person_response(person, {"ready": 0, "total": 0})

    except Exception as e:
        logger.error(
            f"Failed to create person for user {current_user.user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create person: {str(e)}",
        )


@router.get("/persons", response_model=PersonListResponse)
async def list_persons(
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """
    List all persons for the current user.

    Args:
        current_user: The authenticated user (injected)
        db: Database adapter (injected)

    Returns:
        PersonListResponse: List of persons with photo counts
    """
    try:
        user_id = UUID(current_user.user_id)

        # Get all persons
        persons = db.list_persons(owner_id=user_id)

        # Build responses with photo counts
        person_responses = []
        for person in persons:
            photos = db.list_person_photos(person_id=person.id)
            ready_count = sum(1 for p in photos if p.state == PersonPhotoState.READY.value)
            total_count = len(photos)

            person_responses.append(
                _build_person_response(
                    person,
                    {"ready": ready_count, "total": total_count},
                )
            )

        logger.info(f"Listed {len(person_responses)} persons for user {user_id}")

        return PersonListResponse(persons=person_responses)

    except Exception as e:
        logger.error(
            f"Failed to list persons for user {current_user.user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list persons: {str(e)}",
        )


@router.get("/persons/{person_id}", response_model=PersonDetailResponse)
async def get_person(
    person_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """
    Get person details with all reference photos.

    Args:
        person_id: UUID of the person
        current_user: The authenticated user (injected)
        db: Database adapter (injected)

    Returns:
        PersonDetailResponse: Person details with photos

    Raises:
        HTTPException:
            - 404: If person not found
            - 403: If user not authorized
    """
    try:
        user_id = UUID(current_user.user_id)

        # Get person and verify ownership
        person = db.get_person(person_id=person_id, owner_id=user_id)
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found",
            )

        # Get all photos
        photos = db.list_person_photos(person_id=person_id)
        ready_count = sum(1 for p in photos if p.state == PersonPhotoState.READY.value)
        total_count = len(photos)

        # Build photo responses
        photo_responses = [
            PersonPhotoResponse(
                id=photo.id,
                person_id=photo.person_id,
                storage_path=photo.storage_path,
                state=photo.state,
                quality_score=photo.quality_score,
                error_message=photo.error_message,
                created_at=photo.created_at,
            )
            for photo in photos
        ]

        logger.info(f"Retrieved person {person_id} with {total_count} photos")

        return PersonDetailResponse(
            person=_build_person_response(
                person,
                {"ready": ready_count, "total": total_count},
            ),
            photos=photo_responses,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get person {person_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get person: {str(e)}",
        )


@router.post(
    "/persons/{person_id}/photos/upload-url",
    response_model=PersonPhotoUploadUrlResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_photo_upload_url(
    person_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    storage: SupabaseStorage = Depends(get_storage),
):
    """
    Generate a signed upload URL for a person reference photo.

    This does NOT create a database record yet. The client should:
    1. Call this endpoint to get the upload URL
    2. Upload the photo to the signed URL
    3. Call POST /persons/{person_id}/photos/{photo_id}/complete

    Args:
        person_id: UUID of the person
        current_user: The authenticated user (injected)
        db: Database adapter (injected)
        storage: Storage adapter (injected)

    Returns:
        PersonPhotoUploadUrlResponse: Contains photo_id, upload_url, and storage_path

    Raises:
        HTTPException:
            - 404: If person not found
            - 403: If user not authorized
    """
    try:
        user_id = UUID(current_user.user_id)

        # Verify person exists and user owns it
        person = db.get_person(person_id=person_id, owner_id=user_id)
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found",
            )

        # Generate deterministic storage path
        # Pattern: persons/{owner_id}/{person_id}/refs/{photo_id}.jpg
        photo_id = uuid4()
        storage_path = f"persons/{user_id}/{person_id}/refs/{photo_id}.jpg"

        # Create signed upload URL using storage adapter
        upload_url = storage.create_signed_upload_url(storage_path)

        logger.info(
            f"Generated upload URL for person {person_id}, photo {photo_id}, "
            f"path={storage_path}"
        )

        return PersonPhotoUploadUrlResponse(
            photo_id=photo_id,
            upload_url=upload_url,
            storage_path=storage_path,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to create upload URL for person {person_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create upload URL: {str(e)}",
        )


@router.post(
    "/persons/{person_id}/photos/{photo_id}/complete",
    status_code=status.HTTP_202_ACCEPTED,
)
async def complete_photo_upload(
    person_id: UUID,
    photo_id: UUID,
    storage_path: str,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    queue: TaskQueue = Depends(get_queue),
):
    """
    Complete photo upload and enqueue processing task.

    This creates the database record and enqueues the worker task.

    Args:
        person_id: UUID of the person
        photo_id: UUID of the photo (from upload-url response)
        storage_path: Storage path (from upload-url response)
        current_user: The authenticated user (injected)
        db: Database adapter (injected)
        queue: Task queue adapter (injected)

    Returns:
        dict: Status message

    Raises:
        HTTPException:
            - 404: If person not found
            - 403: If user not authorized
            - 400: If storage_path validation fails (path injection prevention)
    """
    try:
        user_id = UUID(current_user.user_id)

        # Verify person exists and user owns it
        person = db.get_person(person_id=person_id, owner_id=user_id)
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found",
            )

        # CRITICAL: Validate storage_path to prevent path injection
        # Expected format: persons/{owner_id}/{person_id}/refs/{photo_id}.jpg
        expected_storage_path = f"persons/{user_id}/{person_id}/refs/{photo_id}.jpg"
        if storage_path != expected_storage_path:
            logger.warning(
                f"Storage path mismatch for photo {photo_id}: "
                f"expected={expected_storage_path}, received={storage_path}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid storage_path. Must match the path from upload-url response.",
            )

        # Create database record with UPLOADED state
        photo = db.create_person_reference_photo(
            owner_id=user_id,
            person_id=person_id,
            storage_path=storage_path,
        )

        logger.info(
            f"Created photo record {photo.id} for person {person_id}, "
            f"state={photo.state}"
        )

        # Enqueue processing task
        queue.enqueue_reference_photo_processing(photo_id=photo.id)

        logger.info(f"Enqueued processing for photo {photo.id}")

        return {
            "status": "accepted",
            "message": "Photo upload completed, processing queued",
            "photo_id": photo.id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to complete photo upload for person {person_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete photo upload: {str(e)}",
        )


@router.delete("/persons/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """
    Delete a person and all associated reference photos.

    Note: This is a soft delete (CASCADE) - photos are also deleted.

    Args:
        person_id: UUID of the person
        current_user: The authenticated user (injected)
        db: Database adapter (injected)

    Raises:
        HTTPException:
            - 404: If person not found
            - 403: If user not authorized
    """
    try:
        user_id = UUID(current_user.user_id)

        # Verify person exists and user owns it
        person = db.get_person(person_id=person_id, owner_id=user_id)
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found",
            )

        # Delete person (CASCADE will delete photos)
        db.delete_person(person_id=person_id, owner_id=user_id)

        logger.info(f"Deleted person {person_id} for user {user_id}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete person {person_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete person: {str(e)}",
        )
