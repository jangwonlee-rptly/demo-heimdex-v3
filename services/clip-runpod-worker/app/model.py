"""
CLIP model loading and inference.
"""

import logging
import time
from typing import List

import open_clip
import torch
from PIL import Image

from app.settings import settings

logger = logging.getLogger(__name__)


class CLIPModel:
    """
    CLIP model wrapper for image and text embedding generation.

    Loads model once at initialization and provides thread-safe inference methods.
    """

    def __init__(self):
        """Initialize CLIP model (loads on first call to load())."""
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self.device = None
        self.model_name = None
        self.pretrained = None
        self.load_time_s = None

    def load(self) -> None:
        """
        Load CLIP model into memory.

        This should be called once at application startup.

        Raises:
            RuntimeError: If model loading fails
        """
        if self.model is not None:
            logger.info("Model already loaded, skipping initialization")
            return

        logger.info("=" * 60)
        logger.info("Loading CLIP model...")
        logger.info("=" * 60)
        logger.info(f"torch version: {torch.__version__}")
        logger.info(f"torch.version.cuda: {torch.version.cuda}")
        logger.info(f"torch.cuda.is_available(): {torch.cuda.is_available()}")

        if torch.cuda.is_available():
            logger.info(f"CUDA device count: {torch.cuda.device_count()}")
            logger.info(f"CUDA device name: {torch.cuda.get_device_name(0)}")

        start_time = time.time()

        # Determine device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")

        # Load model
        self.model_name = settings.clip_model_name
        self.pretrained = settings.clip_pretrained

        try:
            model, _, preprocess = open_clip.create_model_and_transforms(
                model_name=self.model_name,
                pretrained=self.pretrained,
                device=self.device,
            )
            model.eval()  # Set to evaluation mode

            # Get tokenizer for text encoding
            tokenizer = open_clip.get_tokenizer(self.model_name)

            self.model = model
            self.preprocess = preprocess
            self.tokenizer = tokenizer
            self.load_time_s = time.time() - start_time

            logger.info(
                f"✓ CLIP model loaded successfully: {self.model_name} ({self.pretrained}) "
                f"in {self.load_time_s:.2f}s on {self.device}"
            )
            logger.info("=" * 60)

        except Exception as e:
            logger.exception(f"Failed to load CLIP model: {e}")
            raise RuntimeError(f"Failed to load CLIP model: {e}")

    def encode_image(self, image: Image.Image, normalize: bool = True) -> List[float]:
        """
        Generate CLIP embedding for an image.

        Args:
            image: PIL Image object (RGB)
            normalize: Whether to L2-normalize the embedding

        Returns:
            List of floats representing the 512-dimensional embedding

        Raises:
            RuntimeError: If model not loaded or inference fails
        """
        if self.model is None or self.preprocess is None:
            raise RuntimeError("CLIP model not loaded. Call load() first.")

        try:
            # Preprocess image
            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)

            # Run inference
            with torch.no_grad():
                embedding = self.model.encode_image(image_tensor)

                # Normalize if requested
                if normalize:
                    embedding = embedding / embedding.norm(dim=-1, keepdim=True)

                # Convert to list
                embedding_list = embedding.cpu().squeeze(0).tolist()

            return embedding_list

        except Exception as e:
            logger.error(f"Image encoding failed: {e}")
            raise RuntimeError(f"Image encoding failed: {e}")

    def encode_text(self, text: str, normalize: bool = True) -> List[float]:
        """
        Generate CLIP embedding for text.

        Args:
            text: Text string to embed
            normalize: Whether to L2-normalize the embedding

        Returns:
            List of floats representing the 512-dimensional embedding

        Raises:
            RuntimeError: If model not loaded or inference fails
        """
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("CLIP model not loaded. Call load() first.")

        try:
            # Tokenize text
            text_tokens = self.tokenizer([text]).to(self.device)

            # Run inference
            with torch.no_grad():
                embedding = self.model.encode_text(text_tokens)

                # Normalize if requested
                if normalize:
                    embedding = embedding / embedding.norm(dim=-1, keepdim=True)

                # Convert to list
                embedding_list = embedding.cpu().squeeze(0).tolist()

            return embedding_list

        except Exception as e:
            logger.error(f"Text encoding failed: {e}")
            raise RuntimeError(f"Text encoding failed: {e}")

    def encode_images_batch(
        self, images: List[Image.Image], normalize: bool = True
    ) -> List[List[float]]:
        """
        Generate CLIP embeddings for a batch of images (efficient GPU batching).

        Args:
            images: List of PIL Image objects (RGB)
            normalize: Whether to L2-normalize the embeddings

        Returns:
            List of embedding vectors (each 512 dimensions)

        Raises:
            RuntimeError: If model not loaded or inference fails
        """
        if self.model is None or self.preprocess is None:
            raise RuntimeError("CLIP model not loaded. Call load() first.")

        if not images:
            return []

        try:
            # Preprocess and stack all images into a single batch tensor
            image_tensors = [self.preprocess(img) for img in images]
            batch_tensor = torch.stack(image_tensors).to(self.device)

            # Run single batched inference
            with torch.no_grad():
                embeddings = self.model.encode_image(batch_tensor)

                # Normalize if requested
                if normalize:
                    embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)

                # Convert to list of lists
                embeddings_list = embeddings.cpu().tolist()

            return embeddings_list

        except Exception as e:
            logger.error(f"Batch image encoding failed: {e}")
            raise RuntimeError(f"Batch image encoding failed: {e}")

    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self.model is not None

    def get_metadata(self) -> dict:
        """Get model metadata."""
        return {
            "model_name": self.model_name,
            "pretrained": self.pretrained,
            "device": self.device,
            "load_time_s": self.load_time_s,
        }


# Global model singleton
_clip_model = CLIPModel()


def get_clip_model() -> CLIPModel:
    """
    Get the global CLIP model instance.

    Returns:
        CLIPModel instance

    Raises:
        RuntimeError: If model not loaded
    """
    if not _clip_model.is_loaded():
        raise RuntimeError("CLIP model not loaded")
    return _clip_model


def load_model_global() -> None:
    """
    Load CLIP model into global singleton.

    This should be called once at application startup.
    """
    _clip_model.load()
