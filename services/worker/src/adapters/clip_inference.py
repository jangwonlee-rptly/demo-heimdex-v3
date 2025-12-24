"""
CLIP Inference Adapter

This adapter provides a clean interface for calling CLIP embedding services.
Supports multiple backends:
- RunPod Pod (always-on HTTP service) - recommended
- RunPod Serverless (legacy, GPU serverless)
- Local (CPU in-process)

It handles:
- HMAC authentication
- Retry logic with exponential backoff
- Error handling and logging
- Latency tracking
- Batch processing (Pod backend only)

Usage:
    from adapters.clip_inference import get_clip_inference_client

    client = get_clip_inference_client()

    # Single image
    result = client.embed_image_url(
        image_url="https://storage.example.com/image.jpg",
        request_id="scene-123"
    )
    embedding = result["embedding"]  # List[float] with 512 dimensions

    # Batch (Pod backend only)
    results = client.embed_image_batch([
        {"image_url": "https://...", "request_id": "scene-1"},
        {"image_url": "https://...", "request_id": "scene-2"},
    ])

    # Text embedding (Pod backend only)
    result = client.embed_text(
        text="a person walking in the rain",
        request_id="query-1"
    )
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


class RunPodPodClipClient:
    """
    Client for calling RunPod Pod CLIP HTTP service (always-on).

    Implements HMAC authentication, batch processing, and text embedding.
    """

    def __init__(
        self,
        base_url: str,
        hmac_secret: str,
        timeout_s: float = 60.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ):
        """
        Initialize RunPod Pod CLIP client.

        Args:
            base_url: Pod proxy URL (e.g., https://xxxx-8000.proxy.runpod.net)
            hmac_secret: Shared secret for HMAC authentication
            timeout_s: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            backoff_factor: Exponential backoff multiplier
        """
        self.base_url = base_url.rstrip("/")
        self.hmac_secret = hmac_secret
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        # Create session with retry logic
        self.session = self._create_session()

        logger.info(
            f"Initialized RunPodPodClipClient: base_url={base_url}, "
            f"timeout={timeout_s}s, max_retries={max_retries}"
        )

    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry logic.

        Returns:
            Configured requests.Session
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[408, 429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _generate_hmac_signature(self, canonical_message: str, timestamp: int) -> str:
        """
        Generate HMAC-SHA256 signature for authentication.

        Args:
            canonical_message: Canonical message to sign (method|path|payload)
            timestamp: Unix timestamp

        Returns:
            Hexadecimal HMAC signature
        """
        message = f"{canonical_message}|{timestamp}"
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
            model: Model name (informational)

        Returns:
            Dict with embedding and metadata

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
        canonical = f"POST|/v1/embed/image|{image_url}"
        signature = self._generate_hmac_signature(canonical, timestamp)

        # Build request payload
        payload = {
            "image_url": image_url,
            "request_id": request_id or f"req-{int(time.time()*1000)}",
            "normalize": normalize,
            "auth": {
                "ts": timestamp,
                "sig": signature,
            },
        }

        # Make request
        url = f"{self.base_url}/v1/embed/image"
        request_start = time.time()

        try:
            logger.debug(
                f"Calling RunPod Pod CLIP: request_id={request_id}, url={image_url[:100]}..."
            )

            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout_s,
            )

            request_duration = time.time() - request_start

            logger.info(
                f"RunPod Pod request completed: status={response.status_code}, "
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

            # Validate response structure
            if "embedding" not in result:
                raise ClipInferenceError("Missing 'embedding' in response")

            embedding = result["embedding"]
            if not isinstance(embedding, list):
                raise ClipInferenceError(f"Invalid embedding type: {type(embedding)}")

            expected_dim = 512
            if len(embedding) != expected_dim:
                raise ClipInferenceError(
                    f"Unexpected embedding dimension: {len(embedding)} (expected {expected_dim})"
                )

            logger.info(
                f"CLIP embedding generated successfully: request_id={request_id}, "
                f"dim={len(embedding)}, total_latency={request_duration*1000:.1f}ms"
            )

            return result

        except requests.exceptions.Timeout as e:
            duration = time.time() - request_start
            logger.error(f"RunPod Pod request timeout after {duration:.1f}s: {e}")
            raise ClipInferenceTimeoutError(f"Request timeout after {duration:.1f}s: {e}")

        except requests.exceptions.ConnectionError as e:
            duration = time.time() - request_start
            logger.error(f"RunPod Pod connection error after {duration:.1f}s: {e}")
            raise ClipInferenceNetworkError(f"Connection error: {e}")

        except requests.exceptions.RequestException as e:
            duration = time.time() - request_start
            logger.error(f"RunPod Pod request failed after {duration:.1f}s: {e}")
            raise ClipInferenceNetworkError(f"Request failed: {e}")

    def embed_image_batch(
        self, items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate CLIP embeddings for a batch of images.

        Args:
            items: List of dicts with keys: image_url, request_id, normalize (optional)

        Returns:
            List of results (same order as input), each with either:
            - Success: {"request_id": ..., "embedding": [...], ...}
            - Error: {"request_id": ..., "error": {...}}

        Raises:
            ClipInferenceError: If batch request fails entirely
        """
        if not items:
            return []

        # Generate auth for each item
        batch_items = []
        timestamp = int(time.time())

        for item in items:
            image_url = item["image_url"]
            request_id = item.get("request_id", f"batch-{int(time.time()*1000)}")
            normalize = item.get("normalize", True)

            canonical = f"POST|/v1/embed/image-batch|{image_url}"
            signature = self._generate_hmac_signature(canonical, timestamp)

            batch_items.append({
                "image_url": image_url,
                "request_id": request_id,
                "normalize": normalize,
                "auth": {
                    "ts": timestamp,
                    "sig": signature,
                },
            })

        # Make batch request
        url = f"{self.base_url}/v1/embed/image-batch"
        request_start = time.time()

        try:
            logger.debug(f"Calling RunPod Pod CLIP batch: batch_size={len(batch_items)}")

            response = self.session.post(
                url,
                json={"items": batch_items},
                timeout=self.timeout_s,
            )

            request_duration = time.time() - request_start

            if response.status_code != 200:
                raise ClipInferenceError(
                    f"Batch request failed: {response.status_code} - {response.text}"
                )

            result = response.json()
            results = result.get("results", [])

            logger.info(
                f"Batch request completed: batch_size={len(batch_items)}, "
                f"duration={request_duration:.3f}s"
            )

            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"Batch request failed: {e}")
            raise ClipInferenceError(f"Batch request failed: {e}")

    def embed_text(
        self,
        text: str,
        request_id: Optional[str] = None,
        normalize: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate CLIP embedding for text.

        Args:
            text: Text to embed
            request_id: Optional request identifier
            normalize: Whether to L2-normalize the embedding

        Returns:
            Dict with embedding and metadata

        Raises:
            ClipInferenceError: If request fails
        """
        if not text:
            raise ValueError("text cannot be empty")

        # Generate authentication
        timestamp = int(time.time())
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        canonical = f"POST|/v1/embed/text|{text_hash}"
        signature = self._generate_hmac_signature(canonical, timestamp)

        # Build request payload
        payload = {
            "text": text,
            "request_id": request_id or f"txt-{int(time.time()*1000)}",
            "normalize": normalize,
            "auth": {
                "ts": timestamp,
                "sig": signature,
            },
        }

        # Make request
        url = f"{self.base_url}/v1/embed/text"
        request_start = time.time()

        try:
            logger.debug(f"Calling RunPod Pod CLIP text: request_id={request_id}")

            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout_s,
            )

            request_duration = time.time() - request_start

            if response.status_code != 200:
                raise ClipInferenceError(
                    f"Text embedding failed: {response.status_code} - {response.text}"
                )

            result = response.json()

            logger.info(
                f"Text embedding completed: request_id={request_id}, "
                f"duration={request_duration:.3f}s"
            )

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Text embedding request failed: {e}")
            raise ClipInferenceError(f"Text embedding failed: {e}")

    def health_check(self) -> bool:
        """
        Check if RunPod Pod is accessible.

        Returns:
            True if endpoint is accessible, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"RunPod Pod health check failed: {e}")
            return False


class RunPodServerlessClipClient:
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


# Global singleton instances
_runpod_pod_client: Optional[RunPodPodClipClient] = None
_runpod_serverless_client: Optional[RunPodServerlessClipClient] = None


def get_clip_inference_client():
    """
    Get or create the global CLIP client instance based on configured backend.

    Returns None if no backend is configured.

    Returns:
        RunPodPodClipClient, RunPodServerlessClipClient, or None

    Raises:
        ValueError: If backend is configured but required settings are missing
    """
    global _runpod_pod_client, _runpod_serverless_client

    backend = settings.clip_inference_backend

    # RunPod Pod (always-on HTTP) - recommended
    if backend == "runpod_pod":
        if _runpod_pod_client is None:
            # Validate required configuration
            if not settings.clip_pod_base_url:
                logger.error("CLIP_POD_BASE_URL not configured")
                raise ValueError(
                    "CLIP_POD_BASE_URL is required when using runpod_pod backend"
                )

            if not settings.embedding_hmac_secret:
                logger.error("EMBEDDING_HMAC_SECRET not configured")
                raise ValueError(
                    "EMBEDDING_HMAC_SECRET is required when using runpod_pod backend"
                )

            _runpod_pod_client = RunPodPodClipClient(
                base_url=settings.clip_pod_base_url,
                hmac_secret=settings.embedding_hmac_secret,
                timeout_s=settings.clip_pod_timeout_s,
                max_retries=3,
                backoff_factor=2.0,
            )

            logger.info("RunPod Pod CLIP client initialized successfully")

        return _runpod_pod_client

    # RunPod Serverless (legacy)
    elif backend == "runpod_serverless" or backend == "runpod":
        if backend == "runpod":
            logger.warning(
                "Backend 'runpod' is deprecated, use 'runpod_serverless' or 'runpod_pod'"
            )

        if _runpod_serverless_client is None:
            # Validate required configuration
            if not settings.runpod_api_key:
                logger.error("RUNPOD_API_KEY not configured")
                raise ValueError(
                    "RUNPOD_API_KEY is required when using runpod_serverless backend"
                )

            if not settings.runpod_clip_endpoint_id:
                logger.error("RUNPOD_CLIP_ENDPOINT_ID not configured")
                raise ValueError(
                    "RUNPOD_CLIP_ENDPOINT_ID is required when using runpod_serverless backend"
                )

            if not settings.embedding_hmac_secret:
                logger.error("EMBEDDING_HMAC_SECRET not configured")
                raise ValueError(
                    "EMBEDDING_HMAC_SECRET is required when using runpod_serverless backend"
                )

            _runpod_serverless_client = RunPodServerlessClipClient(
                api_key=settings.runpod_api_key,
                endpoint_id=settings.runpod_clip_endpoint_id,
                hmac_secret=settings.embedding_hmac_secret,
                timeout_s=settings.runpod_timeout_s,
                max_retries=3,
                backoff_factor=2.0,
            )

            logger.info("RunPod Serverless CLIP client initialized successfully")

        return _runpod_serverless_client

    # Local or off
    else:
        logger.debug(f"CLIP backend not configured for remote inference: {backend}")
        return None


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
