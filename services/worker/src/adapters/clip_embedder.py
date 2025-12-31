"""CLIP visual embedding client for CPU-friendly image embeddings.

This module provides a singleton ClipEmbedder that generates visual embeddings
from images using OpenCLIP models. Designed for Railway deployment with:
- CPU-first operation (no GPU required)
- Controlled memory footprint
- Graceful degradation on failures
- Model caching to local filesystem
- Timeout protection
- Feature flag support

Typical usage:
    embedder = ClipEmbedder()
    embedding, metadata = embedder.create_visual_embedding(
        image_path=Path("/tmp/scene_12_frame_0.jpg"),
        timeout_s=2.0
    )
"""

import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class ClipEmbeddingMetadata:
    """Metadata for CLIP visual embedding generation."""

    model_name: str
    pretrained: str
    embed_dim: int
    normalized: bool
    device: str
    frame_path: str
    frame_quality: Optional[dict] = None
    inference_time_ms: Optional[float] = None
    created_at: str = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Convert to dict for JSONB storage."""
        return {
            "model_name": self.model_name,
            "pretrained": self.pretrained,
            "embed_dim": self.embed_dim,
            "normalized": self.normalized,
            "device": self.device,
            "frame_path": self.frame_path,
            "frame_quality": self.frame_quality,
            "inference_time_ms": self.inference_time_ms,
            "created_at": self.created_at,
            "error": self.error,
        }


class ClipEmbedder:
    """Singleton CLIP embedder for visual similarity.

    Thread-safe singleton that lazy-loads OpenCLIP model on first use.
    Designed for CPU inference with Railway deployment in mind.

    Features:
    - Lazy model loading (only when first needed)
    - CPU-friendly (no GPU required)
    - Per-inference timeout protection
    - L2 normalization for cosine similarity
    - Model weight caching to local filesystem
    - Graceful error handling with metadata tracking
    - Small memory footprint (single model instance)

    Configuration via environment variables:
    - CLIP_ENABLED: Enable/disable CLIP embeddings (default: false)
    - CLIP_MODEL_NAME: Model architecture (default: "ViT-B-32")
    - CLIP_PRETRAINED: Pretrained weights (default: "openai")
    - CLIP_DEVICE: Device for inference (default: "cpu")
    - CLIP_CACHE_DIR: Model cache directory (default: "/tmp/clip_cache")
    - CLIP_NORMALIZE: L2-normalize embeddings (default: true)
    - CLIP_TIMEOUT_S: Per-inference timeout (default: 2.0)
    - CLIP_MAX_IMAGE_SIZE: Max image dimension (default: 224)
    - CLIP_DEBUG_LOG: Verbose logging (default: false)
    """

    _instance: Optional["ClipEmbedder"] = None
    _model = None
    _preprocess = None
    _device = None
    _embed_dim = None
    _initialized = False
    _settings = None  # Store settings injected via constructor

    def __new__(cls, settings=None):
        """Singleton pattern: return same instance.

        Args:
            settings: Ignored in __new__, but accepted for compatibility with __init__
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, settings=None):
        """Initialize with dependency-injected settings.

        Args:
            settings: Settings instance (required for DI pattern).
                     Must be provided when creating the embedder.
        """
        if not self._initialized:
            self._initialized = True
            # Store settings - must be provided via DI
            if settings is None:
                raise ValueError(
                    "ClipEmbedder requires settings to be provided via constructor. "
                    "Pass Settings instance when creating: ClipEmbedder(settings=settings)"
                )
            self._settings = settings
            logger.info(
                f"ClipEmbedder singleton created (enabled={self._settings.clip_enabled})"
            )

    def _ensure_model_loaded(self) -> bool:
        """Lazy-load CLIP model on first use.

        Returns:
            True if model loaded successfully, False otherwise.

        Side effects:
            Sets self._model, self._preprocess, self._device, self._embed_dim
        """
        if self._model is not None:
            return True

        if not self._settings.clip_enabled:
            logger.info("CLIP embeddings disabled via CLIP_ENABLED=false")
            return False

        try:
            import torch
            import open_clip

            start_time = time.time()

            # Determine device
            if self._settings.clip_device == "cuda" and torch.cuda.is_available():
                self._device = torch.device("cuda")
            else:
                self._device = torch.device("cpu")

            # Set CPU threads if on CPU (prevent thrashing)
            if self._device.type == "cpu":
                num_threads = getattr(self._settings, "clip_cpu_threads", None)
                if num_threads:
                    torch.set_num_threads(num_threads)
                    logger.info(f"Set torch CPU threads to {num_threads}")

            logger.info(
                f"Loading CLIP model: {self._settings.clip_model_name} "
                f"(pretrained={self._settings.clip_pretrained}, device={self._device})"
            )

            # Load model with cache directory
            cache_dir = Path(self._settings.clip_cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)

            model, _, preprocess = open_clip.create_model_and_transforms(
                model_name=self._settings.clip_model_name,
                pretrained=self._settings.clip_pretrained,
                device=self._device,
                cache_dir=str(cache_dir),
            )

            # Set to eval mode
            model.eval()

            # Get embedding dimension from model
            self._embed_dim = model.visual.output_dim

            self._model = model
            self._preprocess = preprocess

            load_time = (time.time() - start_time) * 1000

            logger.info(
                f"CLIP model loaded successfully: {self._settings.clip_model_name} "
                f"(embed_dim={self._embed_dim}, device={self._device}, "
                f"load_time={load_time:.1f}ms, cache_dir={cache_dir})"
            )

            if self._settings.clip_debug_log:
                logger.debug(
                    f"CLIP model details: {model.__class__.__name__}, "
                    f"preprocess={preprocess}"
                )

            return True

        except ImportError as e:
            logger.error(
                f"Failed to import CLIP dependencies: {e}. "
                "Install with: pip install open_clip_torch torch pillow"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}", exc_info=True)
            return False

    def _create_embedding_impl(
        self, image_path: Path, quality_info: Optional[dict] = None
    ) -> tuple[Optional[list[float]], ClipEmbeddingMetadata]:
        """Internal implementation of embedding creation (no timeout).

        Args:
            image_path: Path to image file
            quality_info: Optional quality metrics from frame ranker

        Returns:
            Tuple of (embedding_vector, metadata)
        """
        import torch

        start_time = time.time()

        metadata = ClipEmbeddingMetadata(
            model_name=self._settings.clip_model_name,
            pretrained=self._settings.clip_pretrained,
            embed_dim=self._embed_dim,
            normalized=self._settings.clip_normalize,
            device=str(self._device),
            frame_path=str(image_path.name),
            frame_quality=quality_info,
        )

        try:
            # Load and preprocess image
            image = Image.open(image_path).convert("RGB")

            # Optional: resize if too large (memory safety)
            if self._settings.clip_max_image_size:
                max_size = self._settings.clip_max_image_size
                if max(image.size) > max_size:
                    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Preprocess for model
            image_tensor = self._preprocess(image).unsqueeze(0).to(self._device)

            # Generate embedding with no gradient
            with torch.inference_mode():
                embedding = self._model.encode_image(image_tensor)

                # L2 normalize if configured (recommended for cosine similarity)
                if self._settings.clip_normalize:
                    embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)

                # Convert to list
                embedding_list = embedding.squeeze(0).cpu().numpy().tolist()

            inference_time = (time.time() - start_time) * 1000
            metadata.inference_time_ms = round(inference_time, 2)

            if self._settings.clip_debug_log:
                logger.debug(
                    f"CLIP embedding created: {image_path.name}, "
                    f"dim={len(embedding_list)}, time={inference_time:.1f}ms, "
                    f"norm={torch.norm(embedding).item():.4f}"
                )

            return embedding_list, metadata

        except FileNotFoundError:
            metadata.error = f"Image not found: {image_path}"
            logger.error(metadata.error)
            return None, metadata
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            # Truncate long error messages
            if len(error_msg) > 200:
                error_msg = error_msg[:197] + "..."
            metadata.error = error_msg
            logger.error(
                f"CLIP embedding failed for {image_path.name}: {e}", exc_info=True
            )
            return None, metadata

    def create_visual_embedding(
        self,
        image_path: Path,
        quality_info: Optional[dict] = None,
        timeout_s: Optional[float] = None,
    ) -> tuple[Optional[list[float]], ClipEmbeddingMetadata]:
        """Create CLIP visual embedding from image with timeout protection.

        Args:
            image_path: Path to image file (JPEG, PNG, etc.)
            quality_info: Optional quality metrics from frame ranker
                         (brightness, blur, quality_score)
            timeout_s: Optional timeout in seconds (default: from settings.clip_timeout_s)

        Returns:
            Tuple of (embedding_vector, metadata):
            - embedding_vector: list[float] of length embed_dim (e.g., 512 for ViT-B-32)
                               or None if embedding failed
            - metadata: ClipEmbeddingMetadata with model info, inference time, errors

        Raises:
            Never raises - all errors are caught and returned in metadata.error
        """
        # Return early if CLIP disabled
        if not self._settings.clip_enabled:
            metadata = ClipEmbeddingMetadata(
                model_name="disabled",
                pretrained="disabled",
                embed_dim=0,
                normalized=False,
                device="none",
                frame_path=str(image_path.name),
                error="CLIP embeddings disabled via CLIP_ENABLED=false",
            )
            return None, metadata

        # Ensure model loaded
        if not self._ensure_model_loaded():
            metadata = ClipEmbeddingMetadata(
                model_name=self._settings.clip_model_name,
                pretrained=self._settings.clip_pretrained,
                embed_dim=0,
                normalized=False,
                device="unknown",
                frame_path=str(image_path.name),
                error="Failed to load CLIP model",
            )
            return None, metadata

        # Use configured timeout if not specified
        if timeout_s is None:
            timeout_s = self._settings.clip_timeout_s

        # Execute with timeout protection
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self._create_embedding_impl, image_path, quality_info
                )
                embedding, metadata = future.result(timeout=timeout_s)
                return embedding, metadata

        except FuturesTimeoutError:
            metadata = ClipEmbeddingMetadata(
                model_name=self._settings.clip_model_name,
                pretrained=self._settings.clip_pretrained,
                embed_dim=self._embed_dim or 0,
                normalized=self._settings.clip_normalize,
                device=str(self._device) if self._device else "unknown",
                frame_path=str(image_path.name),
                frame_quality=quality_info,
                error=f"Timeout after {timeout_s}s",
            )
            logger.warning(
                f"CLIP embedding timeout for {image_path.name} "
                f"(limit={timeout_s}s)"
            )
            return None, metadata
        except Exception as e:
            # Should not happen due to internal error handling, but safety net
            metadata = ClipEmbeddingMetadata(
                model_name=self._settings.clip_model_name,
                pretrained=self._settings.clip_pretrained,
                embed_dim=self._embed_dim or 0,
                normalized=self._settings.clip_normalize,
                device=str(self._device) if self._device else "unknown",
                frame_path=str(image_path.name),
                frame_quality=quality_info,
                error=f"Unexpected error: {type(e).__name__}",
            )
            logger.error(
                f"Unexpected CLIP embedding error for {image_path.name}: {e}",
                exc_info=True,
            )
            return None, metadata

    def get_embedding_dim(self) -> Optional[int]:
        """Get embedding dimension of loaded model.

        Returns:
            Embedding dimension (e.g., 512 for ViT-B-32) or None if not loaded
        """
        if self._model is None:
            self._ensure_model_loaded()
        return self._embed_dim

    def is_available(self) -> bool:
        """Check if CLIP embeddings are available.

        Returns:
            True if model is loaded and ready, False otherwise
        """
        if not self._settings.clip_enabled:
            return False
        return self._ensure_model_loaded()
