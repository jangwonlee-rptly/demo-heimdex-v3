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
    ) -> UserProfile:
        """Create a new user profile.

        Args:
            user_id: The UUID of the user.
            full_name: The user's full name.
            industry: The user's industry (optional).
            job_title: The user's job title (optional).
            preferred_language: The user's preferred language (default: "ko").
            marketing_consent: Whether the user consented to marketing emails (default: False).

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
        """Update user profile.

        Args:
            user_id: The UUID of the user.
            full_name: The new full name (optional).
            industry: The new industry (optional).
            job_title: The new job title (optional).
            preferred_language: The new preferred language (optional).
            marketing_consent: The new marketing consent status (optional).

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

    def search_scenes_weighted(
        self,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.5,
        video_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        asr_weight: float = 0.4,
        image_weight: float = 0.4,
        metadata_weight: float = 0.2,
    ) -> list[VideoScene]:
        """Search for scenes using vector similarity with weighted signal boosting.

        Since we currently use combined embeddings (ASR + Visual + Metadata mixed),
        this method applies weights as post-processing boosting factors based on
        content availability in each scene:
        - ASR boost: Applied if transcript_segment exists
        - Visual boost: Applied if visual_summary or visual_description exists
        - Metadata boost: Applied if tags exist

        Args:
            query_embedding: The vector embedding of the search query.
            limit: Maximum number of results to return (default: 10).
            threshold: Similarity threshold (0.0 to 1.0, default: 0.5).
            video_id: Filter by specific video ID (optional).
            user_id: Filter by specific user ID (optional).
            asr_weight: Weight for ASR/transcript signal (0.0 to 1.0).
            image_weight: Weight for visual/image signal (0.0 to 1.0).
            metadata_weight: Weight for metadata signal (0.0 to 1.0).

        Returns:
            list[VideoScene]: A list of matching video scenes, re-ranked by weighted score.

        Note:
            This is a simplified implementation using combined embeddings.
            For true multi-signal search, store separate embeddings per signal
            and compute weighted similarity in the database query.
        """
        # Get initial results with a larger limit to allow for re-ranking
        initial_limit = min(limit * 3, 100)  # Get more results for re-ranking
        scenes = self.search_scenes(
            query_embedding=query_embedding,
            limit=initial_limit,
            threshold=threshold,
            video_id=video_id,
            user_id=user_id,
        )

        # Apply weighted boosting to similarity scores
        for scene in scenes:
            if scene.similarity is None:
                continue

            # Calculate boost multiplier based on content availability and weights
            boost = 1.0
            available_signals = []

            # ASR boost: Check if transcript exists
            if scene.transcript_segment and len(scene.transcript_segment.strip()) > 0:
                available_signals.append('asr')
                boost += asr_weight * 0.5  # Up to 50% boost from ASR

            # Visual boost: Check if visual content exists
            if (scene.visual_summary and len(scene.visual_summary.strip()) > 0) or \
               (scene.visual_description and len(scene.visual_description.strip()) > 0):
                available_signals.append('visual')
                boost += image_weight * 0.5  # Up to 50% boost from visual

            # Metadata boost: Check if tags exist
            if scene.tags and len(scene.tags) > 0:
                available_signals.append('metadata')
                boost += metadata_weight * 0.5  # Up to 50% boost from metadata

            # Normalize boost based on number of available signals
            if available_signals:
                # Penalize scenes missing preferred signals
                signal_coverage = len(available_signals) / 3.0  # Max 3 signals
                boost = 1.0 + (boost - 1.0) * signal_coverage

            # Apply boost to similarity score
            scene.similarity = min(scene.similarity * boost, 1.0)

        # Re-sort by weighted similarity
        scenes.sort(key=lambda s: s.similarity if s.similarity else 0.0, reverse=True)

        # Return top results after re-ranking
        return scenes[:limit]

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


# Global database instance
db = Database(settings.supabase_url, settings.supabase_service_role_key)
