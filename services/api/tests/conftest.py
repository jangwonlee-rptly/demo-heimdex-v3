"""Pytest configuration and shared fixtures for Heimdex API tests.

This module provides reusable fixtures for:
- FastAPI test client
- Mock database clients
- Mock external services (OpenAI, Supabase Storage)
- Test data factories
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock
from uuid import uuid4, UUID
from datetime import datetime

from src.main import app
from src.domain.models import Video, VideoStatus, UserProfile


# ============================================================================
# FastAPI Test Client
# ============================================================================


@pytest.fixture
def client(mock_user_id):
    """
    FastAPI test client for making requests to the API.

    This fixture automatically mocks authentication to bypass JWT validation.

    Args:
        mock_user_id: Fixture providing test user ID

    Yields:
        TestClient: Configured test client with mocked auth
    """
    from src.auth.middleware import User

    # Mock the get_current_user dependency to bypass authentication
    def mock_get_current_user():
        return User(
            user_id=str(mock_user_id),
            email="test@example.com",
            role="authenticated"
        )

    # Override the dependency
    from src.auth import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()


# ============================================================================
# Mock Authentication
# ============================================================================


@pytest.fixture
def mock_user_id() -> UUID:
    """
    Mock user ID for testing authenticated endpoints.

    Returns:
        UUID: A fixed test user ID
    """
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def mock_auth_token() -> str:
    """
    Mock JWT token for authenticated requests.

    Returns:
        str: A mock Bearer token
    """
    return "mock_jwt_token_for_testing"


@pytest.fixture
def auth_headers(mock_auth_token: str) -> dict:
    """
    HTTP headers with authentication for API requests.

    Args:
        mock_auth_token: Mock JWT token fixture

    Returns:
        dict: Headers dictionary with Authorization
    """
    return {"Authorization": f"Bearer {mock_auth_token}"}


# ============================================================================
# Mock Database
# ============================================================================


@pytest.fixture
def mock_db():
    """
    Mock database adapter for testing without real database calls.

    Returns:
        Mock: Configured mock database instance
    """
    db_mock = Mock()

    # Mock common database methods
    db_mock.get_video = Mock(return_value=None)
    db_mock.create_video = Mock()
    db_mock.list_videos = Mock(return_value=[])
    db_mock.update_video_status = Mock()
    db_mock.delete_scenes_for_video = Mock()
    db_mock.clear_video_for_reprocess = Mock()
    db_mock.get_user_profile = Mock(return_value=None)
    db_mock.search_scenes = Mock(return_value=[])
    db_mock.log_search_query = Mock()

    # Mock Supabase client for health checks
    db_mock.client = Mock()
    db_mock.client.table = Mock(return_value=Mock(
        select=Mock(return_value=Mock(
            limit=Mock(return_value=Mock(
                execute=Mock(return_value=Mock(data=[]))
            ))
        ))
    ))

    return db_mock


# ============================================================================
# Mock External Services
# ============================================================================


@pytest.fixture
def mock_storage():
    """
    Mock Supabase storage adapter.

    Returns:
        Mock: Configured mock storage instance
    """
    storage_mock = Mock()
    storage_mock.upload_file = Mock(return_value="https://example.com/mock-file.jpg")
    storage_mock.download_file = Mock()
    storage_mock.delete_file = Mock()

    # Mock storage client for health checks
    storage_mock.client = Mock()
    storage_mock.client.storage = Mock()
    storage_mock.client.storage.list_buckets = Mock(return_value=[])

    return storage_mock


@pytest.fixture
def mock_queue():
    """
    Mock task queue adapter.

    Returns:
        Mock: Configured mock queue instance
    """
    queue_mock = Mock()
    queue_mock.enqueue_video_processing = Mock()

    # Mock Redis broker for health checks
    queue_mock.broker = Mock()
    queue_mock.broker.client = Mock()
    queue_mock.broker.client.ping = Mock(return_value=True)

    return queue_mock


@pytest.fixture
def mock_openai():
    """
    Mock OpenAI client adapter.

    Returns:
        Mock: Configured mock OpenAI client
    """
    openai_mock = Mock()
    openai_mock.create_embedding = Mock(return_value=[0.1] * 1536)  # Mock embedding
    openai_mock.transcribe_audio = Mock(return_value="Mock transcription")

    return openai_mock


# ============================================================================
# Test Data Factories
# ============================================================================


@pytest.fixture
def video_factory():
    """
    Factory function for creating test Video instances.

    Returns:
        callable: Function that creates Video instances with default or custom values
    """
    def _create_video(
        video_id: UUID | None = None,
        owner_id: UUID | None = None,
        status: VideoStatus = VideoStatus.PENDING,
        filename: str = "test_video.mp4",
        **kwargs
    ) -> Video:
        """
        Create a test Video instance.

        Args:
            video_id: Video UUID (auto-generated if None)
            owner_id: Owner UUID (auto-generated if None)
            status: Video status
            filename: Video filename
            **kwargs: Additional Video attributes

        Returns:
            Video: Test video instance
        """
        defaults = {
            "id": video_id or uuid4(),
            "owner_id": owner_id or uuid4(),
            "storage_path": f"test/{filename}",
            "status": status,
            "filename": filename,
            "duration_s": None,
            "frame_rate": None,
            "width": None,
            "height": None,
            "video_created_at": None,
            "thumbnail_url": None,
            "video_summary": None,
            "has_rich_semantics": False,
            "error_message": None,
            "exif_metadata": None,
            "location_latitude": None,
            "location_longitude": None,
            "location_name": None,
            "camera_make": None,
            "camera_model": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        return Video(**defaults)

    return _create_video


@pytest.fixture
def user_profile_factory():
    """
    Factory function for creating test UserProfile instances.

    Returns:
        callable: Function that creates UserProfile instances
    """
    def _create_user_profile(
        user_id: UUID | None = None,
        full_name: str = "Test User",
        **kwargs
    ) -> UserProfile:
        """
        Create a test UserProfile instance.

        Args:
            user_id: User UUID (auto-generated if None)
            full_name: User's full name
            **kwargs: Additional UserProfile attributes

        Returns:
            UserProfile: Test user profile instance
        """
        defaults = {
            "user_id": user_id or uuid4(),
            "full_name": full_name,
            "industry": None,
            "job_title": None,
            "preferred_language": "ko",
            "marketing_consent": False,
            "marketing_consent_at": None,
            "scene_detector_preferences": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        return UserProfile(**defaults)

    return _create_user_profile


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (may use real services)")
    config.addinivalue_line("markers", "slow: Slow-running tests")
