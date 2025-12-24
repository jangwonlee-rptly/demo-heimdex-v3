"""
Pytest configuration and fixtures.
"""

import pytest


@pytest.fixture
def test_image_url():
    """Public test image URL."""
    return "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=512"


@pytest.fixture
def test_secret():
    """Test HMAC secret."""
    return "test-secret-key-for-testing"
