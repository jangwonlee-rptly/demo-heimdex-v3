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
    """Get basic user info from JWT."""
    return UserInfoResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        role=current_user.role,
    )


@router.get("/me/profile", response_model=UserProfileResponse | None)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get the current user's profile.

    Returns None if profile doesn't exist (first-time user).
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
        marketing_consent=profile.marketing_consent,
        marketing_consent_at=profile.marketing_consent_at,
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
    """
    user_id = UUID(current_user.user_id)

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
            marketing_consent=profile_data.marketing_consent,
        )
    else:
        # Create new profile
        logger.info(f"Creating profile for user {user_id}")
        profile = db.create_user_profile(
            user_id=user_id,
            full_name=profile_data.full_name,
            industry=profile_data.industry,
            job_title=profile_data.job_title,
            marketing_consent=profile_data.marketing_consent,
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
        marketing_consent=profile.marketing_consent,
        marketing_consent_at=profile.marketing_consent_at,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
