"""CLIP RunPod client for visual search text embeddings.

This module provides a client for the CLIP RunPod service to generate
512-dimensional CLIP text embeddings for visual similarity search.
These embeddings live in the same vector space as CLIP image embeddings,
enabling true multimodal visual search.
"""
import hashlib
import hmac
import logging
import time
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class ClipClientError(Exception):
    """Base exception for CLIP client errors."""
    pass


class ClipTimeoutError(ClipClientError):
    """CLIP request timed out."""
    pass


class ClipAuthError(ClipClientError):
    """CLIP authentication failed."""
    pass


class ClipClient:
    """Client for CLIP RunPod text embedding service.

    Generates 512-dimensional CLIP text embeddings that can be compared
    against CLIP image embeddings for visual similarity search.

    Features:
    - HMAC authentication (same as image endpoint)
    - Timeout protection
    - Retry logic for transient failures
    - Connection pooling
    - Detailed error logging
    """

    def __init__(
        self,
        base_url: str,
        secret_key: str,
        timeout_s: float = 1.5,
        max_retries: int = 1,
    ):
        """Initialize CLIP client.

        Args:
            base_url: Base URL of CLIP RunPod service (e.g., "https://api-xxx.runpod.net")
            secret_key: HMAC secret for authentication
            timeout_s: Request timeout in seconds
            max_retries: Number of retries for transient failures (0 = no retries)
        """
        self.base_url = base_url.rstrip("/")
        self.secret_key = secret_key
        self.timeout_s = timeout_s
        self.max_retries = max_retries

        # Create persistent HTTP client with connection pooling
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout_s),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

        logger.info(
            f"ClipClient initialized: base_url={base_url}, "
            f"timeout={timeout_s}s, max_retries={max_retries}"
        )

    def _create_hmac_signature(self, method: str, path: str, timestamp: int, text: Optional[str] = None) -> str:
        """Create HMAC-SHA256 signature for request authentication.

        Matches the RunPod service's expected format:
        1. Canonical message: {method}|{path}|{text_hash}
        2. Final message: {canonical_message}|{timestamp}

        Args:
            method: HTTP method (e.g., "POST")
            path: Request path (e.g., "/v1/embed/text")
            timestamp: Unix timestamp
            text: Optional text to hash (for text embedding requests)

        Returns:
            Hex-encoded HMAC signature
        """
        # Create canonical message matching RunPod service format
        if text:
            # Hash the text content (don't include raw text in signature)
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            canonical_message = f"{method}|{path}|{text_hash}"
        else:
            canonical_message = f"{method}|{path}|"

        # Append timestamp to canonical message
        message_to_sign = f"{canonical_message}|{timestamp}"

        # Generate HMAC signature
        signature = hmac.new(
            self.secret_key.encode(),
            message_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()

        return signature

    def create_text_embedding(
        self,
        text: str,
        normalize: bool = True,
        request_id: Optional[str] = None,
    ) -> list[float]:
        """Generate CLIP text embedding for visual similarity search.

        Args:
            text: Query text to embed
            normalize: Whether to L2-normalize the embedding (default: True)
            request_id: Optional request ID for logging/tracing

        Returns:
            list[float]: 512-dimensional CLIP text embedding

        Raises:
            ClipTimeoutError: If request times out
            ClipAuthError: If authentication fails
            ClipClientError: For other errors (network, service, etc.)
        """
        if not text or not text.strip():
            raise ClipClientError("Text cannot be empty")

        request_id = request_id or f"clip-{int(time.time() * 1000)}"
        start_time = time.time()

        # Prepare request
        endpoint = "/v1/embed/text"
        url = f"{self.base_url}{endpoint}"

        # Create HMAC signature with timestamp
        timestamp = int(time.time())
        signature = self._create_hmac_signature("POST", endpoint, timestamp, text=text)

        payload = {
            "text": text,
            "normalize": normalize,
            "request_id": request_id,
            "auth": {
                "ts": timestamp,
                "sig": signature,
            },
        }

        # Execute with retries
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f"CLIP text embedding request: request_id={request_id}, "
                    f"text_len={len(text)}, attempt={attempt + 1}/{self.max_retries + 1}"
                )

                response = self.client.post(url, json=payload)

                # Check for errors
                if response.status_code == 401:
                    raise ClipAuthError(
                        f"CLIP authentication failed: {response.text[:200]}"
                    )

                if response.status_code != 200:
                    raise ClipClientError(
                        f"CLIP service error (status={response.status_code}): "
                        f"{response.text[:200]}"
                    )

                # Parse response
                data = response.json()
                embedding = data.get("embedding")

                if not embedding or not isinstance(embedding, list):
                    raise ClipClientError(
                        f"Invalid CLIP response format: missing or invalid 'embedding' field"
                    )

                elapsed_ms = (time.time() - start_time) * 1000

                logger.info(
                    f"CLIP text embedding success: request_id={request_id}, "
                    f"dim={len(embedding)}, elapsed_ms={elapsed_ms:.1f}, "
                    f"attempts={attempt + 1}"
                )

                return embedding

            except httpx.TimeoutException as e:
                last_error = ClipTimeoutError(
                    f"CLIP request timed out after {self.timeout_s}s"
                )
                logger.warning(
                    f"CLIP timeout: request_id={request_id}, "
                    f"attempt={attempt + 1}/{self.max_retries + 1}"
                )

            except httpx.NetworkError as e:
                last_error = ClipClientError(f"CLIP network error: {e}")
                logger.warning(
                    f"CLIP network error: request_id={request_id}, "
                    f"error={e}, attempt={attempt + 1}/{self.max_retries + 1}"
                )

            except (ClipAuthError, ClipClientError):
                # Don't retry auth errors or client errors
                raise

            except Exception as e:
                last_error = ClipClientError(f"CLIP unexpected error: {type(e).__name__}: {e}")
                logger.error(
                    f"CLIP unexpected error: request_id={request_id}, error={e}",
                    exc_info=True,
                )

            # Wait before retry (exponential backoff)
            if attempt < self.max_retries:
                wait_ms = 100 * (2 ** attempt)  # 100ms, 200ms, 400ms, ...
                time.sleep(wait_ms / 1000)

        # All retries exhausted
        logger.error(
            f"CLIP embedding failed after {self.max_retries + 1} attempts: "
            f"request_id={request_id}, last_error={last_error}"
        )
        raise last_error

    def close(self):
        """Close the HTTP client and release resources."""
        self.client.close()
        logger.info("ClipClient closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global CLIP client instance (lazy-initialized)
_clip_client: Optional[ClipClient] = None


def get_clip_client() -> ClipClient:
    """Get or create the global CLIP client instance.

    Returns:
        ClipClient: Singleton CLIP client

    Raises:
        ClipClientError: If CLIP is not configured
    """
    global _clip_client

    if _clip_client is None:
        if not settings.clip_runpod_url or not settings.clip_runpod_secret:
            raise ClipClientError(
                "CLIP client not configured: missing CLIP_RUNPOD_URL or CLIP_RUNPOD_SECRET"
            )

        _clip_client = ClipClient(
            base_url=settings.clip_runpod_url,
            secret_key=settings.clip_runpod_secret,
            timeout_s=settings.clip_text_embedding_timeout_s,
            max_retries=settings.clip_text_embedding_max_retries,
        )

    return _clip_client


def is_clip_available() -> bool:
    """Check if CLIP client is available and configured.

    Returns:
        bool: True if CLIP is configured and available
    """
    try:
        get_clip_client()
        return True
    except ClipClientError:
        return False
