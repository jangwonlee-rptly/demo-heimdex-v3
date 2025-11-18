"""Database adapter for Postgres/Supabase."""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID
from supabase import create_client, Client

from ..config import settings
from ..domain.models import UserProfile, Video, VideoScene, VideoStatus

logger = logging.getLogger(__name__)


class Database:
    """Database connection and query handler using Supabase client."""

    def __init__(self, supabase_url: str, supabase_key: str):
        self.client: Client = create_client(supabase_url, supabase_key)

    # User Profile operations
    def get_user_profile(self, user_id: UUID) -> Optional[UserProfile]:
        """Get user profile by user_id."""
        response = (
            self.client.table("user_profiles")
            .select("*")
            .eq("user_id", str(user_id))
            .execute()
        )
        if not response.data:
            return None
        return UserProfile(**response.data[0])

    def create_user_profile(
        self,
        user_id: UUID,
        full_name: str,
        industry: Optional[str] = None,
        job_title: Optional[str] = None,
        preferred_language: str = "ko",
        marketing_consent: bool = False,
    ) -> UserProfile:
        """Create a new user profile."""
        marketing_consent_at = datetime.utcnow() if marketing_consent else None

        data = {
            "user_id": str(user_id),
            "full_name": full_name,
            "industry": industry,
            "job_title": job_title,
            "preferred_language": preferred_language,
            "marketing_consent": marketing_consent,
            "marketing_consent_at": marketing_consent_at.isoformat() if marketing_consent_at else None,
        }

        response = self.client.table("user_profiles").insert(data).execute()
        return UserProfile(**response.data[0])

    def update_user_profile(
        self,
        user_id: UUID,
        full_name: Optional[str] = None,
        industry: Optional[str] = None,
        job_title: Optional[str] = None,
        preferred_language: Optional[str] = None,
        marketing_consent: Optional[bool] = None,
    ) -> Optional[UserProfile]:
        """Update user profile."""
        # First, get the existing profile to check marketing_consent
        existing = self.get_user_profile(user_id)
        if not existing:
            return None

        # Build update data
        update_data = {}

        if full_name is not None:
            update_data["full_name"] = full_name
        if industry is not None:
            update_data["industry"] = industry
        if job_title is not None:
            update_data["job_title"] = job_title
        if preferred_language is not None:
            update_data["preferred_language"] = preferred_language
        if marketing_consent is not None:
            update_data["marketing_consent"] = marketing_consent
            # Set marketing_consent_at if changing from False to True
            if marketing_consent and not existing.marketing_consent:
                update_data["marketing_consent_at"] = datetime.utcnow().isoformat()

        if not update_data:
            return existing

        response = (
            self.client.table("user_profiles")
            .update(update_data)
            .eq("user_id", str(user_id))
            .execute()
        )

        if not response.data:
            return None
        return UserProfile(**response.data[0])

    # Video operations
    def create_video(self, owner_id: UUID, storage_path: str, filename: Optional[str] = None) -> Video:
        """Create a new video record."""
        data = {
            "owner_id": str(owner_id),
            "storage_path": storage_path,
            "status": VideoStatus.PENDING.value,
            "filename": filename,
        }

        response = self.client.table("videos").insert(data).execute()
        row = response.data[0]
        # Convert string UUIDs to UUID objects
        row["id"] = UUID(row["id"])
        row["owner_id"] = UUID(row["owner_id"])
        row["status"] = VideoStatus(row["status"])
        return Video(**row)

    def get_video(self, video_id: UUID) -> Optional[Video]:
        """Get video by ID."""
        response = (
            self.client.table("videos")
            .select("*")
            .eq("id", str(video_id))
            .execute()
        )

        if not response.data:
            return None

        row = response.data[0]
        # Convert string UUIDs to UUID objects
        row["id"] = UUID(row["id"])
        row["owner_id"] = UUID(row["owner_id"])
        row["status"] = VideoStatus(row["status"])
        return Video(**row)

    def list_videos(self, owner_id: UUID) -> list[Video]:
        """List all videos for a user."""
        response = (
            self.client.table("videos")
            .select("*")
            .eq("owner_id", str(owner_id))
            .order("created_at", desc=True)
            .execute()
        )

        videos = []
        for row in response.data:
            # Convert string UUIDs to UUID objects
            row["id"] = UUID(row["id"])
            row["owner_id"] = UUID(row["owner_id"])
            row["status"] = VideoStatus(row["status"])
            videos.append(Video(**row))
        return videos

    def update_video_status(
        self,
        video_id: UUID,
        status: VideoStatus,
        error_message: Optional[str] = None,
    ) -> Optional[Video]:
        """Update video status."""
        update_data = {
            "status": status.value,
            "error_message": error_message,
        }

        response = (
            self.client.table("videos")
            .update(update_data)
            .eq("id", str(video_id))
            .execute()
        )

        if not response.data:
            return None

        row = response.data[0]
        # Convert string UUIDs to UUID objects
        row["id"] = UUID(row["id"])
        row["owner_id"] = UUID(row["owner_id"])
        row["status"] = VideoStatus(row["status"])
        return Video(**row)

    # Search operations
    def search_scenes(
        self,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.5,
        video_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> list[VideoScene]:
        """Search for scenes using vector similarity."""
        # Convert embedding list to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        params = {
            "query_embedding": embedding_str,
            "match_threshold": threshold,
            "match_count": limit,
            "filter_video_id": str(video_id) if video_id else None,
            "filter_user_id": str(user_id) if user_id else None,
        }

        response = self.client.rpc("search_scenes_by_embedding", params).execute()
        return [VideoScene(**row) for row in response.data]

    def log_search_query(
        self,
        user_id: UUID,
        query_text: str,
        results_count: int,
        latency_ms: int,
        video_id: Optional[UUID] = None,
    ) -> None:
        """Log a search query for analytics."""
        data = {
            "user_id": str(user_id),
            "video_id": str(video_id) if video_id else None,
            "query_text": query_text,
            "results_count": results_count,
            "latency_ms": latency_ms,
        }

        self.client.table("search_queries").insert(data).execute()


# Global database instance
db = Database(settings.supabase_url, settings.supabase_service_role_key)
