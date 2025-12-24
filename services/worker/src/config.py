"""Configuration for the Worker service."""
from typing import Optional

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
    visual_blur_threshold: float = 50.0  # Min blur score (Laplacian variance) for sharp frames
    visual_semantics_enabled: bool = True  # Enable/disable visual semantics entirely
    visual_semantics_model: str = "gpt-4o-mini"  # Model for visual analysis (upgraded from gpt-5-nano for better accuracy)
    visual_semantics_max_tokens: int = 600  # Max tokens for detailed visual descriptions (increased from 150 to support 500 char descriptions + entities + actions)
    visual_semantics_temperature: float = 0.0  # Temperature for visual analysis (0 = deterministic)
    visual_semantics_include_entities: bool = True  # Include main_entities in JSON response
    visual_semantics_include_actions: bool = True  # Include actions in JSON response
    visual_semantics_retry_on_no_content: bool = True  # Retry with next best frame if first returns no_content
    visual_semantics_max_frame_retries: int = 2  # Max frames to try before giving up (1 = no retries, 2 = try 2nd frame, etc.)

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

    # Multi-embedding configuration (Option B: per-channel embeddings)
    multi_embedding_enabled: bool = True  # Enable multi-channel embeddings (transcript, visual, summary)
    embedding_version: str = "v3-multi"  # Embedding schema version for v3 multi-channel

    # Per-channel embedding text limits (safety: prevent excessive token usage)
    embedding_transcript_max_length: int = 4800  # Max chars for transcript embedding (conservative for clean signal)
    embedding_visual_max_length: int = 3200  # Max chars for visual description + tags embedding
    embedding_summary_max_length: int = 2000  # Max chars for summary embedding (if available)

    # Channel-specific settings
    embedding_visual_include_tags: bool = True  # Include tags in visual channel embedding
    embedding_summary_enabled: bool = False  # Enable summary channel (set to True when summary field is implemented)

    # Embedding retry/backoff configuration (safety)
    embedding_max_retries: int = 3  # Max retry attempts per channel on transient failures
    embedding_retry_delay_s: float = 1.0  # Initial retry delay (exponential backoff)

    # Search text optimization (legacy single-embedding, kept for backward compat)
    search_text_max_length: int = 8000  # Max chars for embedding input
    search_text_transcript_weight: float = 0.6  # Relative priority of transcript in search text

    # OpenSearch configuration (hybrid search)
    opensearch_url: str = "http://opensearch:9200"
    opensearch_index_scenes: str = "scene_docs"
    opensearch_timeout_s: float = 2.0  # Slightly longer timeout for indexing operations
    opensearch_indexing_enabled: bool = True  # Enable/disable OpenSearch indexing

    # Transcription quality filtering configuration
    # These settings help filter out low-quality transcripts (BGM, music, noise)
    transcription_min_chars_for_speech: int = 40  # Minimum chars for valid speech
    transcription_min_speech_char_ratio: float = 0.3  # Min ratio of letters/Hangul vs total
    transcription_max_no_speech_prob: float = 0.8  # Above this, treat segment as no speech
    transcription_min_speech_segments_ratio: float = 0.3  # Min ratio of speech segments required
    transcription_music_markers: list[str] = [
        "♪", "♫", "♬", "♩",  # Music note symbols
        "[music]", "[Music]", "[MUSIC]",  # Common Whisper music tags
        "[음악]", "[배경음악]",  # Korean music tags
        "(music)", "(Music)",
    ]
    transcription_banned_phrases: list[str] = []  # Optional: phrases to filter as low-value

    # CLIP visual embedding configuration (CPU-friendly, Railway-safe)
    clip_enabled: bool = True  # Feature flag: enable CLIP visual embeddings (default: disabled)
    clip_model_name: str = "ViT-B-32"  # CLIP model architecture (ViT-B-32 = 512 dim, faster on CPU)
    clip_pretrained: str = "openai"  # Pretrained weights source (openai, laion400m, etc.)
    clip_device: str = "cpu"  # Device for inference: "cpu" or "cuda"
    clip_cache_dir: str = "/tmp/clip_cache"  # Directory for caching model weights
    clip_normalize: bool = True  # L2-normalize embeddings for cosine similarity (recommended)
    clip_timeout_s: float = 2.0  # Per-scene embedding timeout in seconds
    clip_max_image_size: int = 224  # Max image dimension (resize if larger to save memory)
    clip_frame_strategy: str = "best_quality"  # Frame selection: "best_quality" (current), "middle", "best_of_3" (future)
    clip_cpu_threads: Optional[int] = None  # Optional: limit torch CPU threads to prevent thrashing
    clip_debug_log: bool = False  # Enable verbose logging for CLIP embeddings

    # CLIP inference backend configuration (RunPod vs local)
    clip_inference_backend: str = "runpod_pod"  # Backend: "runpod_pod" (always-on HTTP), "runpod_serverless" (legacy), "local" (CPU in-process), "off" (disabled)
    clip_model_version: str = "openai-vit-b-32-v1"  # Model version identifier for idempotency/cache tracking

    # RunPod Pod configuration (for clip_inference_backend="runpod_pod")
    clip_pod_base_url: str = ""  # RunPod Pod proxy URL (e.g., https://xxxx-8000.proxy.runpod.net)
    clip_pod_timeout_s: float = 60.0  # HTTP request timeout for Pod

    # RunPod serverless configuration (for clip_inference_backend="runpod_serverless", legacy)
    runpod_api_key: str = ""  # RunPod API key (required for serverless backend)
    runpod_clip_endpoint_id: str = ""  # RunPod CLIP endpoint ID (required for serverless backend)
    runpod_timeout_s: float = 60.0  # RunPod request timeout in seconds (includes cold start)

    # HMAC security for RunPod endpoints (both Pod and Serverless)
    embedding_hmac_secret: str = ""  # Shared secret for HMAC authentication (required for RunPod backends)


# Global settings instance
settings = Settings()
