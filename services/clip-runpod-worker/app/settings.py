"""
Application settings using pydantic-settings for environment configuration.
"""

import os
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    # Service metadata
    service_name: str = Field(default="clip-runpod-worker", description="Service name")
    version: str = Field(default="2.0.0", description="Service version")

    # Server configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of uvicorn workers (GPU not fork-safe, keep at 1)")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )

    # Security
    embedding_hmac_secret: str = Field(
        default="", description="HMAC secret for request authentication"
    )
    allow_insecure_auth: bool = Field(
        default=False, description="Allow requests without auth (dev mode only)"
    )
    auth_time_window_seconds: int = Field(
        default=120, description="HMAC timestamp tolerance window in seconds"
    )

    # CLIP model configuration
    clip_model_name: str = Field(default="ViT-B-32", description="CLIP model architecture")
    clip_pretrained: str = Field(default="openai", description="CLIP pretrained weights")

    # Image download limits
    max_image_size_bytes: int = Field(
        default=10 * 1024 * 1024, description="Maximum image download size (10MB)"
    )
    image_download_timeout_s: int = Field(
        default=30, description="Image download timeout in seconds"
    )
    download_concurrency: int = Field(
        default=8, description="Max concurrent downloads in batch requests"
    )

    # Batch processing limits
    max_batch_size: int = Field(
        default=16, description="Maximum batch size for batch endpoints"
    )
    total_request_timeout_s: int = Field(
        default=300, description="Total request timeout (soft limit)"
    )

    # Cache directories
    hf_home: str = Field(
        default=os.environ.get("HF_HOME", "/app/.cache/huggingface"),
        description="Hugging Face cache directory",
    )
    torch_home: str = Field(
        default=os.environ.get("TORCH_HOME", "/app/.cache/torch"),
        description="PyTorch cache directory",
    )

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
