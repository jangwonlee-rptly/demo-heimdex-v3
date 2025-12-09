"""User profile endpoints."""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user, User
from ..domain.schemas import (
    UserProfileCreate,
    UserProfileUpdate,
    UserProfileResponse,
    UserInfoResponse,
)
from ..adapters.database import db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get basic user info from JWT.

    Args:
        current_user: The authenticated user (injected).

    Returns:
        UserInfoResponse: Basic user information including ID and email.
    """
    return UserInfoResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        role=current_user.role,
    )


@router.get("/me/profile", response_model=UserProfileResponse | None)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get the current user's profile.

    Args:
        current_user: The authenticated user (injected).

    Returns:
        Optional[UserProfileResponse]: The user's profile data, or None if it doesn't exist.
    """
    user_id = UUID(current_user.user_id)
    profile = db.get_user_profile(user_id)

    if not profile:
        return None

    return UserProfileResponse(
        user_id=profile.user_id,
        full_name=profile.full_name,
        industry=profile.industry,
        job_title=profile.job_title,
        preferred_language=profile.preferred_language,
        marketing_consent=profile.marketing_consent,
        marketing_consent_at=profile.marketing_consent_at,
        scene_detector_preferences=profile.scene_detector_preferences,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.post("/me/profile", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_user_profile(
    profile_data: UserProfileCreate,
    current_user: User = Depends(get_current_user),
):
    """
    Create or update the current user's profile.

    This endpoint handles both profile creation (onboarding) and updates.

    Args:
        profile_data: The profile data to create or update.
        current_user: The authenticated user (injected).

    Returns:
        UserProfileResponse: The created or updated profile data.

    Raises:
        HTTPException: If the profile creation/update fails.
    """
    user_id = UUID(current_user.user_id)

    # Convert scene_detector_preferences to dict if provided
    scene_prefs_dict = None
    if profile_data.scene_detector_preferences:
        scene_prefs_dict = profile_data.scene_detector_preferences.model_dump(exclude_none=True)

    # Check if profile already exists
    existing_profile = db.get_user_profile(user_id)

    if existing_profile:
        # Update existing profile
        logger.info(f"Updating profile for user {user_id}")
        profile = db.update_user_profile(
            user_id=user_id,
            full_name=profile_data.full_name,
            industry=profile_data.industry,
            job_title=profile_data.job_title,
            preferred_language=profile_data.preferred_language,
            marketing_consent=profile_data.marketing_consent,
            scene_detector_preferences=scene_prefs_dict,
        )
    else:
        # Create new profile
        logger.info(f"Creating profile for user {user_id}")
        profile = db.create_user_profile(
            user_id=user_id,
            full_name=profile_data.full_name,
            industry=profile_data.industry,
            job_title=profile_data.job_title,
            preferred_language=profile_data.preferred_language,
            marketing_consent=profile_data.marketing_consent,
            scene_detector_preferences=scene_prefs_dict,
        )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create/update profile",
        )

    return UserProfileResponse(
        user_id=profile.user_id,
        full_name=profile.full_name,
        industry=profile.industry,
        job_title=profile.job_title,
        preferred_language=profile.preferred_language,
        marketing_consent=profile.marketing_consent,
        marketing_consent_at=profile.marketing_consent_at,
        scene_detector_preferences=profile.scene_detector_preferences,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
