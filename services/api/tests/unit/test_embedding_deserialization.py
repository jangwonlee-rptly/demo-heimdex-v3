"""Tests for embedding deserialization helper.

Tests ensure that the deserialize_embedding() function correctly handles
all possible input formats from Supabase/PostgREST.
"""
import json
import pytest
from src.adapters.database import deserialize_embedding


class TestDeserializeEmbedding:
    """Test deserialize_embedding() helper function."""

    def test_none_returns_none(self):
        """Test that None input returns None."""
        assert deserialize_embedding(None) is None

    def test_list_returns_list(self):
        """Test that list input is returned as-is."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = deserialize_embedding(embedding)
        assert result == embedding
        assert isinstance(result, list)

    def test_json_string_is_parsed(self):
        """Test that JSON string is deserialized to list."""
        embedding_str = "[0.1, 0.2, 0.3, 0.4, 0.5]"
        result = deserialize_embedding(embedding_str)
        assert isinstance(result, list)
        assert len(result) == 5
        assert result == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_512_dimensional_embedding(self):
        """Test realistic 512-dimensional CLIP embedding."""
        # Create a 512-dimensional embedding
        embedding = [float(i) / 512 for i in range(512)]
        embedding_str = json.dumps(embedding)

        # Deserialize
        result = deserialize_embedding(embedding_str)
        assert isinstance(result, list)
        assert len(result) == 512
        assert result == embedding

    def test_negative_values(self):
        """Test embeddings with negative values."""
        embedding_str = "[-0.5, -0.2, 0.0, 0.3, 0.7]"
        result = deserialize_embedding(embedding_str)
        assert result == [-0.5, -0.2, 0.0, 0.3, 0.7]

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Failed to parse embedding JSON"):
            deserialize_embedding("[0.1, 0.2, INVALID]")

    def test_non_list_json_raises_error(self):
        """Test that JSON object (not list) raises ValueError."""
        with pytest.raises(ValueError, match="not a list"):
            deserialize_embedding('{"x": 0.1, "y": 0.2}')

    def test_unexpected_type_raises_error(self):
        """Test that unexpected types raise TypeError."""
        with pytest.raises(TypeError, match="Unexpected embedding type"):
            deserialize_embedding(123)

        with pytest.raises(TypeError, match="Unexpected embedding type"):
            deserialize_embedding({"x": 0.1})

    def test_empty_list(self):
        """Test that empty list is handled."""
        result = deserialize_embedding([])
        assert result == []

    def test_empty_string_json(self):
        """Test that empty JSON list string is handled."""
        result = deserialize_embedding("[]")
        assert result == []

    def test_whitespace_in_json(self):
        """Test JSON with various whitespace formats."""
        # Compact
        result1 = deserialize_embedding("[0.1,0.2,0.3]")
        assert result1 == [0.1, 0.2, 0.3]

        # Spaced
        result2 = deserialize_embedding("[ 0.1 , 0.2 , 0.3 ]")
        assert result2 == [0.1, 0.2, 0.3]

        # Newlines (unlikely but valid JSON)
        result3 = deserialize_embedding("[\n  0.1,\n  0.2,\n  0.3\n]")
        assert result3 == [0.1, 0.2, 0.3]


class TestEmbeddingRoundTrip:
    """Test that embeddings survive round-trip serialization."""

    def test_serialize_then_deserialize(self):
        """Test that we can serialize and deserialize embeddings."""
        original = [float(i) / 100 for i in range(512)]

        # Simulate what PostgREST does: serialize to JSON string
        serialized = json.dumps(original)

        # Deserialize back
        deserialized = deserialize_embedding(serialized)

        assert deserialized == original

    def test_already_deserialized_passthrough(self):
        """Test that already-deserialized embeddings pass through."""
        original = [0.1, 0.2, 0.3]

        # If it's already a list, should return as-is
        result = deserialize_embedding(original)

        assert result is original  # Same object
        assert result == original


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_large_values(self):
        """Test embeddings with large floating point values."""
        embedding_str = "[999999.123, -888888.456, 0.0]"
        result = deserialize_embedding(embedding_str)
        assert result == [999999.123, -888888.456, 0.0]

    def test_scientific_notation(self):
        """Test embeddings with scientific notation."""
        embedding_str = "[1.23e-5, -4.56e3, 7.89e0]"
        result = deserialize_embedding(embedding_str)
        assert len(result) == 3
        assert abs(result[0] - 1.23e-5) < 1e-10
        assert abs(result[1] - (-4.56e3)) < 1e-5

    def test_high_precision_floats(self):
        """Test embeddings with high precision floats."""
        embedding_str = "[0.123456789012345, -0.987654321098765]"
        result = deserialize_embedding(embedding_str)
        assert len(result) == 2
        # JSON parsing may lose some precision
        assert abs(result[0] - 0.123456789012345) < 1e-10

    def test_integer_values(self):
        """Test that integer values in embeddings work."""
        embedding_str = "[0, 1, -1, 100]"
        result = deserialize_embedding(embedding_str)
        # JSON may parse as int or float
        assert result == [0, 1, -1, 100]
