"""Integration tests for video endpoints.

These tests demonstrate how to test the video API endpoints.
They use mocked dependencies to avoid requiring real database/storage.
"""

import pytest
from unittest.mock import patch, Mock
from uuid import uuid4
from src.domain.models import VideoStatus


@pytest.mark.integration
class TestVideoReprocessEndpoint:
    """Test the video reprocess endpoint."""

    @patch("src.routes.videos.db")
    @patch("src.routes.videos.task_queue")
    def test_reprocess_video_success(
        self, mock_queue, mock_db, client, video_factory, mock_user_id, auth_headers
    ):
        """Test successful video reprocessing."""
        # Create a test video
        video_id = uuid4()
        test_video = video_factory(
            video_id=video_id,
            owner_id=mock_user_id,
            status=VideoStatus.READY,
        )

        # Mock database responses
        mock_db.get_video.return_value = test_video
        mock_db.delete_scenes_for_video.return_value = None
        mock_db.clear_video_for_reprocess.return_value = None

        # Mock queue
        mock_queue.enqueue_video_processing.return_value = None

        # Make request
        response = client.post(
            f"/v1/videos/{video_id}/reprocess",
            json={"transcript_language": "ko"},
            headers=auth_headers,
        )

        # Assertions
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["transcript_language"] == "ko"

        # Verify database calls
        mock_db.get_video.assert_called_once_with(video_id)
        mock_db.delete_scenes_for_video.assert_called_once_with(video_id)
        mock_db.clear_video_for_reprocess.assert_called_once()

        # Verify queue call
        mock_queue.enqueue_video_processing.assert_called_once_with(video_id)

    @patch("src.routes.videos.db")
    def test_reprocess_video_not_found(
        self, mock_db, client, mock_user_id, auth_headers
    ):
        """Test reprocessing a non-existent video returns 404."""
        video_id = uuid4()

        # Mock video not found
        mock_db.get_video.return_value = None

        # Make request
        response = client.post(
            f"/v1/videos/{video_id}/reprocess",
            json={"transcript_language": "en"},
            headers=auth_headers,
        )

        # Should return 404 with our custom exception format
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "VIDEO_NOT_FOUND"
        assert str(video_id) in data["message"]

    @patch("src.routes.videos.db")
    def test_reprocess_video_forbidden(
        self, mock_db, client, video_factory, mock_user_id, auth_headers
    ):
        """Test reprocessing a video owned by another user returns 403."""
        video_id = uuid4()
        other_user_id = uuid4()  # Different user

        test_video = video_factory(
            video_id=video_id,
            owner_id=other_user_id,  # Owned by different user
            status=VideoStatus.READY,
        )

        mock_db.get_video.return_value = test_video

        # Make request
        response = client.post(
            f"/v1/videos/{video_id}/reprocess",
            json={},
            headers=auth_headers,
        )

        # Should return 403 forbidden
        assert response.status_code == 403
        data = response.json()
        assert data["error_code"] == "FORBIDDEN"

    @patch("src.routes.videos.db")
    def test_reprocess_video_conflict_when_processing(
        self, mock_db, client, video_factory, mock_user_id, auth_headers
    ):
        """Test reprocessing a video that's already processing returns 409."""
        video_id = uuid4()

        test_video = video_factory(
            video_id=video_id,
            owner_id=mock_user_id,
            status=VideoStatus.PROCESSING,  # Already processing
        )

        mock_db.get_video.return_value = test_video

        # Make request
        response = client.post(
            f"/v1/videos/{video_id}/reprocess",
            json={},
            headers=auth_headers,
        )

        # Should return 409 conflict
        assert response.status_code == 409
        data = response.json()
        assert data["error_code"] == "CONFLICT"
        assert "currently being processed" in data["message"]

    @patch("src.routes.videos.db")
    @patch("src.routes.videos.task_queue")
    def test_reprocess_video_with_auto_detect_language(
        self, mock_queue, mock_db, client, video_factory, mock_user_id, auth_headers
    ):
        """Test reprocessing without language override uses auto-detect."""
        video_id = uuid4()

        test_video = video_factory(
            video_id=video_id,
            owner_id=mock_user_id,
            status=VideoStatus.READY,
        )

        mock_db.get_video.return_value = test_video
        mock_queue.enqueue_video_processing.return_value = None

        # Make request without transcript_language
        response = client.post(
            f"/v1/videos/{video_id}/reprocess",
            json={},  # No language specified
            headers=auth_headers,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["transcript_language"] == "auto-detect"

        # Verify clear_video_for_reprocess was called with None language
        call_args = mock_db.clear_video_for_reprocess.call_args
        assert call_args[1]["transcript_language"] is None
