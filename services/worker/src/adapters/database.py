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

    def get_user_profile(self, user_id: UUID) -> Optional[dict]:
        """Get user profile by user_id."""
        response = (
            self.client.table("user_profiles")
            .select("*")
            .eq("user_id", str(user_id))
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]

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

    def save_transcript(self, video_id: UUID, transcript: str) -> None:
        """
        Save transcript to database as checkpoint.

        This allows us to skip expensive Whisper transcription on retry.

        Args:
            video_id: Video ID
            transcript: Full video transcript
        """
        logger.info(f"Saving transcript checkpoint for video {video_id} ({len(transcript)} chars)")
        self.client.table("videos").update({"full_transcript": transcript}).eq("id", str(video_id)).execute()

    def get_cached_transcript(self, video_id: UUID) -> Optional[str]:
        """
        Get cached transcript if it exists.

        Args:
            video_id: Video ID

        Returns:
            Cached transcript or None if not found
        """
        video = self.get_video(video_id)
        if video and "full_transcript" in video and video["full_transcript"]:
            logger.info(f"Found cached transcript for video {video_id} ({len(video['full_transcript'])} chars)")
            return video["full_transcript"]
        return None

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

    def get_scene(self, video_id: UUID, index: int) -> Optional[dict]:
        """
        Get a specific scene by video_id and index.

        Args:
            video_id: Video ID
            index: Scene index

        Returns:
            Scene data if exists, None otherwise
        """
        response = (
            self.client.table("video_scenes")
            .select("*")
            .eq("video_id", str(video_id))
            .eq("index", index)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]

    def get_existing_scene_indices(self, video_id: UUID) -> set[int]:
        """
        Get set of scene indices that already exist for a video.

        Args:
            video_id: Video ID

        Returns:
            Set of scene indices that have been processed
        """
        response = (
            self.client.table("video_scenes")
            .select("index")
            .eq("video_id", str(video_id))
            .execute()
        )
        return {row["index"] for row in response.data}

    def delete_scenes_for_video(self, video_id: UUID) -> None:
        """Delete all scenes for a video (used for reprocessing)."""
        self.client.table("video_scenes").delete().eq("video_id", str(video_id)).execute()


# Global database instance
db = Database(settings.supabase_url, settings.supabase_service_role_key)
