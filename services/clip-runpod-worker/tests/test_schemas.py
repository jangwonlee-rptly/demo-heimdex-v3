"""
Tests for Pydantic schemas.
"""

import pytest
from pydantic import ValidationError

from app.schemas import (
    AuthPayload,
    BatchEmbedImageRequest,
    EmbedImageRequest,
    EmbedTextRequest,
)


def test_auth_payload_valid():
    """Test valid AuthPayload."""
    auth = AuthPayload(ts=1703001234, sig="a" * 64)
    assert auth.ts == 1703001234
    assert auth.sig == "a" * 64


def test_auth_payload_invalid_timestamp():
    """Test AuthPayload with invalid timestamp."""
    with pytest.raises(ValidationError) as exc_info:
        AuthPayload(ts=0, sig="a" * 64)
    assert "Timestamp must be positive" in str(exc_info.value)


def test_auth_payload_invalid_signature_length():
    """Test AuthPayload with invalid signature length."""
    with pytest.raises(ValidationError) as exc_info:
        AuthPayload(ts=1703001234, sig="abc")
    assert "64-character hex string" in str(exc_info.value)


def test_embed_image_request_valid():
    """Test valid EmbedImageRequest."""
    req = EmbedImageRequest(
        image_url="https://example.com/image.jpg",
        request_id="test-123",
        normalize=True,
        auth=AuthPayload(ts=1703001234, sig="a" * 64),
    )
    assert str(req.image_url) == "https://example.com/image.jpg"
    assert req.request_id == "test-123"
    assert req.normalize is True


def test_embed_image_request_missing_auth():
    """Test EmbedImageRequest without auth."""
    with pytest.raises(ValidationError) as exc_info:
        EmbedImageRequest(
            image_url="https://example.com/image.jpg",
            request_id="test-123",
        )
    assert "auth" in str(exc_info.value).lower()


def test_embed_text_request_valid():
    """Test valid EmbedTextRequest."""
    req = EmbedTextRequest(
        text="a person walking in the rain",
        request_id="query-1",
        normalize=True,
        auth=AuthPayload(ts=1703001234, sig="a" * 64),
    )
    assert req.text == "a person walking in the rain"
    assert req.request_id == "query-1"


def test_embed_text_request_empty_text():
    """Test EmbedTextRequest with empty text."""
    with pytest.raises(ValidationError) as exc_info:
        EmbedTextRequest(
            text="",
            auth=AuthPayload(ts=1703001234, sig="a" * 64),
        )
    assert "at least 1 character" in str(exc_info.value).lower()


def test_batch_embed_image_request_valid():
    """Test valid BatchEmbedImageRequest."""
    req = BatchEmbedImageRequest(
        items=[
            {
                "image_url": "https://example.com/img1.jpg",
                "request_id": "scene-1",
                "normalize": True,
                "auth": {"ts": 1703001234, "sig": "a" * 64},
            },
            {
                "image_url": "https://example.com/img2.jpg",
                "request_id": "scene-2",
                "normalize": True,
                "auth": {"ts": 1703001234, "sig": "b" * 64},
            },
        ]
    )
    assert len(req.items) == 2
    assert req.items[0].request_id == "scene-1"


def test_batch_embed_image_request_empty():
    """Test BatchEmbedImageRequest with empty items."""
    with pytest.raises(ValidationError) as exc_info:
        BatchEmbedImageRequest(items=[])
    assert "at least 1 item" in str(exc_info.value).lower()


def test_batch_embed_image_request_too_large():
    """Test BatchEmbedImageRequest with too many items."""
    items = [
        {
            "image_url": f"https://example.com/img{i}.jpg",
            "request_id": f"scene-{i}",
            "normalize": True,
            "auth": {"ts": 1703001234, "sig": "a" * 64},
        }
        for i in range(20)
    ]
    with pytest.raises(ValidationError) as exc_info:
        BatchEmbedImageRequest(items=items)
    assert "at most 16 items" in str(exc_info.value).lower()
