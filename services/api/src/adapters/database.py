"""Database adapter for Postgres/Supabase."""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID
from supabase import create_client, Client

from ..domain.models import (
    UserProfile,
    Video,
    VideoScene,
    VideoStatus,
    SceneExport,
    ExportStatus,
    AspectRatioStrategy,
    OutputQuality,
    HighlightExportJob,
    HighlightJobStatus,
    Person,
    PersonReferencePhoto,
)

logger = logging.getLogger(__name__)


def deserialize_embedding(value: Any) -> Optional[list[float]]:
    """Safely deserialize pgvector embedding from Supabase/PostgREST.

    Supabase Python client returns pgvector columns as JSON-serialized strings,
    not as auto-parsed Python lists. This helper ensures consistent deserialization
    across all embedding fields.

    Args:
        value: Raw value from database (may be JSON string, list, or None).

    Returns:
        list[float] if valid embedding, None if value is None.

    Raises:
        TypeError: If value is an unexpected type.
        ValueError: If JSON parsing fails or result is not a list.

    Examples:
        >>> deserialize_embedding(None)
        None
        >>> deserialize_embedding([0.1, 0.2, 0.3])
        [0.1, 0.2, 0.3]
        >>> deserialize_embedding('[0.1, 0.2, 0.3]')
        [0.1, 0.2, 0.3]
    """
    if value is None:
        return None

    if isinstance(value, list):
        # Already deserialized (e.g., from mock or different client)
        return value

    if isinstance(value, str):
        # PostgREST serialization: vector(N) -> JSON string
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError(f"Parsed embedding is not a list: {type(parsed).__name__}")
            return parsed
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse embedding JSON: {e}") from e

    raise TypeError(f"Unexpected embedding type: {type(value).__name__}")


class Database:
    """Database connection and query handler using Supabase client."""

    def __init__(self, supabase_url: str, supabase_key: str, search_debug: bool = False):
        """Initialize the database client.

        Args:
            supabase_url: The URL of the Supabase instance.
            supabase_key: The API key for accessing Supabase.
            search_debug: Whether to enable debug logging for search queries.
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        self.search_debug = search_debug

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

    def update_video_queued_at(self, video_id: UUID, queued_at: datetime) -> None:
        """Set the queued timestamp when job is enqueued (Phase 2).

        Args:
            video_id: The UUID of the video.
            queued_at: Timestamp when job was enqueued.

        Returns:
            None: This function does not return a value.
        """
        update_data = {
            "queued_at": queued_at.isoformat(),
            "processing_stage": "queued",
        }
        self.client.table("videos").update(update_data).eq("id", str(video_id)).execute()

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
        """Search for scenes using vector similarity (legacy single-embedding).

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

    def search_scenes_transcript_embedding(
        self,
        query_embedding: list[float],
        user_id: UUID,
        video_id: Optional[UUID] = None,
        match_count: int = 200,
        threshold: float = 0.2,
    ) -> list[tuple[str, int, float]]:
        """Search scenes by transcript embedding (multi-dense channel).

        Args:
            query_embedding: The vector embedding of the search query.
            user_id: User ID for tenant scoping (required).
            video_id: Filter by specific video ID (optional).
            match_count: Maximum number of results to return.
            threshold: Similarity threshold (0.0 to 1.0).

        Returns:
            list[tuple[str, int, float]]: List of (scene_id, rank, similarity) tuples.
        """
        # Convert embedding list to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        params = {
            "query_embedding": embedding_str,
            "match_threshold": threshold,
            "match_count": match_count,
            "filter_video_id": str(video_id) if video_id else None,
            "filter_user_id": str(user_id),  # Always required for tenancy
        }

        try:
            response = self.client.rpc("search_scenes_by_transcript_embedding", params).execute()
            results = []
            for rank, row in enumerate(response.data, start=1):
                results.append((str(row["id"]), rank, float(row["similarity"])))

            if self.search_debug and results:
                logger.info(f"Transcript search: {len(results)} results, top score={results[0][2]:.4f}")
            else:
                logger.debug(f"Transcript search: {len(results)} results")

            return results
        except Exception as e:
            logger.error(f"Transcript embedding search failed: {e}", exc_info=True)
            return []

    def search_scenes_visual_embedding(
        self,
        query_embedding: list[float],
        user_id: UUID,
        video_id: Optional[UUID] = None,
        match_count: int = 200,
        threshold: float = 0.15,
    ) -> list[tuple[str, int, float]]:
        """Search scenes by visual embedding (multi-dense channel).

        Args:
            query_embedding: The vector embedding of the search query.
            user_id: User ID for tenant scoping (required).
            video_id: Filter by specific video ID (optional).
            match_count: Maximum number of results to return.
            threshold: Similarity threshold (0.0 to 1.0).

        Returns:
            list[tuple[str, int, float]]: List of (scene_id, rank, similarity) tuples.
        """
        # Convert embedding list to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        params = {
            "query_embedding": embedding_str,
            "match_threshold": threshold,
            "match_count": match_count,
            "filter_video_id": str(video_id) if video_id else None,
            "filter_user_id": str(user_id),  # Always required for tenancy
        }

        try:
            response = self.client.rpc("search_scenes_by_visual_embedding", params).execute()
            results = []
            for rank, row in enumerate(response.data, start=1):
                results.append((str(row["id"]), rank, float(row["similarity"])))

            if self.search_debug and results:
                logger.info(f"Visual search: {len(results)} results, top score={results[0][2]:.4f}")
            else:
                logger.debug(f"Visual search: {len(results)} results")

            return results
        except Exception as e:
            logger.error(f"Visual embedding search failed: {e}", exc_info=True)
            return []

    def search_scenes_summary_embedding(
        self,
        query_embedding: list[float],
        user_id: UUID,
        video_id: Optional[UUID] = None,
        match_count: int = 200,
        threshold: float = 0.2,
    ) -> list[tuple[str, int, float]]:
        """Search scenes by summary embedding (multi-dense channel).

        Args:
            query_embedding: The vector embedding of the search query.
            user_id: User ID for tenant scoping (required).
            video_id: Filter by specific video ID (optional).
            match_count: Maximum number of results to return.
            threshold: Similarity threshold (0.0 to 1.0).

        Returns:
            list[tuple[str, int, float]]: List of (scene_id, rank, similarity) tuples.
        """
        # Convert embedding list to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        params = {
            "query_embedding": embedding_str,
            "match_threshold": threshold,
            "match_count": match_count,
            "filter_video_id": str(video_id) if video_id else None,
            "filter_user_id": str(user_id),  # Always required for tenancy
        }

        try:
            response = self.client.rpc("search_scenes_by_summary_embedding", params).execute()
            results = []
            for rank, row in enumerate(response.data, start=1):
                results.append((str(row["id"]), rank, float(row["similarity"])))

            if self.search_debug and results:
                logger.info(f"Summary search: {len(results)} results, top score={results[0][2]:.4f}")
            else:
                logger.debug(f"Summary search: {len(results)} results")

            return results
        except Exception as e:
            logger.error(f"Summary embedding search failed: {e}", exc_info=True)
            return []

    def search_scenes_visual_clip_embedding(
        self,
        query_embedding: list[float],
        user_id: UUID,
        video_id: Optional[UUID] = None,
        match_count: int = 200,
        threshold: float = 0.15,
    ) -> list[tuple[str, int, float]]:
        """Search scenes by CLIP visual embedding (true visual similarity).

        This is the CORRECT visual search method that compares CLIP text embeddings
        (512d from query) against CLIP image embeddings (512d from keyframes).
        Both live in the same vision-language vector space, enabling true multimodal search.

        Args:
            query_embedding: CLIP text embedding (512 dimensions).
            user_id: User ID for tenant scoping (required).
            video_id: Filter by specific video ID (optional).
            match_count: Maximum number of results to return.
            threshold: Similarity threshold (0.0 to 1.0).

        Returns:
            list[tuple[str, int, float]]: List of (scene_id, rank, similarity) tuples.
        """
        # Validate embedding dimension (512 for CLIP ViT-B-32)
        if len(query_embedding) != 512:
            logger.warning(
                f"CLIP embedding dimension mismatch: expected 512, got {len(query_embedding)}. "
                "Returning empty results."
            )
            return []

        # Convert embedding list to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        params = {
            "query_embedding": embedding_str,
            "match_threshold": threshold,
            "match_count": match_count,
            "filter_video_id": str(video_id) if video_id else None,
            "filter_user_id": str(user_id),  # Always required for tenancy
        }

        try:
            response = self.client.rpc("search_scenes_by_visual_clip_embedding", params).execute()
            results = []
            for rank, row in enumerate(response.data, start=1):
                results.append((str(row["id"]), rank, float(row["similarity"])))

            if self.search_debug and results:
                logger.info(
                    f"CLIP visual search: {len(results)} results, "
                    f"top score={results[0][2]:.4f}, threshold={threshold}"
                )
            else:
                logger.debug(f"CLIP visual search: {len(results)} results")

            return results
        except Exception as e:
            logger.error(f"CLIP visual embedding search failed: {e}", exc_info=True)
            return []

    def batch_score_scenes_clip(
        self,
        scene_ids: list[str],
        query_embedding: list[float],
        user_id: UUID,
    ) -> dict[str, float]:
        """Batch compute CLIP similarity scores for a set of candidate scenes.

        Used in rerank mode: given a candidate pool from other channels,
        compute CLIP visual similarity scores efficiently in a single DB query.

        Args:
            scene_ids: List of scene IDs to score (candidate pool).
            query_embedding: CLIP text embedding (512 dimensions).
            user_id: User ID for tenant scoping.

        Returns:
            dict[str, float]: Map of scene_id → CLIP similarity score.
                              Missing scenes are omitted (not accessible or no CLIP embedding).
        """
        if not scene_ids:
            return {}

        # Validate embedding dimension
        if len(query_embedding) != 512:
            logger.warning(
                f"CLIP embedding dimension mismatch: expected 512, got {len(query_embedding)}. "
                "Returning empty scores."
            )
            return {}

        # Convert embedding to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        params = {
            "query_embedding": embedding_str,
            "scene_ids": scene_ids,  # Pass as array
            "filter_user_id": str(user_id),
        }

        try:
            response = self.client.rpc("batch_score_scenes_clip", params).execute()

            # Build score map
            scores = {}
            for row in response.data:
                scene_id = str(row["id"])
                similarity = float(row["similarity"])
                scores[scene_id] = similarity

            if self.search_debug:
                score_values = list(scores.values())
                if score_values:
                    logger.info(
                        f"CLIP batch scoring: {len(scores)}/{len(scene_ids)} scenes scored, "
                        f"range=[{min(score_values):.4f}, {max(score_values):.4f}]"
                    )
                else:
                    logger.info(f"CLIP batch scoring: 0/{len(scene_ids)} scenes scored (no embeddings)")

            return scores
        except Exception as e:
            logger.error(f"CLIP batch scoring failed: {e}", exc_info=True)
            return {}

    def get_scenes_by_ids(
        self,
        scene_ids: list[UUID],
        preserve_order: bool = True,
    ) -> list[VideoScene]:
        """Get scenes by a list of IDs.

        Used to hydrate search results after RRF fusion.

        Args:
            scene_ids: List of scene UUIDs to fetch.
            preserve_order: If True, return results in the same order as input IDs.

        Returns:
            list[VideoScene]: List of scenes matching the IDs.
        """
        if not scene_ids:
            return []

        # Convert UUIDs to strings for the query
        id_strings = [str(sid) for sid in scene_ids]

        response = (
            self.client.table("video_scenes")
            .select(
                "id,video_id,index,start_s,end_s,transcript_segment,"
                "visual_summary,combined_text,thumbnail_url,"
                "visual_description,visual_entities,visual_actions,tags,created_at"
            )
            .in_("id", id_strings)
            .execute()
        )

        # Build scenes from response
        scenes_by_id: dict[str, VideoScene] = {}
        for row in response.data:
            row["id"] = UUID(row["id"])
            row["video_id"] = UUID(row["video_id"])
            scene = VideoScene(**row)
            scenes_by_id[str(scene.id)] = scene

        if preserve_order:
            # Return in the order of input IDs
            result = []
            for sid in scene_ids:
                scene = scenes_by_id.get(str(sid))
                if scene:
                    result.append(scene)
            return result
        else:
            return list(scenes_by_id.values())

    def get_video_filenames_by_ids(
        self,
        video_ids: list[UUID],
    ) -> dict[str, str]:
        """Get video filenames for a list of video IDs.

        Used to enrich search results with video filenames.

        Args:
            video_ids: List of video UUIDs to fetch filenames for.

        Returns:
            dict[str, str]: Mapping of video_id (string) to filename.
        """
        if not video_ids:
            return {}

        # Convert UUIDs to strings and deduplicate
        id_strings = list(set(str(vid) for vid in video_ids))

        response = (
            self.client.table("videos")
            .select("id,filename")
            .in_("id", id_strings)
            .execute()
        )

        # Build mapping
        filename_map: dict[str, str] = {}
        for row in response.data:
            video_id = row["id"]
            filename = row.get("filename")
            if filename:
                filename_map[video_id] = filename

        return filename_map

    def log_search_query(
        self,
        user_id: UUID,
        query_text: str,
        results_count: int,
        latency_ms: int,
        video_id: Optional[UUID] = None,
        search_metadata: Optional[dict] = None,
    ) -> None:
        """Log a search query for analytics.

        Args:
            user_id: The UUID of the user making the query.
            query_text: The search query text.
            results_count: Number of results returned.
            latency_ms: Search latency in milliseconds.
            video_id: The specific video ID searched, if any (optional).
            search_metadata: Search execution metadata (fusion config, timings, etc).

        Returns:
            None: This function does not return a value.
        """
        data = {
            "user_id": str(user_id),
            "video_id": str(video_id) if video_id else None,
            "query_text": query_text,
            "results_count": results_count,
            "latency_ms": latency_ms,
            "search_metadata": search_metadata,
        }

        self.client.table("search_queries").insert(data).execute()

    # Search Preferences operations
    def get_user_search_preferences(self, user_id: UUID) -> Optional[dict]:
        """Get user's saved search preferences.

        Args:
            user_id: The UUID of the user.

        Returns:
            Optional[dict]: Preferences dict with weights, fusion_method, etc, or None.
        """
        response = (
            self.client.table("user_profiles")
            .select("search_preferences, created_at, updated_at")
            .eq("user_id", str(user_id))
            .execute()
        )

        if not response.data:
            return None

        row = response.data[0]
        prefs = row.get("search_preferences")

        if not prefs:
            return None

        return {
            **prefs,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def save_user_search_preferences(
        self, user_id: UUID, preferences: dict
    ) -> dict:
        """Save or update user's search preferences.

        Args:
            user_id: The UUID of the user.
            preferences: Preferences dict to save (weights, fusion_method, visual_mode, etc).

        Returns:
            dict: Saved preferences with timestamps.

        Raises:
            ValueError: If user profile not found.
        """
        response = (
            self.client.table("user_profiles")
            .update({"search_preferences": preferences})
            .eq("user_id", str(user_id))
            .execute()
        )

        if not response.data:
            raise ValueError(f"User profile not found: {user_id}")

        row = response.data[0]
        return {
            **preferences,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def delete_user_search_preferences(self, user_id: UUID) -> None:
        """Delete user's search preferences (reset to defaults).

        Args:
            user_id: The UUID of the user.

        Returns:
            None
        """
        self.client.table("user_profiles").update({
            "search_preferences": None,
        }).eq("user_id", str(user_id)).execute()

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

    # Admin operations
    def get_all_videos_for_reprocess(self) -> list[Video]:
        """Get all videos for admin bulk reprocessing.

        Returns videos that are not currently being processed.

        Returns:
            list[Video]: A list of all videos eligible for reprocessing.
        """
        response = (
            self.client.table("videos")
            .select("*")
            .neq("status", VideoStatus.PROCESSING.value)
            .order("created_at", desc=True)
            .execute()
        )

        videos = []
        for row in response.data:
            row["id"] = UUID(row["id"])
            row["owner_id"] = UUID(row["owner_id"])
            row["status"] = VideoStatus(row["status"])
            videos.append(Video(**row))
        return videos

    def get_videos_for_owner_reprocess(self, owner_id: UUID) -> list[Video]:
        """Get all videos for an owner for reprocessing.

        Returns videos for a specific owner that are not currently being processed.

        Args:
            owner_id: The UUID of the owner

        Returns:
            list[Video]: A list of videos eligible for reprocessing for this owner.
        """
        response = (
            self.client.table("videos")
            .select("*")
            .eq("owner_id", str(owner_id))
            .neq("status", VideoStatus.PROCESSING.value)
            .order("created_at", desc=False)
            .execute()
        )

        videos = []
        for row in response.data:
            row["id"] = UUID(row["id"])
            row["owner_id"] = UUID(row["owner_id"])
            row["status"] = VideoStatus(row["status"])
            videos.append(Video(**row))
        return videos

    # Admin Metrics operations
    def get_admin_overview_metrics(self) -> dict:
        """Get overview metrics for admin dashboard.

        Returns:
            dict: Overview metrics including video counts, hours, searches, latency.
        """
        # Use RPC function to compute metrics in single query
        response = self.client.rpc("get_admin_overview_metrics").execute()

        if not response.data or len(response.data) == 0:
            # Return default metrics if no data
            return {
                "videos_ready_total": 0,
                "videos_failed_total": 0,
                "videos_total": 0,
                "failure_rate_pct": 0.0,
                "hours_ready_total": 0.0,
                "searches_7d": 0,
                "avg_search_latency_ms_7d": None,
                "searches_30d": 0,
                "avg_search_latency_ms_30d": None,
            }

        return response.data[0]

    def get_throughput_timeseries(self, days: int = 30) -> list[dict]:
        """Get daily throughput time series.

        Args:
            days: Number of days to look back.

        Returns:
            list[dict]: List of daily throughput data points.
        """
        response = self.client.rpc(
            "get_throughput_timeseries",
            {"days_back": days}
        ).execute()

        return response.data if response.data else []

    def get_search_timeseries(self, days: int = 30) -> list[dict]:
        """Get daily search time series.

        Args:
            days: Number of days to look back.

        Returns:
            list[dict]: List of daily search data points.
        """
        response = self.client.rpc(
            "get_search_timeseries",
            {"days_back": days}
        ).execute()

        return response.data if response.data else []

    def get_admin_users_list(
        self,
        days: int = 7,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "last_activity"
    ) -> dict:
        """Get paginated list of users with metrics.

        Args:
            days: Number of days for recent metrics.
            page: Page number (1-indexed).
            page_size: Items per page.
            sort_by: Sort column (last_activity, hours_ready, videos_ready, searches_7d).

        Returns:
            dict: Paginated user list with items and metadata.
        """
        offset = (page - 1) * page_size

        response = self.client.rpc(
            "get_admin_users_list",
            {
                "days_back": days,
                "limit_count": page_size,
                "offset_count": offset,
                "sort_column": sort_by
            }
        ).execute()

        items = response.data if response.data else []

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_users": None  # Optional for Phase 1
        }

    def get_admin_user_detail(self, user_id: UUID, days: int = 7) -> Optional[dict]:
        """Get detailed user information with recent videos and searches.

        Args:
            user_id: User UUID.
            days: Number of days for recent metrics.

        Returns:
            Optional[dict]: User detail data or None if not found.
        """
        response = self.client.rpc(
            "get_admin_user_detail",
            {
                "target_user_id": str(user_id),
                "days_back": days
            }
        ).execute()

        if not response.data or len(response.data) == 0:
            return None

        return response.data[0]

    # Phase 2: Performance Metrics operations
    def get_admin_processing_latency(self, days: int = 30) -> dict:
        """Get processing latency percentiles and queue time (Phase 2).

        Args:
            days: Number of days to look back.

        Returns:
            dict: Latency metrics including p50/p95/p99 and queue time.
        """
        response = self.client.rpc(
            "get_admin_processing_latency",
            {"p_days_back": days}
        ).execute()

        if not response.data or len(response.data) == 0:
            return {
                "videos_measured": 0,
                "avg_processing_ms": None,
                "p50_processing_ms": None,
                "p95_processing_ms": None,
                "p99_processing_ms": None,
                "avg_queue_ms": None,
                "avg_total_ms": None,
            }

        return response.data[0]

    def get_admin_rtf_distribution(self, days: int = 30) -> dict:
        """Get RTF (Real-Time Factor) distribution (Phase 2).

        Args:
            days: Number of days to look back.

        Returns:
            dict: RTF distribution metrics.
        """
        response = self.client.rpc(
            "get_admin_rtf_distribution",
            {"p_days_back": days}
        ).execute()

        if not response.data or len(response.data) == 0:
            return {
                "videos_measured": 0,
                "avg_rtf": None,
                "p50_rtf": None,
                "p95_rtf": None,
                "p99_rtf": None,
                "avg_video_duration_s": None,
                "avg_processing_duration_s": None,
            }

        return response.data[0]

    def get_admin_queue_analysis(self, days: int = 30) -> dict:
        """Get queue vs processing time analysis (Phase 2).

        Args:
            days: Number of days to look back.

        Returns:
            dict: Queue analysis metrics.
        """
        response = self.client.rpc(
            "get_admin_queue_analysis",
            {"p_days_back": days}
        ).execute()

        if not response.data or len(response.data) == 0:
            return {
                "videos_measured": 0,
                "avg_queue_time_s": None,
                "avg_processing_time_s": None,
                "avg_total_time_s": None,
                "queue_time_pct": None,
                "processing_time_pct": None,
            }

        return response.data[0]

    def get_admin_failures_by_stage(self, days: int = 30) -> list[dict]:
        """Get failures grouped by processing stage (Phase 2).

        Args:
            days: Number of days to look back.

        Returns:
            list[dict]: Failures by stage data.
        """
        response = self.client.rpc(
            "get_admin_failures_by_stage",
            {"p_days_back": days}
        ).execute()

        return response.data if response.data else []

    def get_admin_throughput_timeseries_v2(self, days: int = 30) -> list[dict]:
        """Get enhanced throughput time series with Phase 2 metrics.

        Args:
            days: Number of days to look back.

        Returns:
            list[dict]: Enhanced throughput data points.
        """
        response = self.client.rpc(
            "get_admin_throughput_timeseries_v2",
            {"p_days_back": days}
        ).execute()

        return response.data if response.data else []

    # Highlight Export Job operations
    def create_highlight_export_job(
        self,
        user_id: UUID,
        request_data: dict,
    ) -> HighlightExportJob:
        """Create a new highlight export job.

        Args:
            user_id: UUID of the user creating the job.
            request_data: JSONB containing ordered scenes + options.

        Returns:
            HighlightExportJob: The created job record.
        """
        data = {
            "user_id": str(user_id),
            "status": HighlightJobStatus.QUEUED.value,
            "request": request_data,
        }

        response = self.client.table("highlight_export_jobs").insert(data).execute()
        return self._map_highlight_job_response(response.data[0])

    def get_highlight_export_job(self, job_id: UUID) -> Optional[HighlightExportJob]:
        """Get a highlight export job by ID.

        Args:
            job_id: UUID of the job.

        Returns:
            Optional[HighlightExportJob]: The job if found, otherwise None.
        """
        response = (
            self.client.table("highlight_export_jobs")
            .select("*")
            .eq("id", str(job_id))
            .execute()
        )

        if not response.data:
            return None

        return self._map_highlight_job_response(response.data[0])

    def update_highlight_export_job(
        self,
        job_id: UUID,
        status: Optional[HighlightJobStatus] = None,
        progress: Optional[dict] = None,
        output: Optional[dict] = None,
        error: Optional[dict] = None,
    ) -> HighlightExportJob:
        """Update a highlight export job record.

        Args:
            job_id: UUID of the job to update.
            status: New status (optional).
            progress: Progress data (optional).
            output: Output metadata (optional).
            error: Error details (optional).

        Returns:
            HighlightExportJob: The updated job record.
        """
        update_data = {}
        if status is not None:
            update_data["status"] = status.value
        if progress is not None:
            update_data["progress"] = progress
        if output is not None:
            update_data["output"] = output
        if error is not None:
            update_data["error"] = error

        response = (
            self.client.table("highlight_export_jobs")
            .update(update_data)
            .eq("id", str(job_id))
            .execute()
        )

        return self._map_highlight_job_response(response.data[0])

    def _map_highlight_job_response(self, row: dict) -> HighlightExportJob:
        """Map database row to HighlightExportJob model.

        Args:
            row: Database row as dictionary.

        Returns:
            HighlightExportJob: Mapped job model.
        """
        return HighlightExportJob(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            status=HighlightJobStatus(row["status"]),
            request=row.get("request") or {},
            progress=row.get("progress"),
            output=row.get("output"),
            error=row.get("error"),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
        )

    # ========================================================================
    # PERSON OPERATIONS
    # ========================================================================

    def create_person(
        self,
        owner_id: UUID,
        display_name: Optional[str] = None,
    ) -> Person:
        """Create a new person record.

        Args:
            owner_id: UUID of the owning user.
            display_name: Optional display name for the person.

        Returns:
            Person: The created person.
        """
        data = {
            "owner_id": str(owner_id),
            "display_name": display_name,
            "status": "active",
        }

        response = self.client.table("persons").insert(data).execute()

        if not response.data:
            raise ValueError("Failed to create person")

        return self._map_person_row(response.data[0])

    def get_person(self, person_id: UUID, owner_id: UUID) -> Optional[Person]:
        """Get person by ID (tenant-scoped).

        Args:
            person_id: UUID of the person.
            owner_id: UUID of the owning user (for tenant isolation).

        Returns:
            Optional[Person]: The person if found and owned by user, otherwise None.
        """
        response = (
            self.client.table("persons")
            .select("*")
            .eq("id", str(person_id))
            .eq("owner_id", str(owner_id))
            .execute()
        )

        if not response.data:
            return None

        return self._map_person_row(response.data[0])

    def list_persons(self, owner_id: UUID) -> list[Person]:
        """List all persons for owner.

        Args:
            owner_id: UUID of the owning user.

        Returns:
            list[Person]: List of persons.
        """
        response = (
            self.client.table("persons")
            .select("*")
            .eq("owner_id", str(owner_id))
            .order("created_at", desc=True)
            .execute()
        )

        return [self._map_person_row(row) for row in response.data]

    def update_person_query_embedding(
        self,
        person_id: UUID,
        embedding: list[float],
    ) -> None:
        """Update aggregate query embedding for person.

        Args:
            person_id: UUID of the person.
            embedding: 512-dimensional CLIP embedding.
        """
        if not embedding or len(embedding) != 512:
            raise ValueError(f"Invalid embedding dimension: {len(embedding) if embedding else 0}")

        # Convert to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        self.client.table("persons").update({
            "query_embedding": embedding_str,
        }).eq("id", str(person_id)).execute()

    def delete_person(self, person_id: UUID, owner_id: UUID) -> None:
        """Delete person and cascade to photos.

        Args:
            person_id: UUID of the person.
            owner_id: UUID of the owning user (for tenant isolation).
        """
        self.client.table("persons").delete().eq("id", str(person_id)).eq("owner_id", str(owner_id)).execute()

    # ========================================================================
    # PERSON REFERENCE PHOTO OPERATIONS
    # ========================================================================

    def create_person_reference_photo(
        self,
        owner_id: UUID,
        person_id: UUID,
        storage_path: str,
    ) -> PersonReferencePhoto:
        """Create a reference photo record in UPLOADED state.

        Args:
            owner_id: UUID of the owning user.
            person_id: UUID of the person.
            storage_path: Storage path in Supabase storage.

        Returns:
            PersonReferencePhoto: The created photo record.
        """
        data = {
            "owner_id": str(owner_id),
            "person_id": str(person_id),
            "storage_path": storage_path,
            "state": "UPLOADED",
        }

        response = self.client.table("person_reference_photos").insert(data).execute()

        if not response.data:
            raise ValueError("Failed to create person reference photo")

        return self._map_person_photo_row(response.data[0])

    def get_person_reference_photo(self, photo_id: UUID) -> Optional[PersonReferencePhoto]:
        """Get photo by ID.

        Args:
            photo_id: UUID of the photo.

        Returns:
            Optional[PersonReferencePhoto]: The photo if found, otherwise None.
        """
        response = (
            self.client.table("person_reference_photos")
            .select("*")
            .eq("id", str(photo_id))
            .execute()
        )

        if not response.data:
            return None

        return self._map_person_photo_row(response.data[0])

    def list_person_photos(self, person_id: UUID) -> list[PersonReferencePhoto]:
        """List all photos for a person.

        Args:
            person_id: UUID of the person.

        Returns:
            list[PersonReferencePhoto]: List of photos.
        """
        response = (
            self.client.table("person_reference_photos")
            .select("*")
            .eq("person_id", str(person_id))
            .order("created_at", desc=False)
            .execute()
        )

        return [self._map_person_photo_row(row) for row in response.data]

    def update_person_photo_state(
        self,
        photo_id: UUID,
        state: str,
    ) -> None:
        """Update photo state (UPLOADED, PROCESSING, READY, FAILED).

        Args:
            photo_id: UUID of the photo.
            state: New state.
        """
        self.client.table("person_reference_photos").update({
            "state": state,
        }).eq("id", str(photo_id)).execute()

    def update_person_photo_embedding(
        self,
        photo_id: UUID,
        embedding: list[float],
        quality_score: float,
        state: str = "READY",
    ) -> None:
        """Update photo with embedding after processing.

        Args:
            photo_id: UUID of the photo.
            embedding: 512-dimensional CLIP embedding.
            quality_score: Quality score (0-1).
            state: New state (default: READY).
        """
        if not embedding or len(embedding) != 512:
            raise ValueError(f"Invalid embedding dimension: {len(embedding) if embedding else 0}")

        # Convert to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        self.client.table("person_reference_photos").update({
            "embedding": embedding_str,
            "quality_score": quality_score,
            "state": state,
            "error_message": None,  # Clear any previous error
        }).eq("id", str(photo_id)).execute()

    def update_person_photo_failed(
        self,
        photo_id: UUID,
        error_message: str,
    ) -> None:
        """Mark photo as failed.

        Args:
            photo_id: UUID of the photo.
            error_message: Error message.
        """
        self.client.table("person_reference_photos").update({
            "state": "FAILED",
            "error_message": error_message[:500],  # Truncate
        }).eq("id", str(photo_id)).execute()

    def get_ready_photo_embeddings(self, person_id: UUID) -> list[list[float]]:
        """Get all READY photo embeddings for aggregation.

        Args:
            person_id: UUID of the person.

        Returns:
            list[list[float]]: List of embeddings.
        """
        response = (
            self.client.table("person_reference_photos")
            .select("embedding")
            .eq("person_id", str(person_id))
            .eq("state", "READY")
            .not_.is_("embedding", "null")
            .execute()
        )

        embeddings = []
        for row in response.data:
            embedding = deserialize_embedding(row.get("embedding"))
            if embedding:
                # Validate dimension
                if len(embedding) != 512:
                    logger.warning(
                        f"Skipping photo embedding with invalid dimension: "
                        f"expected 512, got {len(embedding)}"
                    )
                    continue
                embeddings.append(embedding)

        return embeddings

    # ========================================================================
    # PERSON SEARCH RPC
    # ========================================================================

    def search_scenes_by_person_clip_embedding(
        self,
        query_embedding: list[float],
        user_id: UUID,
        video_id: Optional[UUID] = None,
        match_count: int = 200,
        threshold: float = 0.3,
    ) -> list[tuple[str, int, float]]:
        """Search scenes by person CLIP embedding.

        Calls the search_scenes_by_person_clip_embedding RPC function.

        Args:
            query_embedding: 512-dimensional CLIP embedding.
            user_id: UUID of the user (for tenant isolation).
            video_id: Optional video ID to filter results.
            match_count: Number of results to return.
            threshold: Minimum similarity threshold.

        Returns:
            list[tuple[str, int, float]]: List of (scene_id, rank, similarity).
        """
        if not query_embedding or len(query_embedding) != 512:
            logger.warning(f"Invalid person embedding dimension: {len(query_embedding) if query_embedding else 0}")
            return []

        # Convert to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        params = {
            "query_embedding": embedding_str,
            "match_threshold": threshold,
            "match_count": match_count,
            "filter_video_id": str(video_id) if video_id else None,
            "filter_user_id": str(user_id),
        }

        response = self.client.rpc("search_scenes_by_person_clip_embedding", params).execute()

        results = []
        for rank, row in enumerate(response.data, start=1):
            scene_id = row["scene_id"]
            similarity = float(row["similarity"])
            results.append((scene_id, rank, similarity))

        if self.search_debug:
            logger.info(
                f"Person search: query_dim={len(query_embedding)}, "
                f"threshold={threshold}, user_id={user_id}, "
                f"video_id={video_id}, results={len(results)}"
            )

        return results

    # ========================================================================
    # SCENE PERSON EMBEDDINGS
    # ========================================================================

    def create_scene_person_embedding(
        self,
        owner_id: UUID,
        video_id: UUID,
        scene_id: UUID,
        embedding: list[float],
        kind: str = "thumbnail",
        ordinal: int = 0,
    ) -> None:
        """Create or update scene person embedding (upsert on unique constraint).

        Args:
            owner_id: UUID of the owning user.
            video_id: UUID of the video.
            scene_id: UUID of the scene.
            embedding: 512-dimensional CLIP embedding.
            kind: Embedding kind (default: thumbnail).
            ordinal: Ordinal within kind (default: 0).
        """
        if not embedding or len(embedding) != 512:
            raise ValueError(f"Invalid embedding dimension: {len(embedding) if embedding else 0}")

        # Convert to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        data = {
            "owner_id": str(owner_id),
            "video_id": str(video_id),
            "scene_id": str(scene_id),
            "kind": kind,
            "ordinal": ordinal,
            "embedding": embedding_str,
        }

        # Upsert: insert or update on conflict
        self.client.table("scene_person_embeddings").upsert(
            data,
            on_conflict="scene_id,kind,ordinal"
        ).execute()

    def get_scene_person_embedding(
        self,
        scene_id: UUID,
        kind: str = "thumbnail",
        ordinal: int = 0,
    ) -> Optional[dict]:
        """Check if scene has person embedding.

        Args:
            scene_id: UUID of the scene.
            kind: Embedding kind (default: thumbnail).
            ordinal: Ordinal within kind (default: 0).

        Returns:
            Optional[dict]: Embedding record if exists, otherwise None.
        """
        response = (
            self.client.table("scene_person_embeddings")
            .select("id,created_at")
            .eq("scene_id", str(scene_id))
            .eq("kind", kind)
            .eq("ordinal", ordinal)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]

    # ========================================================================
    # MAPPING HELPERS
    # ========================================================================

    def _map_person_row(self, row: dict) -> Person:
        """Map database row to Person model.

        Args:
            row: Database row dict.

        Returns:
            Person: Mapped person model.
        """
        query_embedding = deserialize_embedding(row.get("query_embedding"))

        # Validate embedding dimension if present
        if query_embedding is not None:
            if len(query_embedding) != 512:
                logger.warning(
                    f"Invalid query_embedding dimension for person {row['id']}: "
                    f"expected 512, got {len(query_embedding)}"
                )
            # Check for non-finite values
            if not all(isinstance(x, (int, float)) and abs(x) != float('inf') for x in query_embedding):
                logger.warning(f"Non-finite values in query_embedding for person {row['id']}")

        return Person(
            id=UUID(row["id"]),
            owner_id=UUID(row["owner_id"]),
            display_name=row.get("display_name"),
            query_embedding=query_embedding,
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
        )

    def _map_person_photo_row(self, row: dict) -> PersonReferencePhoto:
        """Map database row to PersonReferencePhoto model.

        Args:
            row: Database row dict.

        Returns:
            PersonReferencePhoto: Mapped photo model.
        """
        embedding = deserialize_embedding(row.get("embedding"))

        # Validate embedding dimension if present
        if embedding is not None:
            if len(embedding) != 512:
                logger.warning(
                    f"Invalid embedding dimension for photo {row['id']}: "
                    f"expected 512, got {len(embedding)}"
                )
            if not all(isinstance(x, (int, float)) and abs(x) != float('inf') for x in embedding):
                logger.warning(f"Non-finite values in embedding for photo {row['id']}")

        return PersonReferencePhoto(
            id=UUID(row["id"]),
            owner_id=UUID(row["owner_id"]),
            person_id=UUID(row["person_id"]),
            storage_path=row["storage_path"],
            state=row["state"],
            embedding=embedding,
            quality_score=row.get("quality_score"),
            face_bbox=row.get("face_bbox"),
            error_message=row.get("error_message"),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
        )


# DEPRECATED: Global instance removed for Phase 1 refactor.
# Use dependency injection instead via get_db() from dependencies.py
# This remains as None to prevent import-time Supabase client creation.
db: Database = None  # type: ignore
