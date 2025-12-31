"""OpenSearch client adapter for scene indexing."""
import logging
from typing import Optional
from datetime import datetime

from opensearchpy import OpenSearch
from opensearchpy.exceptions import (
    ConnectionError as OSConnectionError,
    NotFoundError,
    RequestError,
)

logger = logging.getLogger(__name__)

# Index mapping for scene documents (must match API's mapping)
SCENE_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "refresh_interval": "1s",
        # Custom analyzers for Korean and English
        "analysis": {
            "analyzer": {
                "ko_nori": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["lowercase"],
                },
                "en_english": {
                    "type": "english",
                },
            }
        },
    },
    "mappings": {
        "properties": {
            # IDs for filtering (keyword for exact match)
            "scene_id": {"type": "keyword"},
            "video_id": {"type": "keyword"},
            "owner_id": {"type": "keyword"},
            # Numeric fields
            "index": {"type": "integer"},
            "start_s": {"type": "float"},
            "end_s": {"type": "float"},
            # Text fields for BM25 search with multi-field Korean/English analysis
            "transcript_segment": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "ko": {"type": "text", "analyzer": "ko_nori"},
                    "en": {"type": "text", "analyzer": "en_english"},
                },
            },
            "visual_summary": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "ko": {"type": "text", "analyzer": "ko_nori"},
                    "en": {"type": "text", "analyzer": "en_english"},
                },
            },
            "visual_description": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "ko": {"type": "text", "analyzer": "ko_nori"},
                    "en": {"type": "text", "analyzer": "en_english"},
                },
            },
            "combined_text": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "ko": {"type": "text", "analyzer": "ko_nori"},
                    "en": {"type": "text", "analyzer": "en_english"},
                },
            },
            # Tags: keyword for filtering + text for BM25 with multi-field analysis
            "tags": {"type": "keyword"},
            "tags_text": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "ko": {"type": "text", "analyzer": "ko_nori"},
                    "en": {"type": "text", "analyzer": "en_english"},
                },
            },
            # Metadata
            "thumbnail_url": {"type": "keyword", "index": False},
            "created_at": {"type": "date"},
        }
    },
}


class OpenSearchClient:
    """OpenSearch client for scene document indexing."""

    def __init__(
        self,
        opensearch_url: str,
        timeout_s: float,
        index_scenes: str,
        indexing_enabled: bool = True,
    ):
        """Initialize the OpenSearch client with explicit configuration.

        Args:
            opensearch_url: OpenSearch server URL (e.g., "http://opensearch:9200")
            timeout_s: Request timeout in seconds
            index_scenes: Index name for scene documents
            indexing_enabled: Whether indexing is enabled (feature flag)
        """
        self.opensearch_url = opensearch_url
        self.timeout_s = timeout_s
        self.index_scenes = index_scenes
        self.indexing_enabled = indexing_enabled
        self._client: Optional[OpenSearch] = None

    @property
    def client(self) -> OpenSearch:
        """Lazily initialize and return the OpenSearch client."""
        if self._client is None:
            self._client = OpenSearch(
                hosts=[self.opensearch_url],
                timeout=self.timeout_s,
                max_retries=2,
                retry_on_timeout=True,
            )
        return self._client

    def ping(self) -> bool:
        """Check if OpenSearch is available.

        Returns:
            bool: True if OpenSearch is reachable, False otherwise.
        """
        try:
            return self.client.ping()
        except (OSConnectionError, Exception) as e:
            logger.warning(f"OpenSearch ping failed: {e}")
            return False

    def ensure_index(self) -> bool:
        """Ensure the scene index exists with proper mapping.

        Returns:
            bool: True if index exists or was created, False on error.
        """
        index_name = self.index_scenes
        try:
            if not self.client.indices.exists(index=index_name):
                logger.info(f"Creating OpenSearch index: {index_name}")
                self.client.indices.create(
                    index=index_name,
                    body=SCENE_INDEX_MAPPING,
                )
                logger.info(f"Successfully created index: {index_name}")
            return True
        except RequestError as e:
            if "resource_already_exists_exception" in str(e):
                logger.debug(f"Index {index_name} already exists")
                return True
            logger.error(f"Failed to create index {index_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to ensure index {index_name}: {e}")
            return False

    def upsert_scene_doc(
        self,
        scene_id: str,
        video_id: str,
        owner_id: str,
        index: int,
        start_s: float,
        end_s: float,
        transcript_segment: Optional[str] = None,
        visual_summary: Optional[str] = None,
        visual_description: Optional[str] = None,
        combined_text: Optional[str] = None,
        tags: Optional[list[str]] = None,
        thumbnail_url: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> bool:
        """Upsert a scene document to OpenSearch.

        Uses scene_id as document ID for idempotent upserts.

        Args:
            scene_id: Unique scene identifier.
            video_id: Video the scene belongs to.
            owner_id: Owner of the video (for access control).
            index: Scene index within video.
            start_s: Start time in seconds.
            end_s: End time in seconds.
            transcript_segment: Scene transcript text.
            visual_summary: Visual summary text.
            visual_description: Detailed visual description.
            combined_text: Combined searchable text.
            tags: List of tags for filtering and search.
            thumbnail_url: URL to scene thumbnail.
            created_at: Creation timestamp.

        Returns:
            bool: True if upsert succeeded, False otherwise.
        """
        if not self.indexing_enabled:
            logger.debug("OpenSearch indexing disabled, skipping upsert")
            return True

        index_name = self.index_scenes

        # Build document
        doc = {
            "scene_id": scene_id,
            "video_id": video_id,
            "owner_id": owner_id,
            "index": index,
            "start_s": start_s,
            "end_s": end_s,
            "transcript_segment": transcript_segment or "",
            "visual_summary": visual_summary or "",
            "visual_description": visual_description or "",
            "combined_text": combined_text or "",
            "tags": tags or [],
            "tags_text": " ".join(tags) if tags else "",
            "thumbnail_url": thumbnail_url,
            "created_at": created_at.isoformat() if created_at else datetime.utcnow().isoformat(),
        }

        try:
            self.client.index(
                index=index_name,
                id=scene_id,  # Use scene_id as doc ID for idempotent upserts
                body=doc,
            )
            logger.debug(f"Upserted scene {scene_id} to OpenSearch")
            return True

        except OSConnectionError as e:
            logger.warning(f"OpenSearch connection error during upsert for scene {scene_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to upsert scene {scene_id} to OpenSearch: {e}")
            return False

    def delete_scene_doc(self, scene_id: str) -> bool:
        """Delete a scene document from OpenSearch.

        Args:
            scene_id: The scene ID to delete.

        Returns:
            bool: True if deleted or not found, False on error.
        """
        if not self.indexing_enabled:
            return True

        index_name = self.index_scenes

        try:
            self.client.delete(
                index=index_name,
                id=scene_id,
            )
            logger.debug(f"Deleted scene {scene_id} from OpenSearch")
            return True

        except NotFoundError:
            logger.debug(f"Scene {scene_id} not found in OpenSearch (already deleted)")
            return True
        except Exception as e:
            logger.error(f"Failed to delete scene {scene_id} from OpenSearch: {e}")
            return False

    def delete_scenes_for_video(self, video_id: str) -> bool:
        """Delete all scenes for a video from OpenSearch.

        Used when reprocessing a video.

        Args:
            video_id: The video ID whose scenes should be deleted.

        Returns:
            bool: True if deletion succeeded, False otherwise.
        """
        if not self.indexing_enabled:
            return True

        index_name = self.index_scenes

        try:
            self.client.delete_by_query(
                index=index_name,
                body={
                    "query": {
                        "term": {"video_id": video_id}
                    }
                },
            )
            logger.info(f"Deleted all scenes for video {video_id} from OpenSearch")
            return True

        except NotFoundError:
            logger.debug(f"Index {index_name} not found during delete_by_query")
            return True
        except Exception as e:
            logger.error(f"Failed to delete scenes for video {video_id}: {e}")
            return False

    def bulk_upsert(self, docs: list[dict]) -> tuple[int, int]:
        """Bulk upsert multiple scene documents.

        Args:
            docs: List of document dicts (must include scene_id).

        Returns:
            tuple[int, int]: (success_count, error_count)
        """
        if not self.indexing_enabled or not docs:
            return (len(docs), 0) if docs else (0, 0)

        index_name = self.index_scenes
        actions = []

        for doc in docs:
            scene_id = doc.get("scene_id")
            if not scene_id:
                continue

            # Ensure tags_text is populated
            if "tags" in doc and "tags_text" not in doc:
                doc["tags_text"] = " ".join(doc.get("tags", []))

            # Format for opensearchpy.helpers.bulk
            actions.append({
                "_op_type": "index",
                "_index": index_name,
                "_id": scene_id,
                "_source": doc,
            })

        if not actions:
            return (0, 0)

        try:
            from opensearchpy.helpers import bulk
            success, errors = bulk(
                self.client,
                actions,
                raise_on_error=False,
                raise_on_exception=False,
            )
            if errors:
                logger.warning(f"Bulk upsert had {len(errors)} errors")
                # Log first error for debugging
                if isinstance(errors, list) and len(errors) > 0:
                    logger.warning(f"First error: {errors[0]}")
            return (success, len(errors) if errors else 0)

        except Exception as e:
            logger.error(f"Bulk upsert failed: {e}")
            return (0, len(docs))


# No global instance - OpenSearchClient should be created via dependency injection
# in create_worker_context() with explicit configuration parameters
opensearch_client: Optional[OpenSearchClient] = None
