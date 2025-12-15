"""Configuration for the API service."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    # Supabase configuration
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # Database configuration (Supabase Postgres)
    database_url: str

    # Redis configuration
    redis_url: str = "redis://redis:6379/0"

    # OpenAI configuration
    openai_api_key: str

    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000,http://frontend:3000"

    # Dramatiq broker configuration
    dramatiq_broker: str = "redis"

    # OpenSearch configuration (hybrid search)
    opensearch_url: str = "http://opensearch:9200"
    opensearch_index_scenes: str = "scene_docs"
    opensearch_timeout_s: float = 1.0

    # Hybrid search configuration
    hybrid_search_enabled: bool = True
    search_debug: bool = False
    rrf_k: int = 60
    candidate_k_dense: int = 200
    candidate_k_lexical: int = 200

    # Fusion method configuration
    # Options: "minmax_mean" (default) | "rrf"
    # minmax_mean: Min-Max normalize scores, then weighted arithmetic mean
    # rrf: Reciprocal Rank Fusion (rank-based, more stable with outliers)
    fusion_method: str = "minmax_mean"

    # Weights for minmax_mean fusion (must sum to 1.0)
    # dense (semantic/vector similarity) vs lexical (BM25 keyword matching)
    # Default 0.7/0.3 favors semantic understanding while preserving keyword signal
    fusion_weight_dense: float = 0.7
    fusion_weight_lexical: float = 0.3

    # Small epsilon to avoid division by zero in min-max normalization
    fusion_minmax_eps: float = 1e-9

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list.

        Returns:
            list[str]: A list of allowed origin URLs for CORS configuration.
        """
        return [origin.strip() for origin in self.api_cors_origins.split(",")]


# Global settings instance
settings = Settings()
