"""Database adapter for worker service."""
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID
from supabase import create_client, Client

from ..config import settings

logger = logging.getLogger(__name__)

# Cache for video owner_id lookups (cleared per video processing job)
_video_owner_cache: dict[str, str] = {}


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

    def get_owner_id_for_video(self, video_id: UUID) -> Optional[str]:
        """Get the owner_id for a video, with in-memory caching.

        Args:
            video_id: The UUID of the video.

        Returns:
            Optional[str]: The owner_id as string, or None if not found.
        """
        video_id_str = str(video_id)

        # Check cache first
        if video_id_str in _video_owner_cache:
            return _video_owner_cache[video_id_str]

        # Fetch from database
        video = self.get_video(video_id)
        if video and "owner_id" in video:
            owner_id = video["owner_id"]
            _video_owner_cache[video_id_str] = owner_id
            return owner_id

        return None

    def clear_owner_cache(self) -> None:
        """Clear the video owner cache (call at start of video processing)."""
        _video_owner_cache.clear()

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

    def save_transcript(
        self, video_id: UUID, transcript: str, segments: Optional[list] = None
    ) -> None:
        """
        Save transcript and segments to database as checkpoint.

        This allows us to skip expensive Whisper transcription on retry.

        Args:
            video_id: Video ID
            transcript: Full video transcript
            segments: Optional list of WhisperSegment objects with timestamps

        Returns:
            None: This function does not return a value.
        """
        update_data = {"full_transcript": transcript}

        # Serialize segments to JSONB if provided
        if segments:
            # Convert WhisperSegment dataclass instances to dicts
            segments_json = []
            for seg in segments:
                if hasattr(seg, "__dict__"):
                    # Dataclass instance - convert to dict
                    seg_dict = {
                        "start": seg.start,
                        "end": seg.end,
                        "text": seg.text,
                    }
                    if seg.no_speech_prob is not None:
                        seg_dict["no_speech_prob"] = seg.no_speech_prob
                    if seg.avg_logprob is not None:
                        seg_dict["avg_logprob"] = seg.avg_logprob
                    segments_json.append(seg_dict)
                else:
                    # Already a dict
                    segments_json.append(seg)

            update_data["transcript_segments"] = segments_json
            logger.info(
                f"Saving transcript checkpoint for video {video_id} "
                f"({len(transcript)} chars, {len(segments)} segments)"
            )
        else:
            logger.info(
                f"Saving transcript checkpoint for video {video_id} ({len(transcript)} chars)"
            )

        self.client.table("videos").update(update_data).eq(
            "id", str(video_id)
        ).execute()

    def get_cached_transcript(
        self, video_id: UUID
    ) -> tuple[Optional[str], Optional[list]]:
        """
        Get cached transcript and segments if they exist.

        Args:
            video_id: Video ID

        Returns:
            Tuple of (transcript, segments) where:
            - transcript: Full video transcript text or None
            - segments: List of segment dicts with timestamps or None
        """
        video = self.get_video(video_id)
        if not video:
            return (None, None)

        transcript = video.get("full_transcript")
        segments = video.get("transcript_segments")

        if transcript:
            if segments:
                logger.info(
                    f"Found cached transcript for video {video_id} "
                    f"({len(transcript)} chars, {len(segments)} segments)"
                )
            else:
                logger.info(
                    f"Found cached transcript for video {video_id} ({len(transcript)} chars, no segments)"
                )
            return (transcript, segments)

        return (None, None)

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
        owner_id: Optional[str] = None,
        # v3-multi embedding fields
        embedding_transcript: Optional[list[float]] = None,
        embedding_visual: Optional[list[float]] = None,
        embedding_summary: Optional[list[float]] = None,
        embedding_version: Optional[str] = None,
        multi_embedding_metadata: Optional[dict] = None,
        # CLIP visual embedding fields
        embedding_visual_clip: Optional[list[float]] = None,
        visual_clip_metadata: Optional[dict] = None,
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
            owner_id: Optional owner_id for OpenSearch indexing (fetched if not provided).

        Returns:
            UUID: The UUID of the created scene.
        """
        # Convert embedding list to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Helper function to convert embedding to pgvector format
        def to_pgvector(emb: Optional[list[float]]) -> Optional[str]:
            if emb is None:
                return None
            return "[" + ",".join(str(x) for x in emb) + "]"

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

        # Add v3-multi embedding fields if present
        if embedding_transcript is not None:
            data["embedding_transcript"] = to_pgvector(embedding_transcript)
        if embedding_visual is not None:
            data["embedding_visual"] = to_pgvector(embedding_visual)
        if embedding_summary is not None:
            data["embedding_summary"] = to_pgvector(embedding_summary)
        if embedding_version is not None:
            data["embedding_version"] = embedding_version
        if multi_embedding_metadata is not None:
            data["embedding_metadata"] = multi_embedding_metadata  # Override with multi-metadata

        # Add CLIP visual embedding fields if present
        if embedding_visual_clip is not None:
            data["embedding_visual_clip"] = to_pgvector(embedding_visual_clip)
        if visual_clip_metadata is not None:
            data["visual_clip_metadata"] = visual_clip_metadata

        response = self.client.table("video_scenes").insert(data).execute()
        scene_id = UUID(response.data[0]["id"])

        # Index to OpenSearch for hybrid search (non-blocking on failure)
        self._index_scene_to_opensearch(
            scene_id=scene_id,
            video_id=video_id,
            owner_id=owner_id,
            index=index,
            start_s=start_s,
            end_s=end_s,
            transcript_segment=transcript_segment,
            visual_summary=visual_summary,
            visual_description=visual_description,
            combined_text=combined_text,
            tags=tags,
            thumbnail_url=thumbnail_url,
        )

        return scene_id

    def _index_scene_to_opensearch(
        self,
        scene_id: UUID,
        video_id: UUID,
        owner_id: Optional[str],
        index: int,
        start_s: float,
        end_s: float,
        transcript_segment: Optional[str],
        visual_summary: Optional[str],
        visual_description: Optional[str],
        combined_text: Optional[str],
        tags: Optional[list[str]],
        thumbnail_url: Optional[str],
    ) -> None:
        """Index scene to OpenSearch for hybrid search.

        This is a non-blocking operation - failures are logged but don't
        affect the main scene creation flow.
        """
        try:
            from .opensearch_client import opensearch_client

            # Get owner_id if not provided
            if owner_id is None:
                owner_id = self.get_owner_id_for_video(video_id)
                if owner_id is None:
                    logger.warning(f"Could not find owner_id for video {video_id}, skipping OpenSearch indexing")
                    return

            # Upsert to OpenSearch
            opensearch_client.upsert_scene_doc(
                scene_id=str(scene_id),
                video_id=str(video_id),
                owner_id=owner_id,
                index=index,
                start_s=start_s,
                end_s=end_s,
                transcript_segment=transcript_segment,
                visual_summary=visual_summary,
                visual_description=visual_description,
                combined_text=combined_text,
                tags=tags,
                thumbnail_url=thumbnail_url,
            )

        except Exception as e:
            # Log but don't fail - OpenSearch is a secondary index
            logger.warning(f"Failed to index scene {scene_id} to OpenSearch: {e}")

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
        # Delete from Supabase
        self.client.table("video_scenes").delete().eq("video_id", str(video_id)).execute()

        # Delete from OpenSearch (non-blocking on failure)
        try:
            from .opensearch_client import opensearch_client
            opensearch_client.delete_scenes_for_video(str(video_id))
        except Exception as e:
            logger.warning(f"Failed to delete scenes for video {video_id} from OpenSearch: {e}")

    def get_scene_by_id(self, scene_id: UUID) -> Optional[dict]:
        """Get a scene by its ID.

        Args:
            scene_id: The UUID of the scene.

        Returns:
            Scene data if exists, None otherwise
        """
        response = (
            self.client.table("video_scenes")
            .select("*")
            .eq("id", str(scene_id))
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]

    def get_scene_export(self, export_id: UUID) -> Optional[dict]:
        """Get a scene export by ID.

        Args:
            export_id: UUID of the export.

        Returns:
            Export data if found, otherwise None.
        """
        response = (
            self.client.table("scene_exports")
            .select("*")
            .eq("id", str(export_id))
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]

    def update_scene_export(
        self,
        export_id: UUID,
        status: Optional[str] = None,
        storage_path: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        duration_s: Optional[float] = None,
        resolution: Optional[str] = None,
        error_message: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> dict:
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
            Updated export data.
        """
        update_data = {}
        if status is not None:
            update_data["status"] = status
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
        return response.data[0]


# Global database instance
db = Database(settings.supabase_url, settings.supabase_service_role_key)
