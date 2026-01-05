"""Tests for person-related database mappers.

Tests ensure that person and photo mappers correctly deserialize embeddings
in all scenarios (string, list, None).
"""
import json
import pytest
from datetime import datetime
from uuid import uuid4
from src.adapters.database import Database


class TestPersonMappers:
    """Test person and photo row mapping with embedding deserialization."""

    @pytest.fixture
    def db(self):
        """Create a database instance for testing (mocked Supabase client)."""
        # We don't need a real connection for mapper tests
        # Just create the Database instance with dummy credentials
        return Database(
            supabase_url="http://localhost:54321",
            supabase_key="dummy_key"
        )

    def test_map_person_row_with_string_embedding(self, db):
        """Test _map_person_row with embedding as JSON string."""
        person_id = uuid4()
        owner_id = uuid4()
        embedding = [float(i) / 512 for i in range(512)]
        embedding_str = json.dumps(embedding)

        row = {
            "id": str(person_id),
            "owner_id": str(owner_id),
            "display_name": "Test Person",
            "query_embedding": embedding_str,  # JSON string (realistic)
            "status": "active",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

        person = db._map_person_row(row)

        assert person.id == person_id
        assert person.owner_id == owner_id
        assert person.display_name == "Test Person"
        assert isinstance(person.query_embedding, list)
        assert len(person.query_embedding) == 512
        assert person.query_embedding == embedding

    def test_map_person_row_with_list_embedding(self, db):
        """Test _map_person_row with embedding already as list."""
        person_id = uuid4()
        owner_id = uuid4()
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        row = {
            "id": str(person_id),
            "owner_id": str(owner_id),
            "display_name": "Test Person",
            "query_embedding": embedding,  # Already list (from mock)
            "status": "active",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

        person = db._map_person_row(row)

        assert person.id == person_id
        assert isinstance(person.query_embedding, list)
        assert person.query_embedding == embedding

    def test_map_person_row_with_none_embedding(self, db):
        """Test _map_person_row with no embedding (None)."""
        person_id = uuid4()
        owner_id = uuid4()

        row = {
            "id": str(person_id),
            "owner_id": str(owner_id),
            "display_name": "Test Person",
            "query_embedding": None,  # No embedding yet
            "status": "active",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

        person = db._map_person_row(row)

        assert person.id == person_id
        assert person.query_embedding is None

    def test_map_person_row_missing_embedding_key(self, db):
        """Test _map_person_row when embedding key is missing."""
        person_id = uuid4()
        owner_id = uuid4()

        row = {
            "id": str(person_id),
            "owner_id": str(owner_id),
            "display_name": "Test Person",
            # query_embedding key not present
            "status": "active",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

        person = db._map_person_row(row)

        assert person.query_embedding is None

    def test_map_person_photo_row_with_string_embedding(self, db):
        """Test _map_person_photo_row with embedding as JSON string."""
        photo_id = uuid4()
        person_id = uuid4()
        owner_id = uuid4()
        embedding = [float(i) / 512 for i in range(512)]
        embedding_str = json.dumps(embedding)

        row = {
            "id": str(photo_id),
            "owner_id": str(owner_id),
            "person_id": str(person_id),
            "storage_path": "person_photos/test.jpg",
            "state": "READY",
            "embedding": embedding_str,  # JSON string
            "quality_score": 0.95,
            "face_bbox": {"x": 100, "y": 50, "w": 200, "h": 200},
            "error_message": None,
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

        photo = db._map_person_photo_row(row)

        assert photo.id == photo_id
        assert isinstance(photo.embedding, list)
        assert len(photo.embedding) == 512
        assert photo.embedding == embedding

    def test_map_person_photo_row_with_list_embedding(self, db):
        """Test _map_person_photo_row with embedding already as list."""
        photo_id = uuid4()
        person_id = uuid4()
        owner_id = uuid4()
        embedding = [0.1, 0.2, 0.3]

        row = {
            "id": str(photo_id),
            "owner_id": str(owner_id),
            "person_id": str(person_id),
            "storage_path": "person_photos/test.jpg",
            "state": "READY",
            "embedding": embedding,  # Already list
            "quality_score": 0.85,
            "face_bbox": None,
            "error_message": None,
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

        photo = db._map_person_photo_row(row)

        assert isinstance(photo.embedding, list)
        assert photo.embedding == embedding

    def test_map_person_photo_row_with_none_embedding(self, db):
        """Test _map_person_photo_row with no embedding (UPLOADED state)."""
        photo_id = uuid4()
        person_id = uuid4()
        owner_id = uuid4()

        row = {
            "id": str(photo_id),
            "owner_id": str(owner_id),
            "person_id": str(person_id),
            "storage_path": "person_photos/test.jpg",
            "state": "UPLOADED",
            "embedding": None,  # Not processed yet
            "quality_score": None,
            "face_bbox": None,
            "error_message": None,
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

        photo = db._map_person_photo_row(row)

        assert photo.embedding is None
        assert photo.state == "UPLOADED"


class TestEmbeddingValidation:
    """Test embedding validation in mappers."""

    @pytest.fixture
    def db(self):
        """Create a database instance for testing."""
        return Database(
            supabase_url="http://localhost:54321",
            supabase_key="dummy_key"
        )

    def test_person_invalid_dimension_logs_warning(self, db, caplog):
        """Test that invalid embedding dimension logs warning."""
        person_id = uuid4()
        owner_id = uuid4()
        # Invalid: only 256 dimensions instead of 512
        embedding = [float(i) / 256 for i in range(256)]
        embedding_str = json.dumps(embedding)

        row = {
            "id": str(person_id),
            "owner_id": str(owner_id),
            "display_name": "Test Person",
            "query_embedding": embedding_str,
            "status": "active",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

        person = db._map_person_row(row)

        # Should still create the person but log warning
        assert person.query_embedding is not None
        assert len(person.query_embedding) == 256
        assert "Invalid query_embedding dimension" in caplog.text
        assert "expected 512, got 256" in caplog.text

    def test_photo_invalid_dimension_logs_warning(self, db, caplog):
        """Test that invalid photo embedding dimension logs warning."""
        photo_id = uuid4()
        person_id = uuid4()
        owner_id = uuid4()
        # Invalid: only 128 dimensions
        embedding = [0.1] * 128
        embedding_str = json.dumps(embedding)

        row = {
            "id": str(photo_id),
            "owner_id": str(owner_id),
            "person_id": str(person_id),
            "storage_path": "person_photos/test.jpg",
            "state": "READY",
            "embedding": embedding_str,
            "quality_score": 0.9,
            "face_bbox": None,
            "error_message": None,
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

        photo = db._map_person_photo_row(row)

        assert photo.embedding is not None
        assert len(photo.embedding) == 128
        assert "Invalid embedding dimension" in caplog.text
        assert "expected 512, got 128" in caplog.text
