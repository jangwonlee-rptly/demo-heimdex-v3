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

    # CLIP RunPod configuration (for visual search)
    clip_runpod_url: str = ""  # e.g., "https://api-xxxx.runpod.net"
    clip_runpod_secret: str = ""  # HMAC secret for auth
    clip_text_embedding_timeout_s: float = 1.5
    clip_text_embedding_max_retries: int = 1

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

    # Admin configuration
    admin_user_ids: str = ""  # Comma-separated UUIDs of admin users

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

    # Multi-embedding dense retrieval configuration (Option B: per-channel embeddings)
    multi_dense_enabled: bool = False
    multi_dense_timeout_s: float = 1.5  # Timeout per retrieval task (not whole request)

    # Per-channel candidate K values (how many results to fetch from each channel)
    candidate_k_transcript: int = 200
    candidate_k_visual: int = 200
    candidate_k_summary: int = 200
    # candidate_k_lexical already defined above

    # Per-channel similarity thresholds (0.0 to 1.0)
    threshold_transcript: float = 0.2
    threshold_visual: float = 0.15  # Lower threshold for visual (text often short/sparse)
    threshold_summary: float = 0.2

    # Multi-channel fusion weights (must sum to 1.0)
    # Default allocation: transcript is most important, lexical helps with keywords,
    # visual adds context, summary provides overview
    weight_transcript: float = 0.45
    weight_visual: float = 0.25
    weight_summary: float = 0.10
    weight_lexical_multi: float = 0.20  # Separate from fusion_weight_lexical for legacy mode

    # Multi-dense fusion method (reuses fusion_method setting)
    # Options: "minmax_mean" (default) | "rrf"

    # Visual search mode configuration
    # Options: "recall" | "rerank" | "auto"
    # - recall: CLIP participates in retrieval (parallel topK + fusion)
    # - rerank: CLIP only reranks candidates from other channels (more stable)
    # - auto: use visual intent router to decide per-query
    visual_mode: str = "auto"

    # Rerank mode configuration
    rerank_candidate_pool_size: int = 500  # How many candidates to retrieve before CLIP rerank
    rerank_clip_weight: float = 0.3  # CLIP contribution in rerank blend (0.0-1.0)
    rerank_min_score_range: float = 0.05  # Skip CLIP if score range < this (flat scores)

    # Visual intent router configuration (for auto mode)
    visual_router_boost_weight: float = 0.15  # Additional weight for visual queries in auto mode
    visual_router_reduce_weight: float = 0.05  # Reduced weight for speech queries in auto mode

    # Feature flags
    enable_user_search_weights: bool = True  # Enable user-customizable search weights

    # Fusion percentile clipping (optional outlier control)
    fusion_percentile_clip_enabled: bool = False
    fusion_percentile_clip_lo: float = 0.05  # 5th percentile
    fusion_percentile_clip_hi: float = 0.95  # 95th percentile

    # Weight guardrails
    max_visual_weight: float = 0.8  # Cap visual weight (prevent sparse match over-reliance)
    min_lexical_weight: float = 0.05  # Minimum lexical weight (preserve keyword signal)

    # Display score calibration (UI confidence metric, does not affect ranking)
    # When enabled, adds a 'display_score' field to search results that is calibrated
    # per-query to avoid overconfident "100%" displays on mediocre matches.
    enable_display_score_calibration: bool = False
    display_score_method: str = "exp_squash"  # Options: "exp_squash", "pctl_ceiling"
    display_score_max_cap: float = 0.97  # Maximum display score (typically 0.95-0.97)
    display_score_alpha: float = 3.0  # Exponential squashing parameter (2.0-5.0, higher = more aggressive)

    # Lookup soft lexical gating (reduces false positives for brand/name queries)
    # When enabled, detects lookup-like queries (brands, proper nouns) and prefers
    # lexical matches when available. If lexical has no hits, falls back to dense
    # retrieval but labels results as "best guess" in the UI.
    enable_lookup_soft_gating: bool = False
    lookup_lexical_min_hits: int = 1  # Minimum lexical hits to trigger allowlist mode
    lookup_fallback_mode: str = "dense_best_guess"  # Future-proof: fallback strategy
    lookup_label_mode: str = "api_field"  # How to communicate match quality (api_field | message)

    # Lookup absolute display score calibration (for best_guess fallback)
    # When lookup fallback is used (lexical_hits=0), calibrate display_score using
    # absolute dense similarity instead of fused score to avoid overconfident ~95% displays
    enable_lookup_absolute_display_score: bool = False
    lookup_abs_sim_floor: float = 0.20  # Min raw similarity for linear mapping
    lookup_abs_sim_ceil: float = 0.55   # Max raw similarity for linear mapping
    lookup_best_guess_max_cap: float = 0.65  # Max display score for best_guess (lower than supported)

    def validate_multi_dense_weights(self) -> tuple[bool, str, dict[str, float]]:
        """Validate and redistribute multi-dense channel weights.

        Returns:
            tuple: (is_valid, error_message, redistributed_weights)
                   If valid, error_message is empty and redistributed_weights contains
                   the normalized weights. If a channel is disabled (weight=0),
                   its weight is redistributed proportionally to other channels.

        Raises:
            None: Returns error information instead of raising
        """
        weights = {
            "transcript": self.weight_transcript,
            "visual": self.weight_visual,
            "summary": self.weight_summary,
            "lexical": self.weight_lexical_multi,
        }

        # Validate all weights are in [0, 1]
        for channel, weight in weights.items():
            if not (0.0 <= weight <= 1.0):
                return (
                    False,
                    f"Channel '{channel}' weight must be in [0, 1], got {weight}",
                    {},
                )

        # Check if weights sum to ~1.0 (with tolerance)
        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 1e-6:
            return (
                False,
                f"Multi-dense channel weights must sum to 1.0, got {total_weight:.6f} "
                f"(transcript={self.weight_transcript}, visual={self.weight_visual}, "
                f"summary={self.weight_summary}, lexical={self.weight_lexical_multi})",
                {},
            )

        # Filter out zero-weight channels and redistribute
        active_weights = {ch: w for ch, w in weights.items() if w > 0.0}

        if not active_weights:
            return (
                False,
                "At least one channel must have non-zero weight",
                {},
            )

        # Redistribute weights to sum to 1.0 (handles floating-point precision)
        active_total = sum(active_weights.values())
        redistributed = {
            ch: w / active_total for ch, w in active_weights.items()
        }

        return (True, "", redistributed)

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list.

        Returns:
            list[str]: A list of allowed origin URLs for CORS configuration.
        """
        return [origin.strip() for origin in self.api_cors_origins.split(",")]

    @property
    def admin_user_ids_list(self) -> list[str]:
        """Parse admin user IDs into a list.

        Returns:
            list[str]: A list of admin user UUIDs.
        """
        if not self.admin_user_ids:
            return []
        return [uid.strip() for uid in self.admin_user_ids.split(",") if uid.strip()]


# DEPRECATED: Module-level settings instance removed for Phase 1 refactor.
# Settings are now created at app startup (main.py lifespan) and injected via dependencies.
# This remains as None to prevent import-time side effects.
# Use get_settings() dependency injection in routes instead.
settings: Settings = None  # type: ignore
