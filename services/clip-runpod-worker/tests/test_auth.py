"""
Tests for HMAC authentication.
"""

import hashlib
import hmac
import time

import pytest

from app.schemas import AuthPayload
from app.security import (
    AuthError,
    create_canonical_message,
    generate_payload_hash,
    validate_auth,
)
from app.settings import Settings


def test_generate_payload_hash():
    """Test payload hash generation."""
    text = "hello world"
    expected = hashlib.sha256(text.encode()).hexdigest()
    assert generate_payload_hash(text) == expected


def test_create_canonical_message_image():
    """Test canonical message creation for image."""
    canonical = create_canonical_message(
        "POST", "/v1/embed/image", image_url="https://example.com/image.jpg"
    )
    assert canonical == "POST|/v1/embed/image|https://example.com/image.jpg"


def test_create_canonical_message_text():
    """Test canonical message creation for text."""
    text = "hello world"
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    canonical = create_canonical_message("POST", "/v1/embed/text", text=text)
    assert canonical == f"POST|/v1/embed/text|{text_hash}"


def test_validate_auth_success(monkeypatch):
    """Test successful authentication."""
    # Set up settings
    secret = "test-secret"
    monkeypatch.setattr("app.security.settings", Settings(embedding_hmac_secret=secret))

    # Create valid signature
    ts = int(time.time())
    payload = "POST|/v1/embed/image|https://example.com/image.jpg"
    message = f"{payload}|{ts}"
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    auth = AuthPayload(ts=ts, sig=sig)

    # Should not raise
    validate_auth(payload, auth, "test-request-id")


def test_validate_auth_signature_mismatch(monkeypatch):
    """Test authentication with wrong signature."""
    secret = "test-secret"
    monkeypatch.setattr("app.security.settings", Settings(embedding_hmac_secret=secret))

    ts = int(time.time())
    payload = "POST|/v1/embed/image|https://example.com/image.jpg"
    sig = "wrong_signature_" + ("a" * 48)

    auth = AuthPayload(ts=ts, sig=sig)

    with pytest.raises(AuthError) as exc_info:
        validate_auth(payload, auth, "test-request-id")
    assert "HMAC signature mismatch" in str(exc_info.value)


def test_validate_auth_timestamp_expired(monkeypatch):
    """Test authentication with expired timestamp."""
    secret = "test-secret"
    monkeypatch.setattr("app.security.settings", Settings(embedding_hmac_secret=secret))

    # Timestamp from 5 minutes ago (outside default 120s window)
    ts = int(time.time()) - 300
    payload = "POST|/v1/embed/image|https://example.com/image.jpg"
    message = f"{payload}|{ts}"
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    auth = AuthPayload(ts=ts, sig=sig)

    with pytest.raises(AuthError) as exc_info:
        validate_auth(payload, auth, "test-request-id")
    assert "timestamp outside allowed window" in str(exc_info.value).lower()


def test_validate_auth_no_secret_insecure_mode(monkeypatch):
    """Test authentication with no secret but insecure mode enabled."""
    monkeypatch.setattr(
        "app.security.settings", Settings(embedding_hmac_secret="", allow_insecure_auth=True)
    )

    ts = int(time.time())
    payload = "POST|/v1/embed/image|https://example.com/image.jpg"
    auth = AuthPayload(ts=ts, sig="a" * 64)

    # Should not raise (insecure mode allows)
    validate_auth(payload, auth, "test-request-id")


def test_validate_auth_no_secret_secure_mode(monkeypatch):
    """Test authentication with no secret and secure mode (should fail)."""
    monkeypatch.setattr(
        "app.security.settings", Settings(embedding_hmac_secret="", allow_insecure_auth=False)
    )

    ts = int(time.time())
    payload = "POST|/v1/embed/image|https://example.com/image.jpg"
    auth = AuthPayload(ts=ts, sig="a" * 64)

    with pytest.raises(AuthError) as exc_info:
        validate_auth(payload, auth, "test-request-id")
    assert "not configured" in str(exc_info.value).lower()
