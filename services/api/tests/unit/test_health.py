"""Unit tests for health check endpoints."""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime


@pytest.mark.unit
class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_basic_health_check(self, client):
        """Test basic liveness health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    @patch("src.routes.health.db")
    @patch("src.routes.health.task_queue")
    @patch("src.routes.health.storage")
    def test_readiness_check_all_healthy(
        self, mock_storage, mock_queue, mock_db, client
    ):
        """Test readiness check when all dependencies are healthy."""
        # Mock successful database check
        mock_db.client.table.return_value.select.return_value.limit.return_value.execute.return_value = Mock(
            data=[]
        )

        # Mock successful Redis check
        mock_queue.broker.client.ping.return_value = True

        # Mock successful storage check
        mock_storage.client.storage.list_buckets.return_value = []

        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "dependencies" in data

        # Check database health
        assert data["dependencies"]["database"]["status"] == "healthy"
        assert "latency_ms" in data["dependencies"]["database"]

        # Check Redis health
        assert data["dependencies"]["redis"]["status"] == "healthy"

        # Check storage health
        assert data["dependencies"]["storage"]["status"] == "healthy"

    @patch("src.routes.health.db")
    @patch("src.routes.health.task_queue")
    @patch("src.routes.health.storage")
    def test_readiness_check_database_unhealthy(
        self, mock_storage, mock_queue, mock_db, client
    ):
        """Test readiness check when database is unhealthy."""
        # Mock database failure
        mock_db.client.table.return_value.select.side_effect = Exception(
            "Connection refused"
        )

        # Mock successful Redis and storage
        mock_queue.broker.client.ping.return_value = True
        mock_storage.client.storage.list_buckets.return_value = []

        response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"

        # Database should be unhealthy
        assert data["dependencies"]["database"]["status"] == "unhealthy"
        assert "Connection refused" in data["dependencies"]["database"]["error"]

        # Other services should still be healthy
        assert data["dependencies"]["redis"]["status"] == "healthy"
        assert data["dependencies"]["storage"]["status"] == "healthy"

    @patch("src.routes.health.db")
    @patch("src.routes.health.task_queue")
    @patch("src.routes.health.storage")
    def test_readiness_check_redis_unhealthy(
        self, mock_storage, mock_queue, mock_db, client
    ):
        """Test readiness check when Redis is unhealthy."""
        # Mock successful database and storage
        mock_db.client.table.return_value.select.return_value.limit.return_value.execute.return_value = Mock(
            data=[]
        )
        mock_storage.client.storage.list_buckets.return_value = []

        # Mock Redis failure
        mock_queue.broker.client.ping.side_effect = Exception("Connection timeout")

        response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"

        # Redis should be unhealthy
        assert data["dependencies"]["redis"]["status"] == "unhealthy"
        assert "Connection timeout" in data["dependencies"]["redis"]["error"]

    @patch("src.routes.health.db")
    @patch("src.routes.health.task_queue")
    @patch("src.routes.health.storage")
    def test_readiness_check_latency_tracking(
        self, mock_storage, mock_queue, mock_db, client
    ):
        """Test that readiness check tracks latency for each dependency."""
        # Mock successful checks
        mock_db.client.table.return_value.select.return_value.limit.return_value.execute.return_value = Mock(
            data=[]
        )
        mock_queue.broker.client.ping.return_value = True
        mock_storage.client.storage.list_buckets.return_value = []

        response = client.get("/health/ready")
        data = response.json()

        # All dependencies should report latency
        for dep_name in ["database", "redis", "storage"]:
            assert "latency_ms" in data["dependencies"][dep_name]
            latency = data["dependencies"][dep_name]["latency_ms"]
            assert isinstance(latency, int)
            assert latency >= 0
