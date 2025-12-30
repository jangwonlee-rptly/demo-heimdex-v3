"""OpenSearch client adapter for hybrid search."""
import logging
from typing import Optional
from uuid import UUID

from opensearchpy import OpenSearch
from opensearchpy.exceptions import (
    ConnectionError as OSConnectionError,
    NotFoundError,
    RequestError,
)

logger = logging.getLogger(__name__)

# Index mapping for scene documents
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
    """OpenSearch client for BM25 lexical search."""

    def __init__(self, url: str, timeout_s: float = 1.0, index_name: str = "scene_docs"):
        """Initialize the OpenSearch client.

        Args:
            url: OpenSearch server URL (e.g., "http://opensearch:9200")
            timeout_s: Request timeout in seconds
            index_name: Name of the scene index
        """
        self._client: Optional[OpenSearch] = None
        self._available: Optional[bool] = None
        self._url = url
        self._timeout_s = timeout_s
        self._index_name = index_name

    @property
    def client(self) -> OpenSearch:
        """Lazily initialize and return the OpenSearch client."""
        if self._client is None:
            self._client = OpenSearch(
                hosts=[self._url],
                timeout=self._timeout_s,
                max_retries=1,
                retry_on_timeout=False,
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

    def is_available(self) -> bool:
        """Check if OpenSearch is available (with caching for the request).

        Returns:
            bool: True if available, False otherwise.
        """
        if self._available is None:
            self._available = self.ping()
        return self._available

    def reset_availability_cache(self) -> None:
        """Reset the availability cache for next check."""
        self._available = None

    def check_nori_plugin(self) -> bool:
        """Check if the analysis-nori plugin is installed.

        Returns:
            bool: True if nori plugin is available, False otherwise.
        """
        try:
            # Get node info to check installed plugins
            node_info = self.client.nodes.info(node_id="_all", filter_path="nodes.*.plugins")

            for node_id, node_data in node_info.get("nodes", {}).items():
                plugins = node_data.get("plugins", [])
                for plugin in plugins:
                    plugin_name = plugin.get("name", "")
                    if "nori" in plugin_name.lower():
                        logger.info(f"Nori plugin found: {plugin_name}")
                        return True

            logger.warning("Nori plugin not found in OpenSearch installation")
            return False
        except Exception as e:
            logger.error(f"Failed to check nori plugin: {e}")
            return False

    def ensure_index(self) -> bool:
        """Ensure the scene index exists with proper mapping.

        Returns:
            bool: True if index exists or was created, False on error.
        """
        index_name = self._index_name

        # Log plugin availability (non-fatal check)
        try:
            self.check_nori_plugin()
        except Exception as e:
            logger.warning(f"Could not check nori plugin availability: {e}")

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

    def bm25_search(
        self,
        query: str,
        owner_id: str,
        video_id: Optional[str] = None,
        size: int = 200,
    ) -> list[dict]:
        """Search scenes using BM25 lexical matching.

        Args:
            query: The search query text.
            owner_id: Filter by owner ID (required for security).
            video_id: Optional filter by video ID.
            size: Maximum number of results to return.

        Returns:
            list[dict]: List of search results with scene_id, score, and rank.
        """
        if not self.is_available():
            logger.warning("OpenSearch not available, skipping BM25 search")
            return []

        index_name = self._index_name

        # Build filter conditions
        filter_conditions = [{"term": {"owner_id": owner_id}}]
        if video_id:
            filter_conditions.append({"term": {"video_id": video_id}})

        # Multi-match query across text fields with boosts
        # Search both Korean (.ko) and English (.en) analyzed subfields plus base field
        search_body = {
            "size": size,
            "query": {
                "bool": {
                    "filter": filter_conditions,
                    "should": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    # Tags - highest boost
                                    "tags_text^4",
                                    "tags_text.ko^4",
                                    "tags_text.en^4",
                                    # Transcript - high boost
                                    "transcript_segment^3",
                                    "transcript_segment.ko^3",
                                    "transcript_segment.en^3",
                                    # Visual description - medium boost
                                    "visual_description^2",
                                    "visual_description.ko^2",
                                    "visual_description.en^2",
                                    # Visual summary - medium boost
                                    "visual_summary^2",
                                    "visual_summary.ko^2",
                                    "visual_summary.en^2",
                                    # Combined text - base boost
                                    "combined_text^1",
                                    "combined_text.ko^1",
                                    "combined_text.en^1",
                                ],
                                "type": "best_fields",
                                "operator": "or",
                                "minimum_should_match": "2<75%",
                            }
                        }
                    ],
                    "minimum_should_match": 1,
                }
            },
            "_source": ["scene_id"],
        }

        try:
            response = self.client.search(
                index=index_name,
                body=search_body,
            )

            results = []
            for rank, hit in enumerate(response["hits"]["hits"], start=1):
                results.append({
                    "scene_id": hit["_source"]["scene_id"],
                    "score": hit["_score"],
                    "rank": rank,
                })

            logger.debug(f"BM25 search returned {len(results)} results for query: {query[:50]}...")
            return results

        except NotFoundError:
            logger.warning(f"Index {index_name} not found, returning empty results")
            return []
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def get_index_stats(self) -> Optional[dict]:
        """Get index statistics for debugging.

        Returns:
            Optional[dict]: Index stats or None if unavailable.
        """
        if not self.is_available():
            return None

        try:
            index_name = self._index_name
            stats = self.client.indices.stats(index=index_name)
            return {
                "doc_count": stats["_all"]["primaries"]["docs"]["count"],
                "size_bytes": stats["_all"]["primaries"]["store"]["size_in_bytes"],
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return None


# DEPRECATED: Global instance removed for Phase 1 refactor.
# Use dependency injection instead via get_opensearch() from dependencies.py
opensearch_client: OpenSearchClient = None  # type: ignore
