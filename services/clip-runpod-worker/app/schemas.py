"""
Pydantic schemas for request/response validation.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ============================================================================
# Authentication
# ============================================================================


class AuthPayload(BaseModel):
    """HMAC authentication payload."""

    ts: int = Field(..., description="Unix timestamp when request was created")
    sig: str = Field(..., description="HMAC-SHA256 signature")

    @field_validator("ts")
    @classmethod
    def validate_timestamp(cls, v: int) -> int:
        """Validate timestamp is positive."""
        if v <= 0:
            raise ValueError("Timestamp must be positive")
        return v

    @field_validator("sig")
    @classmethod
    def validate_signature(cls, v: str) -> str:
        """Validate signature is non-empty hex string."""
        if not v or len(v) != 64:
            raise ValueError("Signature must be 64-character hex string (SHA256)")
        return v


# ============================================================================
# Single Image Embedding
# ============================================================================


class EmbedImageRequest(BaseModel):
    """Request schema for single image embedding."""

    image_url: HttpUrl = Field(..., description="Image URL to embed")
    request_id: Optional[str] = Field(None, description="Request identifier for tracing")
    normalize: bool = Field(default=True, description="L2-normalize embedding")
    auth: AuthPayload = Field(..., description="HMAC authentication")


class Timings(BaseModel):
    """Timing breakdown for operations."""

    download_ms: Optional[float] = Field(None, description="Image download time in ms")
    inference_ms: Optional[float] = Field(None, description="Model inference time in ms")
    total_ms: float = Field(..., description="Total processing time in ms")


class EmbedImageResponse(BaseModel):
    """Response schema for single image embedding."""

    request_id: str = Field(..., description="Request identifier")
    embedding: List[float] = Field(..., description="512-dimensional embedding vector")
    dim: int = Field(..., description="Embedding dimension (512)")
    model_name: str = Field(..., description="Model name (e.g., ViT-B-32)")
    pretrained: str = Field(..., description="Pretrained weights (e.g., openai)")
    device: str = Field(..., description="Device used (cuda/cpu)")
    normalized: bool = Field(..., description="Whether embedding is L2-normalized")
    timings: Timings = Field(..., description="Timing breakdown")


# ============================================================================
# Batch Image Embedding
# ============================================================================


class BatchEmbedImageItem(BaseModel):
    """Single item in batch embedding request."""

    image_url: HttpUrl = Field(..., description="Image URL to embed")
    request_id: str = Field(..., description="Request identifier (required for batch)")
    normalize: bool = Field(default=True, description="L2-normalize embedding")
    auth: AuthPayload = Field(..., description="HMAC authentication")


class BatchEmbedImageRequest(BaseModel):
    """Request schema for batch image embedding."""

    items: List[BatchEmbedImageItem] = Field(
        ..., min_length=1, max_length=16, description="Batch of images to embed (max 16)"
    )


class BatchEmbedImageItemResult(BaseModel):
    """Single item result in batch response (success case)."""

    request_id: str = Field(..., description="Request identifier")
    embedding: List[float] = Field(..., description="512-dimensional embedding vector")
    dim: int = Field(..., description="Embedding dimension (512)")
    normalized: bool = Field(..., description="Whether embedding is L2-normalized")
    timings: Timings = Field(..., description="Timing breakdown")


class BatchEmbedImageItemError(BaseModel):
    """Single item error in batch response."""

    request_id: str = Field(..., description="Request identifier")
    error: "ErrorDetail" = Field(..., description="Error details")


class BatchTimings(BaseModel):
    """Timing breakdown for batch operations."""

    total_download_ms: float = Field(..., description="Total download time across all images")
    total_inference_ms: float = Field(..., description="Total inference time (single GPU batch)")
    total_ms: float = Field(..., description="Total batch processing time")


class BatchEmbedImageResponse(BaseModel):
    """Response schema for batch image embedding."""

    results: List[BatchEmbedImageItemResult | BatchEmbedImageItemError] = Field(
        ..., description="Per-item results or errors"
    )
    model_name: str = Field(..., description="Model name (e.g., ViT-B-32)")
    pretrained: str = Field(..., description="Pretrained weights (e.g., openai)")
    device: str = Field(..., description="Device used (cuda/cpu)")
    batch_timings: BatchTimings = Field(..., description="Batch timing breakdown")


# ============================================================================
# Text Embedding
# ============================================================================


class EmbedTextRequest(BaseModel):
    """Request schema for text embedding."""

    text: str = Field(..., min_length=1, max_length=10000, description="Text to embed")
    request_id: Optional[str] = Field(None, description="Request identifier for tracing")
    normalize: bool = Field(default=True, description="L2-normalize embedding")
    auth: AuthPayload = Field(..., description="HMAC authentication")


class EmbedTextResponse(BaseModel):
    """Response schema for text embedding."""

    request_id: str = Field(..., description="Request identifier")
    embedding: List[float] = Field(..., description="512-dimensional embedding vector")
    dim: int = Field(..., description="Embedding dimension (512)")
    model_name: str = Field(..., description="Model name (e.g., ViT-B-32)")
    pretrained: str = Field(..., description="Pretrained weights (e.g., openai)")
    device: str = Field(..., description="Device used (cuda/cpu)")
    normalized: bool = Field(..., description="Whether embedding is L2-normalized")
    timings: Timings = Field(..., description="Timing breakdown")


# ============================================================================
# Health Check
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status (ok/degraded)")
    model_name: str = Field(..., description="Loaded model name")
    pretrained: str = Field(..., description="Pretrained weights")
    device: str = Field(..., description="Device (cuda/cpu)")
    torch_version: str = Field(..., description="PyTorch version")
    cuda_version: Optional[str] = Field(None, description="CUDA version (if available)")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")


# ============================================================================
# Error Responses
# ============================================================================


class ErrorDetail(BaseModel):
    """Structured error detail."""

    code: str = Field(..., description="Error code (e.g., AUTH_FAILED, DOWNLOAD_ERROR)")
    message: str = Field(..., description="Human-readable error message")
    request_id: Optional[str] = Field(None, description="Request identifier")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail = Field(..., description="Error details")


# Update forward references
BatchEmbedImageItemError.model_rebuild()
