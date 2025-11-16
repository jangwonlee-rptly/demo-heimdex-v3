"""Database adapter for worker service."""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID
from supabase import create_client, Client

from ..config import settings

logger = logging.getLogger(__name__)


class VideoStatus:
    """Video status enum (matching database enum)."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class Database:
    """Database connection and query handler using Supabase client."""

    def __init__(self, supabase_url: str, supabase_key: str):
        self.client: Client = create_client(supabase_url, supabase_key)

    def get_video(self, video_id: UUID) -> Optional[dict]:
        """Get video by ID."""
        response = (
            self.client.table("videos")
            .select("*")
            .eq("id", str(video_id))
            .execute()
        )

        if not response.data:
            return None
        return response.data[0]

    def update_video_status(
        self,
        video_id: UUID,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update video status."""
        update_data = {
            "status": status,
            "error_message": error_message,
        }

        self.client.table("videos").update(update_data).eq("id", str(video_id)).execute()

    def update_video_metadata(
        self,
        video_id: UUID,
        duration_s: Optional[float] = None,
        frame_rate: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        video_created_at: Optional[datetime] = None,
        thumbnail_url: Optional[str] = None,
    ) -> None:
        """Update video metadata."""
        update_data = {
            "duration_s": duration_s,
            "frame_rate": frame_rate,
            "width": width,
            "height": height,
            "video_created_at": video_created_at.isoformat() if video_created_at else None,
            "thumbnail_url": thumbnail_url,
        }

        self.client.table("videos").update(update_data).eq("id", str(video_id)).execute()

    def create_scene(
        self,
        video_id: UUID,
        index: int,
        start_s: float,
        end_s: float,
        transcript_segment: Optional[str],
        visual_summary: Optional[str],
        combined_text: str,
        embedding: list[float],
        thumbnail_url: Optional[str] = None,
    ) -> UUID:
        """Create a video scene record."""
        # Convert embedding list to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        data = {
            "video_id": str(video_id),
            "index": index,
            "start_s": start_s,
            "end_s": end_s,
            "transcript_segment": transcript_segment,
            "visual_summary": visual_summary,
            "combined_text": combined_text,
            "embedding": embedding_str,
            "thumbnail_url": thumbnail_url,
        }

        response = self.client.table("video_scenes").insert(data).execute()
        return UUID(response.data[0]["id"])

    def delete_scenes_for_video(self, video_id: UUID) -> None:
        """Delete all scenes for a video (used for reprocessing)."""
        self.client.table("video_scenes").delete().eq("video_id", str(video_id)).execute()


# Global database instance
db = Database(settings.supabase_url, settings.supabase_service_role_key)
