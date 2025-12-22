"""
RunPod Serverless Worker for CLIP Image Embedding Generation

This handler:
1. Loads CLIP model once at startup (global singleton)
2. Uses GPU when available (cuda)
3. Accepts image URLs with HMAC authentication
4. Returns normalized embedding vectors

Input schema:
{
  "image_url": "https://signed-url-to-thumbnail",
  "request_id": "scene-uuid",
  "normalize": true,
  "model": "ViT-B-32",
  "auth": { "ts": 1730000000, "sig": "..." }
}

Output schema:
{
  "request_id": "scene-uuid",
  "embedding": [ ... ],
  "dim": 512,
  "model": "ViT-B-32",
  "normalized": true
}
"""

import hashlib
import hmac
import io
import logging
import os
import time
from typing import Any, Dict, List, Optional

import open_clip
import requests
import runpod
import torch
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
EMBEDDING_HMAC_SECRET = os.environ.get("EMBEDDING_HMAC_SECRET", "")
MAX_IMAGE_SIZE_BYTES = int(os.environ.get("MAX_IMAGE_SIZE_BYTES", 10 * 1024 * 1024))  # 10MB
IMAGE_DOWNLOAD_TIMEOUT = int(os.environ.get("IMAGE_DOWNLOAD_TIMEOUT", 30))  # 30 seconds
AUTH_TIME_WINDOW_SECONDS = int(os.environ.get("AUTH_TIME_WINDOW_SECONDS", 120))  # 2 minutes
DEFAULT_MODEL_NAME = os.environ.get("CLIP_MODEL_NAME", "ViT-B-32")
DEFAULT_PRETRAINED = os.environ.get("CLIP_PRETRAINED", "openai")

# Global model singleton (loaded once at startup)
_model = None
_preprocess = None
_device = None
_model_name = None
_pretrained = None


def load_model_global() -> None:
    """
    Load CLIP model into global variables at startup.
    This runs once when the worker initializes.
    """
    global _model, _preprocess, _device, _model_name, _pretrained

    if _model is not None:
        logger.info("Model already loaded, skipping initialization")
        return

    logger.info("Initializing CLIP model...")
    start_time = time.time()

    # Determine device
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {_device}")

    # Load model
    _model_name = DEFAULT_MODEL_NAME
    _pretrained = DEFAULT_PRETRAINED

    try:
        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name=_model_name,
            pretrained=_pretrained,
            device=_device,
        )
        model.eval()  # Set to evaluation mode

        _model = model
        _preprocess = preprocess

        load_time = time.time() - start_time
        logger.info(
            f"CLIP model loaded successfully: {_model_name} ({_pretrained}) "
            f"in {load_time:.2f}s on {_device}"
        )

    except Exception as e:
        logger.error(f"Failed to load CLIP model: {e}")
        raise


def validate_auth(image_url: str, auth: Dict[str, Any]) -> bool:
    """
    Validate HMAC signature for request authentication.

    Args:
        image_url: The image URL from the request
        auth: Dict with "ts" (timestamp) and "sig" (signature)

    Returns:
        True if authentication is valid, False otherwise
    """
    if not EMBEDDING_HMAC_SECRET:
        logger.warning("EMBEDDING_HMAC_SECRET not set - authentication disabled")
        return True

    if not auth or "ts" not in auth or "sig" not in auth:
        logger.error("Missing auth fields in request")
        return False

    # Validate timestamp (prevent replay attacks)
    try:
        request_ts = int(auth["ts"])
        current_ts = int(time.time())
        time_diff = abs(current_ts - request_ts)

        if time_diff > AUTH_TIME_WINDOW_SECONDS:
            logger.error(
                f"Request timestamp outside allowed window: "
                f"{time_diff}s > {AUTH_TIME_WINDOW_SECONDS}s"
            )
            return False
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid timestamp: {e}")
        return False

    # Validate HMAC signature
    # Message format: image_url|ts
    message = f"{image_url}|{request_ts}"
    expected_sig = hmac.new(
        EMBEDDING_HMAC_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, auth["sig"]):
        logger.error("HMAC signature mismatch")
        return False

    return True


def download_image(image_url: str) -> Image.Image:
    """
    Download image from URL with safety limits.

    Args:
        image_url: URL to download from

    Returns:
        PIL Image object

    Raises:
        ValueError: If download fails or exceeds limits
    """
    try:
        logger.info(f"Downloading image from: {image_url[:100]}...")

        response = requests.get(
            image_url,
            timeout=IMAGE_DOWNLOAD_TIMEOUT,
            stream=True,
        )
        response.raise_for_status()

        # Check content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Image too large: {content_length} bytes > {MAX_IMAGE_SIZE_BYTES}"
            )

        # Download with size limit
        image_data = io.BytesIO()
        downloaded_bytes = 0

        for chunk in response.iter_content(chunk_size=8192):
            downloaded_bytes += len(chunk)
            if downloaded_bytes > MAX_IMAGE_SIZE_BYTES:
                raise ValueError(
                    f"Image download exceeded {MAX_IMAGE_SIZE_BYTES} bytes"
                )
            image_data.write(chunk)

        image_data.seek(0)
        image = Image.open(image_data).convert("RGB")

        logger.info(f"Image downloaded successfully: {image.size}")
        return image

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download image: {e}")
        raise ValueError(f"Image download failed: {e}")
    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        raise ValueError(f"Image processing failed: {e}")


def generate_embedding(image: Image.Image, normalize: bool = True) -> List[float]:
    """
    Generate CLIP embedding for an image.

    Args:
        image: PIL Image object
        normalize: Whether to L2-normalize the embedding

    Returns:
        List of floats representing the embedding vector

    Raises:
        RuntimeError: If model not loaded or inference fails
    """
    if _model is None or _preprocess is None:
        raise RuntimeError("CLIP model not loaded")

    try:
        # Preprocess image
        image_tensor = _preprocess(image).unsqueeze(0).to(_device)

        # Run inference
        with torch.no_grad():
            embedding = _model.encode_image(image_tensor)

            # Normalize if requested
            if normalize:
                embedding = embedding / embedding.norm(dim=-1, keepdim=True)

            # Convert to list
            embedding_list = embedding.cpu().squeeze(0).tolist()

        logger.info(f"Generated embedding with {len(embedding_list)} dimensions")
        return embedding_list

    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise RuntimeError(f"Embedding generation failed: {e}")


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod handler function - processes a single job.

    Args:
        job: RunPod job dict with "input" containing request parameters

    Returns:
        Dict with embedding result or error
    """
    job_input = job.get("input", {})

    # Extract parameters
    image_url = job_input.get("image_url")
    request_id = job_input.get("request_id", "unknown")
    normalize = job_input.get("normalize", True)
    model_override = job_input.get("model", _model_name)
    auth = job_input.get("auth", {})

    logger.info(f"Processing request: {request_id}")

    # Validate required fields
    if not image_url:
        return {
            "error": "Missing required field: image_url",
            "request_id": request_id,
        }

    # Validate authentication
    if not validate_auth(image_url, auth):
        return {
            "error": "Authentication failed",
            "request_id": request_id,
        }

    # Warn if model override requested (not supported in this version)
    if model_override != _model_name:
        logger.warning(
            f"Model override requested ({model_override}) but only "
            f"{_model_name} is loaded. Using loaded model."
        )

    try:
        # Download image
        start_time = time.time()
        image = download_image(image_url)
        download_time = time.time() - start_time

        # Generate embedding
        inference_start = time.time()
        embedding = generate_embedding(image, normalize=normalize)
        inference_time = time.time() - inference_start

        total_time = time.time() - start_time

        logger.info(
            f"Request {request_id} completed in {total_time:.3f}s "
            f"(download: {download_time:.3f}s, inference: {inference_time:.3f}s)"
        )

        # Return result
        return {
            "request_id": request_id,
            "embedding": embedding,
            "dim": len(embedding),
            "model": _model_name,
            "pretrained": _pretrained,
            "normalized": normalize,
            "timings": {
                "download_ms": round(download_time * 1000, 2),
                "inference_ms": round(inference_time * 1000, 2),
                "total_ms": round(total_time * 1000, 2),
            },
        }

    except ValueError as e:
        logger.error(f"Request {request_id} failed: {e}")
        return {
            "error": str(e),
            "request_id": request_id,
        }
    except RuntimeError as e:
        logger.error(f"Request {request_id} failed: {e}")
        return {
            "error": str(e),
            "request_id": request_id,
        }
    except Exception as e:
        logger.error(f"Request {request_id} failed with unexpected error: {e}")
        return {
            "error": f"Unexpected error: {e}",
            "request_id": request_id,
        }


# Initialize model at startup
load_model_global()

# Start RunPod serverless worker
if __name__ == "__main__":
    logger.info("Starting RunPod CLIP worker...")
    runpod.serverless.start({"handler": handler})
