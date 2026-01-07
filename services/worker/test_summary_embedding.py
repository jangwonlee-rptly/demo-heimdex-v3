"""
Unit tests for summary embedding generation.

This test ensures that when scenes have visual_summary text, the embedding_summary
vector is generated correctly during video processing.

Run with:
    docker-compose run --rm worker pytest test_summary_embedding.py -v
"""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from uuid import uuid4

from src.domain.sidecar_builder import SidecarBuilder, MultiEmbeddingMetadata
from src.domain.scene_detector import Scene


@pytest.fixture
def mock_settings():
    """Mock settings with summary embeddings enabled."""
    settings = Mock()
    settings.multi_embedding_enabled = True
    settings.embedding_summary_enabled = True
    settings.embedding_summary_max_length = 2000
    settings.embedding_transcript_max_length = 4800
    settings.embedding_visual_max_length = 3200
    settings.embedding_visual_include_tags = True
    settings.embedding_version = "v3-multi"
    settings.sidecar_schema_version = "v2"
    settings.embedding_max_retries = 3
    settings.embedding_retry_delay_s = 1.0

    # Visual analysis settings
    settings.visual_analysis_skip_short_scenes = False
    settings.visual_analysis_min_duration_s = 0.0

    # CLIP settings
    settings.clip_enabled = False

    return settings


@pytest.fixture
def mock_storage():
    """Mock storage adapter."""
    storage = Mock()
    return storage


@pytest.fixture
def mock_ffmpeg():
    """Mock FFmpeg adapter."""
    ffmpeg = Mock()
    return ffmpeg


@pytest.fixture
def mock_openai():
    """Mock OpenAI client that returns embeddings."""
    openai = Mock()

    def create_embedding_mock(text):
        # Return a mock embedding (1536 dimensions)
        return [0.1] * 1536

    openai.create_embedding = Mock(side_effect=create_embedding_mock)
    return openai


@pytest.fixture
def sidecar_builder(mock_settings, mock_storage, mock_ffmpeg, mock_openai):
    """Create SidecarBuilder instance with mocks."""
    return SidecarBuilder(
        storage=mock_storage,
        ffmpeg=mock_ffmpeg,
        openai=mock_openai,
        clip_embedder=None,
        settings=mock_settings,
    )


def test_create_multi_channel_embeddings_with_summary(sidecar_builder, mock_openai):
    """Test that summary embeddings are generated when summary text is provided."""
    # Arrange
    transcript_segment = "안녕하세요, 테스트입니다."
    visual_description = "A test scene with a person speaking"
    tags = ["person", "speech"]
    summary = "비디오는 밤의 파리에서 에펠탑이 빛나는 장면으로 시작된다. 금색 조명에 둘러싸인 에펠탑은 도시의 중심에서 화려함을 더한다."

    # Act
    (
        embedding_transcript,
        embedding_visual,
        embedding_summary,
        multi_metadata,
    ) = sidecar_builder._create_multi_channel_embeddings(
        transcript_segment=transcript_segment,
        visual_description=visual_description,
        tags=tags,
        summary=summary,
        scene_index=1,
        language="ko",
    )

    # Assert
    assert embedding_transcript is not None, "Transcript embedding should be generated"
    assert len(embedding_transcript) == 1536, "Transcript embedding should have 1536 dimensions"

    assert embedding_visual is not None, "Visual embedding should be generated"
    assert len(embedding_visual) == 1536, "Visual embedding should have 1536 dimensions"

    # CRITICAL: Summary embedding must be generated
    assert embedding_summary is not None, "Summary embedding MUST be generated when summary text is provided"
    assert len(embedding_summary) == 1536, "Summary embedding should have 1536 dimensions"

    assert multi_metadata is not None, "Multi-embedding metadata should exist"
    assert isinstance(multi_metadata, MultiEmbeddingMetadata)

    assert multi_metadata.transcript is not None, "Transcript metadata should exist"
    assert multi_metadata.visual is not None, "Visual metadata should exist"
    assert multi_metadata.summary is not None, "Summary metadata MUST exist"

    assert multi_metadata.summary.language == "ko", "Summary metadata should track language"
    assert multi_metadata.summary.input_text_length == len(summary), "Summary metadata should track input length"

    # Verify OpenAI was called 3 times (transcript, visual, summary)
    assert mock_openai.create_embedding.call_count == 3, "Should call OpenAI 3 times for 3 channels"


def test_create_multi_channel_embeddings_without_summary(sidecar_builder, mock_openai):
    """Test that no summary embedding is generated when summary is empty/None."""
    # Arrange
    transcript_segment = "Test transcript"
    visual_description = "Test visual"
    tags = []
    summary = None  # No summary

    # Act
    (
        embedding_transcript,
        embedding_visual,
        embedding_summary,
        multi_metadata,
    ) = sidecar_builder._create_multi_channel_embeddings(
        transcript_segment=transcript_segment,
        visual_description=visual_description,
        tags=tags,
        summary=summary,
        scene_index=1,
        language="ko",
    )

    # Assert
    assert embedding_transcript is not None, "Transcript embedding should be generated"
    assert embedding_visual is not None, "Visual embedding should be generated"
    assert embedding_summary is None, "Summary embedding should be None when no summary provided"

    assert multi_metadata.transcript is not None
    assert multi_metadata.visual is not None
    assert multi_metadata.summary is None, "Summary metadata should be None"

    # Verify OpenAI was called 2 times (transcript, visual only)
    assert mock_openai.create_embedding.call_count == 2, "Should call OpenAI 2 times when no summary"


def test_create_multi_channel_embeddings_summary_truncation(sidecar_builder, mock_openai):
    """Test that long summary text is truncated to max_length."""
    # Arrange
    transcript_segment = "Test"
    visual_description = "Test"
    tags = []
    # Create a very long summary (> 2000 chars)
    long_summary = "에펠탑 " * 500  # ~3000 chars

    # Act
    (
        embedding_transcript,
        embedding_visual,
        embedding_summary,
        multi_metadata,
    ) = sidecar_builder._create_multi_channel_embeddings(
        transcript_segment=transcript_segment,
        visual_description=visual_description,
        tags=tags,
        summary=long_summary,
        scene_index=1,
        language="ko",
    )

    # Assert
    assert embedding_summary is not None, "Summary embedding should be generated even with long text"

    # Check that the text passed to OpenAI was truncated
    # Get the last call's argument (summary channel)
    summary_call_args = mock_openai.create_embedding.call_args_list[-1]
    summary_text_used = summary_call_args[0][0]

    assert len(summary_text_used) <= 2000, "Summary text should be truncated to max_length"


def test_summary_embedding_disabled_in_config(mock_settings, mock_storage, mock_ffmpeg, mock_openai):
    """Test that summary embedding is NOT generated when disabled in config."""
    # Arrange
    mock_settings.embedding_summary_enabled = False  # Disable
    builder = SidecarBuilder(
        storage=mock_storage,
        ffmpeg=mock_ffmpeg,
        openai=mock_openai,
        clip_embedder=None,
        settings=mock_settings,
    )

    summary = "Test summary text"

    # Act
    (
        embedding_transcript,
        embedding_visual,
        embedding_summary,
        multi_metadata,
    ) = builder._create_multi_channel_embeddings(
        transcript_segment="Test",
        visual_description="Test",
        tags=[],
        summary=summary,
        scene_index=1,
        language="ko",
    )

    # Assert
    assert embedding_summary is None, "Summary embedding should be None when disabled in config"
    assert multi_metadata.summary is None, "Summary metadata should be None when disabled"


def test_summary_embedding_integration_with_build_sidecar(sidecar_builder, mock_ffmpeg, mock_storage):
    """
    Integration test: Verify that build_sidecar() generates summary embedding
    when visual_summary is provided.

    This is the CRITICAL test that ensures end-to-end functionality.
    """
    # Arrange
    scene = Scene(
        index=0,
        start_frame=0,
        end_frame=100,
        start_s=0.0,
        end_s=4.0,
    )

    video_path = Path("/fake/video.mp4")
    full_transcript = "Full video transcript"
    video_id = uuid4()
    owner_id = uuid4()
    work_dir = Path("/tmp/work")

    # Mock visual analysis to return a summary
    with patch.object(sidecar_builder, '_generate_visual_analysis') as mock_visual:
        visual_summary = "비디오는 밤의 파리에서 에펠탑이 빛나는 장면으로 시작된다."
        mock_visual.return_value = (
            visual_summary,  # visual_summary
            "A detailed description",  # visual_description
            ["eiffel tower", "paris", "night"],  # entities
            ["shining", "glowing"],  # actions
        )

        # Mock frame extraction
        mock_ffmpeg.extract_thumbnail.return_value = "/fake/thumb.jpg"
        mock_storage.upload_thumbnail.return_value = "https://fake/thumb.jpg"

        # Act
        sidecar = sidecar_builder.build_sidecar(
            scene=scene,
            video_path=video_path,
            full_transcript=full_transcript,
            video_id=video_id,
            owner_id=owner_id,
            work_dir=work_dir,
            language="ko",
        )

    # Assert
    assert sidecar.visual_summary == visual_summary, "Visual summary should be set"

    # CRITICAL: embedding_summary must be generated
    assert sidecar.embedding_summary is not None, (
        "CRITICAL: embedding_summary MUST be non-null when visual_summary exists. "
        "This is the root cause of the bug - scenes have visual_summary text but no embedding."
    )
    assert len(sidecar.embedding_summary) == 1536, "Summary embedding should have correct dimensions"

    # Check metadata
    assert sidecar.embedding_version == "v3-multi", "Should use v3-multi embedding version"
    assert sidecar.multi_embedding_metadata is not None
    assert sidecar.multi_embedding_metadata.summary is not None, "Summary metadata must exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
