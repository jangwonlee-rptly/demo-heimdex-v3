"""
HMAC authentication and security utilities.
"""

import hashlib
import hmac
import logging
import time
from typing import Optional

from app.schemas import AuthPayload
from app.settings import settings

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Authentication error."""

    pass


def validate_auth(
    payload: str, auth: AuthPayload, request_id: Optional[str] = None
) -> None:
    """
    Validate HMAC authentication for a request.

    Args:
        payload: The canonical payload string to sign (e.g., "POST|/v1/embed/image|ts|payload_hash")
        auth: Authentication payload with timestamp and signature
        request_id: Optional request ID for logging

    Raises:
        AuthError: If authentication fails
    """
    # Check if secret is configured
    if not settings.embedding_hmac_secret:
        if settings.allow_insecure_auth:
            logger.warning(
                f"HMAC secret not set but ALLOW_INSECURE_AUTH=true - "
                f"authentication disabled for request_id={request_id}"
            )
            return
        else:
            logger.error(
                f"HMAC secret not configured and ALLOW_INSECURE_AUTH=false - "
                f"authentication required but cannot be performed"
            )
            raise AuthError(
                "Server configuration error: authentication required but not configured"
            )

    # Validate timestamp (prevent replay attacks)
    try:
        request_ts = auth.ts
        current_ts = int(time.time())
        time_diff = abs(current_ts - request_ts)

        if time_diff > settings.auth_time_window_seconds:
            logger.error(
                f"Request timestamp outside allowed window: "
                f"time_diff={time_diff}s > {settings.auth_time_window_seconds}s, "
                f"request_id={request_id}"
            )
            raise AuthError(
                f"Request timestamp outside allowed window "
                f"({time_diff}s > {settings.auth_time_window_seconds}s)"
            )
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid timestamp: {e}, request_id={request_id}")
        raise AuthError(f"Invalid timestamp: {e}")

    # Validate HMAC signature
    # Canonical message includes timestamp
    message = f"{payload}|{request_ts}"
    expected_sig = hmac.new(
        settings.embedding_hmac_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, auth.sig):
        logger.error(f"HMAC signature mismatch for request_id={request_id}")
        raise AuthError("HMAC signature mismatch")

    logger.debug(f"Authentication successful for request_id={request_id}")


def generate_payload_hash(payload: str) -> str:
    """
    Generate SHA256 hash of payload for signing.

    Args:
        payload: Payload string to hash

    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_canonical_message(
    method: str, path: str, image_url: Optional[str] = None, text: Optional[str] = None
) -> str:
    """
    Create canonical message for signing.

    Format: {method}|{path}|{payload_identifier}

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        image_url: Image URL (for image embedding requests)
        text: Text content (for text embedding requests)

    Returns:
        Canonical message string
    """
    if image_url:
        payload_part = image_url
    elif text:
        # For text, use hash to avoid including full text in signature
        payload_part = generate_payload_hash(text)
    else:
        payload_part = ""

    return f"{method}|{path}|{payload_part}"
