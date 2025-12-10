"""Database adapter for Postgres/Supabase."""
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from supabase import create_client, Client

from ..config import settings
from ..domain.models import (
    UserProfile,
    Video,
    VideoScene,
    VideoStatus,
    SceneExport,
    ExportStatus,
    AspectRatioStrategy,
    OutputQuality,
)

logger = logging.getLogger(__name__)


class Database:
    """Database connection and query handler using Supabase client."""

    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize the database client.

        Args:
            supabase_url: The URL of the Supabase instance.
            supabase_key: The API key for accessing Supabase.
        """
        self.client: Client = create_client(supabase_url, supabase_key)

    # User Profile operations
    def get_user_profile(self, user_id: UUID) -> Optional[UserProfile]:
        """Get user profile by user_id.

        Args:
            user_id: The UUID of the user.

        Returns:
            Optional[UserProfile]: The user profile if found, otherwise None.
        """
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
        scene_detector_preferences: Optional[dict] = None,
    ) -> UserProfile:
        """Create a new user profile.

        Args:
            user_id: The UUID of the user.
            full_name: The user's full name.
            industry: The user's industry (optional).
            job_title: The user's job title (optional).
            preferred_language: The user's preferred language (default: "ko").
            marketing_consent: Whether the user consented to marketing emails (default: False).
            scene_detector_preferences: Custom scene detector thresholds (optional).

        Returns:
            UserProfile: The created user profile.
        """
        marketing_consent_at = datetime.utcnow() if marketing_consent else None

        data = {
            "user_id": str(user_id),
            "full_name": full_name,
            "industry": industry,
            "job_title": job_title,
            "preferred_language": preferred_language,
            "marketing_consent": marketing_consent,
            "marketing_consent_at": marketing_consent_at.isoformat() if marketing_consent_at else None,
            "scene_detector_preferences": scene_detector_preferences,
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
        scene_detector_preferences: Optional[dict] = None,
    ) -> Optional[UserProfile]:
        """Update user profile.

        Args:
            user_id: The UUID of the user.
            full_name: The new full name (optional).
            industry: The new industry (optional).
            job_title: The new job title (optional).
            preferred_language: The new preferred language (optional).
            marketing_consent: The new marketing consent status (optional).
            scene_detector_preferences: Custom scene detector thresholds (optional).

        Returns:
            Optional[UserProfile]: The updated user profile if successful, otherwise None.
        """
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
        if scene_detector_preferences is not None:
            update_data["scene_detector_preferences"] = scene_detector_preferences

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
        """Create a new video record.

        Args:
            owner_id: The UUID of the user who owns the video.
            storage_path: The path where the video is stored.
            filename: The original filename of the uploaded video (optional).

        Returns:
            Video: The created video record.
        """
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
        """Get video by ID.

        Args:
            video_id: The UUID of the video.

        Returns:
            Optional[Video]: The video record if found, otherwise None.
        """
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
        """List all videos for a user.

        Args:
            owner_id: The UUID of the user.

        Returns:
            list[Video]: A list of videos owned by the user, ordered by creation time.
        """
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
        """Update video status.

        Args:
            video_id: The UUID of the video.
            status: The new status of the video.
            error_message: An error message if the status is FAILED (optional).

        Returns:
            Optional[Video]: The updated video record if successful, otherwise None.
        """
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

    def get_scene(self, scene_id: UUID) -> Optional[VideoScene]:
        """Get a single scene by ID.

        Args:
            scene_id: The UUID of the scene.

        Returns:
            Optional[VideoScene]: The scene if found, otherwise None.
        """
        response = (
            self.client.table("video_scenes")
            .select("id,video_id,index,start_s,end_s,transcript_segment,visual_summary,combined_text,thumbnail_url,visual_description,visual_entities,visual_actions,tags,created_at")
            .eq("id", str(scene_id))
            .execute()
        )

        if not response.data:
            return None

        row = response.data[0]
        # Convert string UUIDs to UUID objects
        row["id"] = UUID(row["id"])
        row["video_id"] = UUID(row["video_id"])
        return VideoScene(**row)

    def get_video_scenes(self, video_id: UUID) -> list[VideoScene]:
        """Get all scenes for a video, ordered by index.

        Args:
            video_id: The UUID of the video.

        Returns:
            list[VideoScene]: A list of scenes for the video.
        """
        response = (
            self.client.table("video_scenes")
            .select("id,video_id,index,start_s,end_s,transcript_segment,visual_summary,combined_text,thumbnail_url,visual_description,visual_entities,visual_actions,tags,created_at")
            .eq("video_id", str(video_id))
            .order("index", desc=False)
            .execute()
        )

        scenes = []
        for row in response.data:
            # Convert string UUIDs to UUID objects
            row["id"] = UUID(row["id"])
            row["video_id"] = UUID(row["video_id"])
            scenes.append(VideoScene(**row))
        return scenes

    def delete_scenes_for_video(self, video_id: UUID) -> None:
        """Delete all scenes for a video (used for reprocessing).

        Args:
            video_id: The UUID of the video.

        Returns:
            None: This function does not return a value.
        """
        self.client.table("video_scenes").delete().eq("video_id", str(video_id)).execute()

    def clear_video_for_reprocess(
        self,
        video_id: UUID,
        transcript_language: Optional[str] = None,
    ) -> Optional[Video]:
        """Clear video data for reprocessing with optional language override.

        This clears:
        - full_transcript (to force re-transcription)
        - video_summary
        - has_rich_semantics flag
        - Sets transcript_language for forced language on re-transcription

        Args:
            video_id: The UUID of the video.
            transcript_language: Optional ISO-639-1 language code for forced transcription.

        Returns:
            Optional[Video]: The updated video record if successful, otherwise None.
        """
        update_data = {
            "full_transcript": None,
            "video_summary": None,
            "has_rich_semantics": False,
            "transcript_language": transcript_language,
            "status": VideoStatus.PENDING.value,
            "error_message": None,
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
        """Search for scenes using vector similarity.

        Args:
            query_embedding: The vector embedding of the search query.
            limit: Maximum number of results to return (default: 10).
            threshold: Similarity threshold (0.0 to 1.0, default: 0.5).
            video_id: Filter by specific video ID (optional).
            user_id: Filter by specific user ID (optional).

        Returns:
            list[VideoScene]: A list of matching video scenes.
        """
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
        """Log a search query for analytics.

        Args:
            user_id: The UUID of the user making the query.
            query_text: The search query text.
            results_count: Number of results returned.
            latency_ms: Search latency in milliseconds.
            video_id: The specific video ID searched, if any (optional).

        Returns:
            None: This function does not return a value.
        """
        data = {
            "user_id": str(user_id),
            "video_id": str(video_id) if video_id else None,
            "query_text": query_text,
            "results_count": results_count,
            "latency_ms": latency_ms,
        }

        self.client.table("search_queries").insert(data).execute()

    # Scene Export operations
    def create_scene_export(
        self,
        scene_id: UUID,
        user_id: UUID,
        aspect_ratio_strategy: AspectRatioStrategy,
        output_quality: OutputQuality,
    ) -> SceneExport:
        """Create a new scene export request.

        Args:
            scene_id: UUID of the scene to export.
            user_id: UUID of the user creating the export.
            aspect_ratio_strategy: How to handle aspect ratio conversion.
            output_quality: Video quality preset.

        Returns:
            SceneExport: The created export record.
        """
        data = {
            "scene_id": str(scene_id),
            "user_id": str(user_id),
            "aspect_ratio_strategy": aspect_ratio_strategy.value,
            "output_quality": output_quality.value,
            "status": ExportStatus.PENDING.value,
        }

        response = self.client.table("scene_exports").insert(data).execute()
        return self._map_export_response(response.data[0])

    def get_scene_export(self, export_id: UUID) -> Optional[SceneExport]:
        """Get a scene export by ID.

        Args:
            export_id: UUID of the export.

        Returns:
            Optional[SceneExport]: The export if found, otherwise None.
        """
        response = (
            self.client.table("scene_exports")
            .select("*")
            .eq("id", str(export_id))
            .execute()
        )

        if not response.data:
            return None

        return self._map_export_response(response.data[0])

    def update_scene_export(
        self,
        export_id: UUID,
        status: Optional[ExportStatus] = None,
        storage_path: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        duration_s: Optional[float] = None,
        resolution: Optional[str] = None,
        error_message: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> SceneExport:
        """Update a scene export record.

        Args:
            export_id: UUID of the export to update.
            status: New status (optional).
            storage_path: Path to exported file (optional).
            file_size_bytes: File size in bytes (optional).
            duration_s: Duration in seconds (optional).
            resolution: Video resolution (optional).
            error_message: Error message if failed (optional).
            completed_at: Completion timestamp (optional).

        Returns:
            SceneExport: The updated export record.
        """
        update_data = {}
        if status is not None:
            update_data["status"] = status.value
        if storage_path is not None:
            update_data["storage_path"] = storage_path
        if file_size_bytes is not None:
            update_data["file_size_bytes"] = file_size_bytes
        if duration_s is not None:
            update_data["duration_s"] = duration_s
        if resolution is not None:
            update_data["resolution"] = resolution
        if error_message is not None:
            update_data["error_message"] = error_message
        if completed_at is not None:
            update_data["completed_at"] = completed_at.isoformat()

        response = (
            self.client.table("scene_exports")
            .update(update_data)
            .eq("id", str(export_id))
            .execute()
        )

        return self._map_export_response(response.data[0])

    def count_user_exports_since(self, user_id: UUID, since: datetime) -> int:
        """Count how many exports a user has created since a given datetime.

        Args:
            user_id: UUID of the user.
            since: Count exports created after this timestamp.

        Returns:
            int: Number of exports created since the given datetime.
        """
        response = (
            self.client.table("scene_exports")
            .select("id", count="exact")
            .eq("user_id", str(user_id))
            .gte("created_at", since.isoformat())
            .execute()
        )

        return response.count or 0

    def get_oldest_user_export_today(self, user_id: UUID) -> Optional[SceneExport]:
        """Get the user's oldest export from the last 24 hours.

        Useful for calculating when rate limit will reset.

        Args:
            user_id: UUID of the user.

        Returns:
            Optional[SceneExport]: The oldest export if found, otherwise None.
        """
        since = datetime.utcnow() - timedelta(hours=24)

        response = (
            self.client.table("scene_exports")
            .select("*")
            .eq("user_id", str(user_id))
            .gte("created_at", since.isoformat())
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return self._map_export_response(response.data[0])

    def get_expired_exports(self) -> list[SceneExport]:
        """Get all expired exports for cleanup.

        Returns:
            list[SceneExport]: List of expired exports with status 'completed'.
        """
        now = datetime.utcnow()

        response = (
            self.client.table("scene_exports")
            .select("*")
            .eq("status", ExportStatus.COMPLETED.value)
            .lt("expires_at", now.isoformat())
            .execute()
        )

        return [self._map_export_response(row) for row in response.data]

    def delete_scene_export(self, export_id: UUID) -> None:
        """Delete a scene export record.

        Args:
            export_id: UUID of the export to delete.
        """
        self.client.table("scene_exports").delete().eq("id", str(export_id)).execute()

    def _map_export_response(self, row: dict) -> SceneExport:
        """Map database row to SceneExport model.

        Args:
            row: Database row as dictionary.

        Returns:
            SceneExport: Mapped export model.
        """
        return SceneExport(
            id=UUID(row["id"]),
            scene_id=UUID(row["scene_id"]),
            user_id=UUID(row["user_id"]),
            aspect_ratio_strategy=AspectRatioStrategy(row["aspect_ratio_strategy"]),
            output_quality=OutputQuality(row["output_quality"]),
            status=ExportStatus(row["status"]),
            error_message=row.get("error_message"),
            storage_path=row.get("storage_path"),
            file_size_bytes=row.get("file_size_bytes"),
            duration_s=row.get("duration_s"),
            resolution=row.get("resolution"),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
            expires_at=datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None,
        )


# Global database instance
db = Database(settings.supabase_url, settings.supabase_service_role_key)
