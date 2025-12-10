"""Unit tests for custom exception hierarchy."""

import pytest
from src.exceptions import (
    HeimdexException,
    VideoNotFoundException,
    ForbiddenException,
    ConflictException,
    DatabaseException,
    EmbeddingException,
)


class TestHeimdexException:
    """Test the base HeimdexException class."""

    def test_base_exception_creation(self):
        """Test creating a base HeimdexException."""
        exc = HeimdexException(
            message="Test error",
            error_code="TEST_ERROR",
            status_code=500,
        )

        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.status_code == 500
        assert exc.details == {}

    def test_exception_with_details(self):
        """Test exception with additional details."""
        exc = HeimdexException(
            message="Test error",
            error_code="TEST_ERROR",
            details={"foo": "bar", "count": 42},
        )

        assert exc.details == {"foo": "bar", "count": 42}


class TestResourceNotFoundException:
    """Test resource not found exceptions."""

    def test_video_not_found_exception(self):
        """Test VideoNotFoundException creation."""
        video_id = "12345678-1234-5678-1234-567812345678"
        exc = VideoNotFoundException(video_id)

        assert exc.status_code == 404
        assert exc.error_code == "VIDEO_NOT_FOUND"
        assert exc.video_id == video_id
        assert video_id in exc.message

    def test_video_not_found_with_details(self):
        """Test VideoNotFoundException with additional details."""
        video_id = "12345678-1234-5678-1234-567812345678"
        exc = VideoNotFoundException(video_id, details={"owner": "user123"})

        assert exc.details == {"owner": "user123"}


class TestAuthorizationExceptions:
    """Test authorization exceptions."""

    def test_forbidden_exception(self):
        """Test ForbiddenException creation."""
        exc = ForbiddenException(message="Access denied")

        assert exc.status_code == 403
        assert exc.error_code == "FORBIDDEN"
        assert exc.message == "Access denied"

    def test_forbidden_exception_with_defaults(self):
        """Test ForbiddenException with default message."""
        exc = ForbiddenException()

        assert exc.message == "Access forbidden"


class TestConflictException:
    """Test conflict exceptions."""

    def test_conflict_exception(self):
        """Test ConflictException creation."""
        exc = ConflictException(
            message="Video is being processed",
            resource_type="video",
        )

        assert exc.status_code == 409
        assert exc.error_code == "CONFLICT"
        assert exc.details["resource_type"] == "video"


class TestExternalServiceExceptions:
    """Test external service exceptions."""

    def test_database_exception(self):
        """Test DatabaseException creation."""
        exc = DatabaseException(
            message="Failed to insert row",
            operation="insert",
        )

        assert exc.status_code == 503
        assert exc.error_code == "DATABASE_ERROR"
        assert exc.details["operation"] == "insert"


class TestProcessingExceptions:
    """Test processing exceptions."""

    def test_embedding_exception(self):
        """Test EmbeddingException creation."""
        exc = EmbeddingException(
            message="Text too long",
            text_length=10000,
        )

        assert exc.status_code == 500
        assert exc.error_code == "EMBEDDING_ERROR"
        assert exc.details["text_length"] == 10000
