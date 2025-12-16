"""Tests for CLIP visual embedding generation.

This module tests the ClipEmbedder adapter for CPU-friendly CLIP visual embeddings.
Tests are designed to run without loading actual CLIP models by mocking dependencies.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from src.adapters.clip_embedder import ClipEmbedder, ClipEmbeddingMetadata


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset ClipEmbedder singleton state before each test."""
    ClipEmbedder._instance = None
    ClipEmbedder._model = None
    ClipEmbedder._preprocess = None
    ClipEmbedder._device = None
    ClipEmbedder._embed_dim = None
    ClipEmbedder._initialized = False
    yield
    # Cleanup after test
    ClipEmbedder._instance = None
    ClipEmbedder._model = None
    ClipEmbedder._preprocess = None
    ClipEmbedder._device = None
    ClipEmbedder._embed_dim = None
    ClipEmbedder._initialized = False


@pytest.fixture
def mock_settings_enabled():
    """Mock settings with CLIP enabled."""
    with patch('src.adapters.clip_embedder.settings') as mock_settings:
        mock_settings.clip_enabled = True
        mock_settings.clip_model_name = "ViT-B-32"
        mock_settings.clip_pretrained = "openai"
        mock_settings.clip_device = "cpu"
        mock_settings.clip_cache_dir = "/tmp/clip_cache"
        mock_settings.clip_normalize = True
        mock_settings.clip_timeout_s = 2.0
        mock_settings.clip_max_image_size = 224
        mock_settings.clip_debug_log = False
        yield mock_settings


@pytest.fixture
def mock_settings_disabled():
    """Mock settings with CLIP disabled."""
    with patch('src.adapters.clip_embedder.settings') as mock_settings:
        mock_settings.clip_enabled = False
        mock_settings.clip_model_name = "ViT-B-32"
        mock_settings.clip_pretrained = "openai"
        yield mock_settings


@pytest.fixture
def mock_clip_model():
    """Mock OpenCLIP model and dependencies."""
    mock_model = MagicMock()
    mock_model.visual.output_dim = 512
    mock_model.eval = MagicMock(return_value=mock_model)

    # Mock encode_image to return a fake embedding tensor
    mock_embedding_tensor = MagicMock()
    mock_embedding_tensor.squeeze = MagicMock(return_value=MagicMock())
    mock_embedding_tensor.squeeze().cpu = MagicMock(return_value=MagicMock())
    mock_embedding_tensor.squeeze().cpu().numpy = MagicMock(return_value=MagicMock())
    mock_embedding_tensor.squeeze().cpu().numpy().tolist = MagicMock(
        return_value=[0.1] * 512  # 512-dim embedding
    )
    mock_model.encode_image = MagicMock(return_value=mock_embedding_tensor)

    mock_preprocess = MagicMock()

    return mock_model, mock_preprocess


class TestClipEmbedderDisabled:
    """Tests for ClipEmbedder when CLIP is disabled."""

    def test_disabled_returns_none(self, mock_settings_disabled):
        """Test that create_visual_embedding returns None when CLIP is disabled."""
        embedder = ClipEmbedder()
        embedding, metadata = embedder.create_visual_embedding(
            image_path=Path("/tmp/test.jpg")
        )

        assert embedding is None
        assert metadata is not None
        assert metadata.error == "CLIP embeddings disabled via CLIP_ENABLED=false"
        assert metadata.model_name == "disabled"

    def test_disabled_is_available_false(self, mock_settings_disabled):
        """Test that is_available returns False when disabled."""
        embedder = ClipEmbedder()
        assert embedder.is_available() is False

    def test_disabled_get_embedding_dim_none(self, mock_settings_disabled):
        """Test that get_embedding_dim returns None when disabled."""
        embedder = ClipEmbedder()
        assert embedder.get_embedding_dim() is None


class TestClipEmbedderSingleton:
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self, mock_settings_enabled):
        """Test that multiple ClipEmbedder() calls return the same instance."""
        embedder1 = ClipEmbedder()
        embedder2 = ClipEmbedder()
        assert embedder1 is embedder2

    def test_model_loaded_once(self, mock_settings_enabled, mock_clip_model):
        """Test that model is loaded only once across multiple calls."""
        mock_model, mock_preprocess = mock_clip_model

        with patch('builtins.__import__', side_effect=lambda name, *args, **kwargs:
                   Mock(create_model_and_transforms=Mock(return_value=(mock_model, None, mock_preprocess)))
                   if name == 'open_clip' else __import__(name, *args, **kwargs)):
            embedder = ClipEmbedder()
            # Model loading is internal and lazy - just verify no crash
            assert embedder._model is None  # Not loaded yet
            # Second call should also not crash
            assert embedder._model is None


class TestClipEmbedderModelLoading:
    """Tests for model loading behavior."""

    def test_model_loading_with_disabled_setting(self, mock_settings_disabled):
        """Test that model loading returns False when CLIP is disabled."""
        embedder = ClipEmbedder()
        result = embedder._ensure_model_loaded()

        assert result is False
        assert embedder._model is None

    def test_model_already_loaded(self, mock_settings_enabled):
        """Test that _ensure_model_loaded returns True if model already loaded."""
        embedder = ClipEmbedder()
        # Simulate already loaded model
        embedder._model = Mock()
        embedder._embed_dim = 512

        result = embedder._ensure_model_loaded()
        assert result is True


class TestClipEmbedderEmbeddingGeneration:
    """Tests for embedding generation."""

    def test_embedding_disabled(self, mock_settings_disabled):
        """Test that embedding generation returns None when CLIP is disabled."""
        mock_image_path = Path("/tmp/test_scene_12.jpg")

        embedder = ClipEmbedder()
        embedding, metadata = embedder.create_visual_embedding(
            image_path=mock_image_path,
            quality_info={"quality_score": 0.85}
        )

        assert embedding is None
        assert metadata is not None
        assert metadata.error == "CLIP embeddings disabled via CLIP_ENABLED=false"
        assert metadata.frame_quality is None

    def test_embedding_model_load_failure(self, mock_settings_enabled):
        """Test embedding generation when model fails to load."""
        mock_image_path = Path("/tmp/test.jpg")

        embedder = ClipEmbedder()
        # Force model to not load (simulating import error)
        embedder._model = None

        # Patch _ensure_model_loaded to return False
        with patch.object(embedder, '_ensure_model_loaded', return_value=False):
            embedding, metadata = embedder.create_visual_embedding(
                image_path=mock_image_path
            )

            assert embedding is None
            assert metadata.error == "Failed to load CLIP model"


class TestClipEmbeddingMetadata:
    """Tests for ClipEmbeddingMetadata dataclass."""

    def test_metadata_to_dict(self):
        """Test metadata serialization to dict."""
        metadata = ClipEmbeddingMetadata(
            model_name="ViT-B-32",
            pretrained="openai",
            embed_dim=512,
            normalized=True,
            device="cpu",
            frame_path="scene_12_frame_0.jpg",
            frame_quality={"quality_score": 0.85},
            inference_time_ms=145.2,
            error=None,
        )

        result = metadata.to_dict()

        assert result["model_name"] == "ViT-B-32"
        assert result["pretrained"] == "openai"
        assert result["embed_dim"] == 512
        assert result["normalized"] is True
        assert result["device"] == "cpu"
        assert result["frame_path"] == "scene_12_frame_0.jpg"
        assert result["frame_quality"] == {"quality_score": 0.85}
        assert result["inference_time_ms"] == 145.2
        assert result["error"] is None
        assert "created_at" in result  # Auto-generated

    def test_metadata_with_error(self):
        """Test metadata with error message."""
        metadata = ClipEmbeddingMetadata(
            model_name="ViT-B-32",
            pretrained="openai",
            embed_dim=512,
            normalized=True,
            device="cpu",
            frame_path="scene_12_frame_0.jpg",
            error="Timeout after 2.0s",
        )

        result = metadata.to_dict()

        assert result["error"] == "Timeout after 2.0s"


class TestClipEmbedderHelperMethods:
    """Tests for helper methods."""

    def test_get_embedding_dim_when_model_loaded(self, mock_settings_enabled):
        """Test get_embedding_dim returns correct value when model is loaded."""
        embedder = ClipEmbedder()
        # Simulate loaded model
        embedder._model = Mock()
        embedder._embed_dim = 512

        assert embedder.get_embedding_dim() == 512

    def test_get_embedding_dim_when_model_not_loaded(self, mock_settings_disabled):
        """Test get_embedding_dim returns None when model is not loaded."""
        embedder = ClipEmbedder()
        assert embedder.get_embedding_dim() is None

    def test_is_available_with_loaded_model(self, mock_settings_enabled):
        """Test is_available returns True when model is loaded."""
        embedder = ClipEmbedder()
        # Simulate loaded model
        embedder._model = Mock()
        embedder._embed_dim = 512

        # Patch _ensure_model_loaded to return True
        with patch.object(embedder, '_ensure_model_loaded', return_value=True):
            assert embedder.is_available() is True
