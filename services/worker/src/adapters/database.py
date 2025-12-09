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
        """Initialize the database client.

        Args:
            supabase_url: The URL of the Supabase instance.
            supabase_key: The API key for accessing Supabase.
        """
        self.client: Client = create_client(supabase_url, supabase_key)

    def get_user_profile(self, user_id: UUID) -> Optional[dict]:
        """Get user profile by user_id.

        Args:
            user_id: The UUID of the user.

        Returns:
            Optional[dict]: The user profile data if found, otherwise None.
        """
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
        """Get video by ID.

        Args:
            video_id: The UUID of the video.

        Returns:
            Optional[dict]: The video data if found, otherwise None.
        """
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
        """Update video status.

        Args:
            video_id: The UUID of the video.
            status: The new status.
            error_message: Optional error message.

        Returns:
            None: This function does not return a value.
        """
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
        video_summary: Optional[str] = None,
        has_rich_semantics: Optional[bool] = None,
        # EXIF metadata fields
        exif_metadata: Optional[dict] = None,
        location_latitude: Optional[float] = None,
        location_longitude: Optional[float] = None,
        location_name: Optional[str] = None,
        camera_make: Optional[str] = None,
        camera_model: Optional[str] = None,
    ) -> None:
        """Update video metadata.

        Args:
            video_id: The UUID of the video.
            duration_s: Duration of the video in seconds.
            frame_rate: Frame rate of the video.
            width: Width of the video resolution.
            height: Height of the video resolution.
            video_created_at: Creation timestamp from video metadata.
            thumbnail_url: URL of the video thumbnail.
            video_summary: AI-generated video summary (v2).
            has_rich_semantics: Flag indicating rich semantics processing (v2).
            exif_metadata: JSONB EXIF metadata (GPS, camera, recording settings).
            location_latitude: GPS latitude (denormalized for queries).
            location_longitude: GPS longitude (denormalized for queries).
            location_name: Reverse-geocoded location name (denormalized for queries).
            camera_make: Camera manufacturer (denormalized for queries).
            camera_model: Camera model (denormalized for queries).

        Returns:
            None: This function does not return a value.
        """
        update_data = {
            "duration_s": duration_s,
            "frame_rate": frame_rate,
            "width": width,
            "height": height,
            "video_created_at": video_created_at.isoformat() if video_created_at else None,
            "thumbnail_url": thumbnail_url,
            "video_summary": video_summary,
            "has_rich_semantics": has_rich_semantics,
            # EXIF metadata fields
            "exif_metadata": exif_metadata,
            "location_latitude": location_latitude,
            "location_longitude": location_longitude,
            "location_name": location_name,
            "camera_make": camera_make,
            "camera_model": camera_model,
        }

        # Remove None values to avoid overwriting existing data
        update_data = {k: v for k, v in update_data.items() if v is not None}

        if update_data:
            self.client.table("videos").update(update_data).eq("id", str(video_id)).execute()

    def save_transcript(self, video_id: UUID, transcript: str) -> None:
        """
        Save transcript to database as checkpoint.

        This allows us to skip expensive Whisper transcription on retry.

        Args:
            video_id: Video ID
            transcript: Full video transcript

        Returns:
            None: This function does not return a value.
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
        visual_description: Optional[str] = None,
        visual_entities: Optional[list[str]] = None,
        visual_actions: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        # Sidecar v2 metadata fields
        sidecar_version: Optional[str] = None,
        search_text: Optional[str] = None,
        embedding_metadata: Optional[dict] = None,
        needs_reprocess: bool = False,
        processing_stats: Optional[dict] = None,
    ) -> UUID:
        """Create a video scene record.

        Args:
            video_id: The UUID of the video.
            index: The scene index.
            start_s: Start time of the scene in seconds.
            end_s: End time of the scene in seconds.
            transcript_segment: The transcript segment for the scene.
            visual_summary: The visual summary of the scene.
            combined_text: The combined text for embedding.
            embedding: The embedding vector.
            thumbnail_url: The URL of the scene thumbnail.
            visual_description: Richer 1-2 sentence description (v2).
            visual_entities: List of main entities detected (v2).
            visual_actions: List of actions detected (v2).
            tags: Normalized tags for filtering (v2).
            sidecar_version: Schema version for migration tracking (v2).
            search_text: Optimized text for embedding generation (v2).
            embedding_metadata: Info about embedding model/generation (v2).
            needs_reprocess: Flag indicating scene may benefit from reprocessing (v2).
            processing_stats: Debug stats about sidecar generation (v2).

        Returns:
            UUID: The UUID of the created scene.
        """
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
            "visual_description": visual_description,
            "visual_entities": visual_entities or [],
            "visual_actions": visual_actions or [],
            "tags": tags or [],
            # Sidecar v2 metadata fields
            "sidecar_version": sidecar_version or "v2",
            "search_text": search_text,
            "embedding_metadata": embedding_metadata,
            "needs_reprocess": needs_reprocess,
            "processing_stats": processing_stats,
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

    def get_scene_descriptions(self, video_id: UUID) -> list[str]:
        """
        Get all visual descriptions for a video's scenes, ordered by index.

        This is used to generate video-level summaries.

        Args:
            video_id: Video ID

        Returns:
            List of scene descriptions in order (empty strings for scenes without descriptions)
        """
        response = (
            self.client.table("video_scenes")
            .select("index, visual_description")
            .eq("video_id", str(video_id))
            .order("index")
            .execute()
        )

        # Extract descriptions, filtering out empty/null ones
        descriptions = [
            row.get("visual_description", "").strip()
            for row in response.data
            if row.get("visual_description")
        ]

        return descriptions

    def delete_scenes_for_video(self, video_id: UUID) -> None:
        """Delete all scenes for a video (used for reprocessing).

        Args:
            video_id: The UUID of the video.

        Returns:
            None: This function does not return a value.
        """
        self.client.table("video_scenes").delete().eq("video_id", str(video_id)).execute()


# Global database instance
db = Database(settings.supabase_url, settings.supabase_service_role_key)
