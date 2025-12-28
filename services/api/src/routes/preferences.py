"""User preferences API endpoints.

Handles user-customizable settings including search weight preferences.
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from ..auth.middleware import get_current_user, User
from ..adapters.database import db
from ..domain.search.weights import validate_user_weights

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])


# Request/Response Schemas

class SearchPreferences(BaseModel):
    """User's saved search preferences."""

    channel_weights: dict[str, float] = Field(
        ...,
        description="Per-channel weights (transcript, visual, summary, lexical). "
                    "Will be normalized to sum to 1.0.",
        examples=[
            {"transcript": 0.5, "visual": 0.3, "summary": 0.1, "lexical": 0.1},
            {"transcript": 0.6, "visual": 0.4, "summary": 0, "lexical": 0},
        ],
    )
    fusion_method: str = Field(
        "minmax_mean",
        pattern="^(minmax_mean|rrf)$",
        description="Fusion method: 'minmax_mean' or 'rrf'",
    )
    visual_mode: str = Field(
        "auto",
        pattern="^(recall|rerank|skip|auto)$",
        description="Visual search mode: 'recall', 'rerank', 'skip', or 'auto'",
    )

    @field_validator("channel_weights")
    @classmethod
    def validate_weights(cls, v):
        """Validate channel weights."""
        is_valid, error_msg = validate_user_weights(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class SearchPreferencesResponse(SearchPreferences):
    """Search preferences with metadata."""

    user_id: UUID
    created_at: datetime
    updated_at: datetime


# Endpoints

@router.get("/search", response_model=Optional[SearchPreferencesResponse])
def get_search_preferences(
    current_user: User = Depends(get_current_user),
):
    """Get user's saved search preferences.

    Returns:
        SearchPreferencesResponse if preferences exist, None otherwise
    """
    try:
        prefs = db.get_user_search_preferences(current_user.user_id)

        if not prefs:
            return None

        # Parse JSONB to response model
        return SearchPreferencesResponse(
            user_id=current_user.user_id,
            channel_weights=prefs.get("weights", {}),
            fusion_method=prefs.get("fusion_method", "minmax_mean"),
            visual_mode=prefs.get("visual_mode", "auto"),
            created_at=prefs.get("created_at"),
            updated_at=prefs.get("updated_at"),
        )

    except Exception as e:
        logger.error(f"Failed to get search preferences for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve search preferences",
        )


@router.put("/search", response_model=SearchPreferencesResponse)
def save_search_preferences(
    preferences: SearchPreferences,
    current_user: User = Depends(get_current_user),
):
    """Save or update user's search preferences.

    Args:
        preferences: Search preferences to save

    Returns:
        Saved preferences with metadata
    """
    try:
        # Normalize weights to ensure they sum to 1.0
        from ..domain.search.weights import normalize_weights

        normalized_weights = normalize_weights(preferences.channel_weights)

        # Build preferences dict
        prefs_dict = {
            "weights": normalized_weights,
            "fusion_method": preferences.fusion_method,
            "visual_mode": preferences.visual_mode,
            "version": 1,
        }

        # Save to database
        saved = db.save_user_search_preferences(
            user_id=current_user.user_id,
            preferences=prefs_dict,
        )

        logger.info(
            f"Saved search preferences for user {current_user.user_id}: "
            f"weights={normalized_weights}, fusion_method={preferences.fusion_method}"
        )

        return SearchPreferencesResponse(
            user_id=current_user.user_id,
            channel_weights=normalized_weights,
            fusion_method=preferences.fusion_method,
            visual_mode=preferences.visual_mode,
            created_at=saved.get("created_at"),
            updated_at=saved.get("updated_at"),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to save search preferences for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save search preferences",
        )


@router.delete("/search")
def reset_search_preferences(
    current_user: User = Depends(get_current_user),
):
    """Reset to system defaults (delete saved preferences).

    Returns:
        Confirmation message
    """
    try:
        db.delete_user_search_preferences(current_user.user_id)

        logger.info(f"Reset search preferences for user {current_user.user_id}")

        return {"message": "Preferences reset to system defaults"}

    except Exception as e:
        logger.error(f"Failed to delete search preferences for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset search preferences",
        )
