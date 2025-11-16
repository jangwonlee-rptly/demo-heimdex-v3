"""Configuration for the Worker service."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    # Supabase configuration
    supabase_url: str
    supabase_service_role_key: str

    # Database configuration (Supabase Postgres)
    database_url: str

    # Redis configuration
    redis_url: str = "redis://redis:6379/0"

    # OpenAI configuration
    openai_api_key: str

    # Processing configuration
    temp_dir: str = "/tmp/heimdex"
    max_keyframes_per_scene: int = 3
    scene_detection_threshold: float = 27.0  # pyscenedetect default
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536


# Global settings instance
settings = Settings()
