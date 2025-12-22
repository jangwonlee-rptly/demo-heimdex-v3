"""
RunPod CLIP Inference Adapter

This adapter provides a clean interface for calling the RunPod CLIP serverless endpoint.
It handles:
- HMAC authentication
- Retry logic with exponential backoff
- Error handling and logging
- Latency tracking

Usage:
    from adapters.clip_inference import get_clip_inference_client

    client = get_clip_inference_client()
    result = client.embed_image_url(
        image_url="https://storage.example.com/image.jpg",
        request_id="scene-123"
    )

    embedding = result["embedding"]  # List[float] with 512 dimensions
"""

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import settings

logger = logging.getLogger(__name__)


class ClipInferenceError(Exception):
    """Base exception for CLIP inference errors."""
    pass


class ClipInferenceAuthError(ClipInferenceError):
    """Authentication-related errors."""
    pass


class ClipInferenceNetworkError(ClipInferenceError):
    """Network and HTTP-related errors."""
    pass


class ClipInferenceTimeoutError(ClipInferenceError):
    """Timeout errors."""
    pass


class RunPodClipClient:
    """
    Client for calling RunPod CLIP serverless endpoint.

    Implements retry logic, HMAC authentication, and structured error handling.
    """

    def __init__(
        self,
        api_key: str,
        endpoint_id: str,
        hmac_secret: str,
        timeout_s: float = 60.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ):
        """
        Initialize RunPod CLIP client.

        Args:
            api_key: RunPod API key
            endpoint_id: RunPod endpoint ID
            hmac_secret: Shared secret for HMAC authentication
            timeout_s: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            backoff_factor: Exponential backoff multiplier
        """
        self.api_key = api_key
        self.endpoint_id = endpoint_id
        self.hmac_secret = hmac_secret
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        # Construct endpoint URL
        # RunPod sync endpoint: https://api.runpod.ai/v2/{endpoint_id}/runsync
        self.endpoint_url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"

        # Create session with retry logic
        self.session = self._create_session()

        logger.info(
            f"Initialized RunPodClipClient: endpoint_id={endpoint_id}, "
            f"timeout={timeout_s}s, max_retries={max_retries}"
        )

    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry logic.

        Retries on:
        - 5xx server errors (RunPod worker issues, cold starts)
        - 429 rate limiting
        - Connection errors
        - Timeouts

        Returns:
            Configured requests.Session
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[408, 429, 500, 502, 503, 504],
            allowed_methods=["POST"],
            raise_on_status=False,  # We'll handle status codes manually
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _generate_hmac_signature(self, image_url: str, timestamp: int) -> str:
        """
        Generate HMAC-SHA256 signature for authentication.

        Args:
            image_url: Image URL to sign
            timestamp: Unix timestamp

        Returns:
            Hexadecimal HMAC signature
        """
        message = f"{image_url}|{timestamp}"
        signature = hmac.new(
            self.hmac_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def embed_image_url(
        self,
        image_url: str,
        request_id: Optional[str] = None,
        normalize: bool = True,
        model: str = "ViT-B-32",
    ) -> Dict[str, Any]:
        """
        Generate CLIP embedding for an image URL.

        Args:
            image_url: Publicly accessible URL to image
            request_id: Optional request identifier for tracing
            normalize: Whether to L2-normalize the embedding
            model: Model name (informational, currently only ViT-B-32 supported)

        Returns:
            Dict with:
                - request_id: str
                - embedding: List[float] (512 dimensions)
                - dim: int
                - model: str
                - normalized: bool
                - timings: Dict[str, float]

        Raises:
            ClipInferenceAuthError: Authentication failures
            ClipInferenceNetworkError: Network/HTTP errors
            ClipInferenceTimeoutError: Request timeouts
            ClipInferenceError: Other errors
        """
        if not image_url:
            raise ValueError("image_url cannot be empty")

        # Validate URL format
        try:
            parsed = urlparse(image_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid URL format: {image_url}")
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")

        # Generate authentication
        timestamp = int(time.time())
        signature = self._generate_hmac_signature(image_url, timestamp)

        # Build request payload
        payload = {
            "input": {
                "image_url": image_url,
                "request_id": request_id or f"req-{int(time.time()*1000)}",
                "normalize": normalize,
                "model": model,
                "auth": {
                    "ts": timestamp,
                    "sig": signature,
                },
            }
        }

        # Prepare headers
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Make request with timing
        request_start = time.time()

        try:
            logger.debug(
                f"Calling RunPod CLIP endpoint: request_id={request_id}, "
                f"url={image_url[:100]}..."
            )

            response = self.session.post(
                self.endpoint_url,
                json=payload,
                headers=headers,
                timeout=self.timeout_s,
            )

            request_duration = time.time() - request_start

            # Log request details
            logger.info(
                f"RunPod request completed: status={response.status_code}, "
                f"duration={request_duration:.3f}s, request_id={request_id}"
            )

            # Handle HTTP errors
            if response.status_code == 401 or response.status_code == 403:
                raise ClipInferenceAuthError(
                    f"Authentication failed: {response.status_code} - {response.text}"
                )

            if response.status_code >= 500:
                raise ClipInferenceNetworkError(
                    f"Server error: {response.status_code} - {response.text}"
                )

            if response.status_code != 200:
                raise ClipInferenceNetworkError(
                    f"HTTP error: {response.status_code} - {response.text}"
                )

            # Parse response
            try:
                result = response.json()
            except Exception as e:
                raise ClipInferenceError(f"Failed to parse JSON response: {e}")

            # Check RunPod job status
            status = result.get("status")
            if status != "COMPLETED":
                error_msg = result.get("error", "Unknown error")
                raise ClipInferenceError(
                    f"RunPod job failed with status {status}: {error_msg}"
                )

            # Extract output
            output = result.get("output")
            if not output:
                raise ClipInferenceError("No output in RunPod response")

            # Check for errors in output
            if "error" in output:
                error_msg = output["error"]

                # Categorize errors
                if "Authentication failed" in error_msg:
                    raise ClipInferenceAuthError(f"RunPod auth error: {error_msg}")
                elif "timeout" in error_msg.lower() or "Timeout" in error_msg:
                    raise ClipInferenceTimeoutError(f"RunPod timeout: {error_msg}")
                else:
                    raise ClipInferenceError(f"RunPod error: {error_msg}")

            # Validate output structure
            if "embedding" not in output:
                raise ClipInferenceError("Missing 'embedding' in output")

            embedding = output["embedding"]
            if not isinstance(embedding, list):
                raise ClipInferenceError(f"Invalid embedding type: {type(embedding)}")

            expected_dim = 512
            if len(embedding) != expected_dim:
                raise ClipInferenceError(
                    f"Unexpected embedding dimension: {len(embedding)} (expected {expected_dim})"
                )

            # Log success with timing details
            timings = output.get("timings", {})
            logger.info(
                f"CLIP embedding generated successfully: request_id={request_id}, "
                f"dim={len(embedding)}, total_latency={request_duration*1000:.1f}ms, "
                f"inference_ms={timings.get('inference_ms', 'N/A')}"
            )

            return output

        except requests.exceptions.Timeout as e:
            duration = time.time() - request_start
            logger.error(f"RunPod request timeout after {duration:.1f}s: {e}")
            raise ClipInferenceTimeoutError(
                f"Request timeout after {duration:.1f}s: {e}"
            )

        except requests.exceptions.ConnectionError as e:
            duration = time.time() - request_start
            logger.error(f"RunPod connection error after {duration:.1f}s: {e}")
            raise ClipInferenceNetworkError(
                f"Connection error: {e}"
            )

        except requests.exceptions.RequestException as e:
            duration = time.time() - request_start
            logger.error(f"RunPod request failed after {duration:.1f}s: {e}")
            raise ClipInferenceNetworkError(
                f"Request failed: {e}"
            )

    def health_check(self) -> bool:
        """
        Check if RunPod endpoint is accessible.

        Returns:
            True if endpoint is accessible, False otherwise
        """
        try:
            # Try to make a simple request (will fail at validation but confirms connectivity)
            response = self.session.get(
                f"https://api.runpod.ai/v2/{self.endpoint_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            return response.status_code in [200, 404]  # 404 is fine for GET on sync endpoint
        except Exception as e:
            logger.warning(f"RunPod health check failed: {e}")
            return False


# Global singleton instance
_runpod_client: Optional[RunPodClipClient] = None


def get_clip_inference_client() -> Optional[RunPodClipClient]:
    """
    Get or create the global RunPod CLIP client instance.

    Returns None if RunPod backend is not configured.

    Returns:
        RunPodClipClient instance or None
    """
    global _runpod_client

    # Check if RunPod backend is enabled
    if settings.clip_inference_backend != "runpod":
        logger.debug(
            f"RunPod backend not enabled (backend={settings.clip_inference_backend})"
        )
        return None

    # Create singleton instance
    if _runpod_client is None:
        # Validate required configuration
        if not settings.runpod_api_key:
            logger.error("RUNPOD_API_KEY not configured")
            raise ValueError("RUNPOD_API_KEY is required when using RunPod backend")

        if not settings.runpod_clip_endpoint_id:
            logger.error("RUNPOD_CLIP_ENDPOINT_ID not configured")
            raise ValueError(
                "RUNPOD_CLIP_ENDPOINT_ID is required when using RunPod backend"
            )

        if not settings.embedding_hmac_secret:
            logger.error("EMBEDDING_HMAC_SECRET not configured")
            raise ValueError(
                "EMBEDDING_HMAC_SECRET is required when using RunPod backend"
            )

        _runpod_client = RunPodClipClient(
            api_key=settings.runpod_api_key,
            endpoint_id=settings.runpod_clip_endpoint_id,
            hmac_secret=settings.embedding_hmac_secret,
            timeout_s=settings.runpod_timeout_s,
            max_retries=3,
            backoff_factor=2.0,
        )

        logger.info("RunPod CLIP client initialized successfully")

    return _runpod_client


def embed_image_url(
    image_url: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to generate CLIP embedding from image URL.

    Args:
        image_url: Publicly accessible image URL
        request_id: Optional request identifier

    Returns:
        Dict with embedding and metadata

    Raises:
        ValueError: If RunPod backend not configured
        ClipInferenceError: If inference fails
    """
    client = get_clip_inference_client()

    if client is None:
        raise ValueError(
            f"RunPod CLIP client not available (backend={settings.clip_inference_backend})"
        )

    return client.embed_image_url(
        image_url=image_url,
        request_id=request_id,
        normalize=True,
        model=settings.clip_model_name,
    )
