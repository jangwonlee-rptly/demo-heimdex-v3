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
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Scene detection configuration
    scene_detector: str = "adaptive"  # Scene detection strategy: "adaptive" or "content"
    scene_min_len_seconds: float = 1.0  # Minimum scene length in seconds

    # AdaptiveDetector parameters (used when scene_detector="adaptive")
    scene_adaptive_threshold: float = 3.0  # Adaptive threshold for scene changes
    scene_adaptive_window_width: int = 2  # Rolling window width for adaptive detection
    scene_adaptive_min_content_val: float = 15.0  # Minimum content value to trigger detection

    # ContentDetector parameters (used when scene_detector="content")
    scene_content_threshold: float = 27.0  # Content threshold (pyscenedetect default)

    # Parallel processing configuration
    max_scene_workers: int = 3  # Max concurrent scenes to process in parallel
    max_api_concurrency: int = 3  # Max concurrent API calls (respects rate limits)

    # Visual semantics optimization configuration
    visual_brightness_threshold: float = 15.0  # Min brightness (0-255) for informative frames
    visual_blur_threshold: float = 100.0  # Min blur score (Laplacian variance) for sharp frames
    visual_semantics_enabled: bool = True  # Enable/disable visual semantics entirely
    visual_semantics_model: str = "gpt-5-nano"  # Model for visual analysis (cheaper variant)
    visual_semantics_max_tokens: int = 128  # Max tokens for visual analysis response
    visual_semantics_temperature: float = 0.0  # Temperature for visual analysis (0 = deterministic)
    visual_semantics_include_entities: bool = True  # Include main_entities in JSON response
    visual_semantics_include_actions: bool = True  # Include actions in JSON response

    # Cost optimization: minimum scene duration (seconds) to trigger visual analysis
    # Scenes shorter than this will skip visual analysis if transcript is available
    visual_semantics_min_duration_s: float = 1.5

    # Cost optimization: minimum transcript length (chars) to consider "rich" transcript
    # If transcript is longer than this, visual analysis may be skipped for short scenes
    visual_semantics_transcript_threshold: int = 50

    # Cost optimization: force visual analysis if transcript is empty/short
    # even for very short scenes
    visual_semantics_force_on_no_transcript: bool = True

    # Sidecar schema version for future migrations
    sidecar_schema_version: str = "v2"

    # Search text optimization
    search_text_max_length: int = 8000  # Max chars for embedding input
    search_text_transcript_weight: float = 0.6  # Relative priority of transcript in search text


# Global settings instance
settings = Settings()
