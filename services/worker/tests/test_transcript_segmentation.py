"""Tests for timestamp-aligned transcript segmentation."""
import pytest
from src.domain.sidecar_builder import SidecarBuilder


class TestExtractTranscriptSegmentFromSegments:
    """Tests for _extract_transcript_segment_from_segments function."""

    def test_exact_overlap(self):
        """Test segment extraction with exact time overlap."""
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Hello world"},
            {"start": 2.0, "end": 4.0, "text": "this is a test"},
            {"start": 4.0, "end": 6.0, "text": "of the system"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=2.0,
            scene_end_s=4.0,
            video_duration_s=6.0,
            min_chars=0,  # Disable context expansion for this test
        )

        assert result == "this is a test"

    def test_partial_overlap_start(self):
        """Test segment extraction when scene starts mid-segment."""
        segments = [
            {"start": 0.0, "end": 3.0, "text": "Hello world"},
            {"start": 3.0, "end": 6.0, "text": "this is a test"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=1.5,  # Starts during first segment
            scene_end_s=3.5,
            video_duration_s=6.0,
            min_chars=0,  # Disable context expansion
        )

        # Should include both segments that overlap
        assert "Hello world" in result
        assert "this is a test" in result

    def test_partial_overlap_end(self):
        """Test segment extraction when scene ends mid-segment."""
        segments = [
            {"start": 0.0, "end": 3.0, "text": "First segment"},
            {"start": 3.0, "end": 6.0, "text": "Second segment"},
            {"start": 6.0, "end": 9.0, "text": "Third segment"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=2.5,
            scene_end_s=6.5,  # Ends during third segment
            video_duration_s=9.0,
            min_chars=0,  # Disable context expansion
        )

        # Should include all overlapping segments
        assert "First segment" in result
        assert "Second segment" in result
        assert "Third segment" in result

    def test_no_overlap_returns_empty(self):
        """Test that no overlap returns empty string."""
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Hello world"},
            {"start": 5.0, "end": 7.0, "text": "Goodbye world"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=2.5,
            scene_end_s=4.5,  # Gap with no segments
            video_duration_s=10.0,
            min_chars=0,  # Disable context expansion
        )

        assert result == ""

    def test_context_expansion_short_segment(self):
        """Test context expansion when initial segment is too short."""
        segments = [
            {"start": 0.0, "end": 1.0, "text": "Short."},  # Only 6 chars
            {"start": 2.0, "end": 5.0, "text": "This is additional context that should be included when expanding."},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=0.0,
            scene_end_s=1.0,
            video_duration_s=10.0,
            min_chars=200,  # Require at least 200 chars
            context_pad_s=3.0,  # Expand by 3 seconds
        )

        # Should expand to include the second segment
        assert "Short." in result
        assert "additional context" in result

    def test_context_expansion_clamped_at_zero(self):
        """Test that context expansion doesn't go below 0."""
        segments = [
            {"start": 0.0, "end": 1.0, "text": "Start"},
            {"start": 1.0, "end": 3.0, "text": "Middle part here"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=0.5,
            scene_end_s=1.5,
            video_duration_s=10.0,
            min_chars=200,
            context_pad_s=5.0,  # Would expand to -4.5, should clamp to 0
        )

        # Should include segments from 0.0 (not negative)
        assert "Start" in result
        assert "Middle" in result

    def test_context_expansion_clamped_at_duration(self):
        """Test that context expansion doesn't exceed video duration."""
        segments = [
            {"start": 7.0, "end": 8.0, "text": "Near the end"},
            {"start": 8.0, "end": 10.0, "text": "The very end of video"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=7.5,
            scene_end_s=8.5,
            video_duration_s=10.0,
            min_chars=200,
            context_pad_s=5.0,  # Would expand to 13.5, should clamp to 10.0
        )

        # Should include segments up to 10.0 (not beyond)
        assert "Near the end" in result
        assert "very end" in result

    def test_empty_segments_list(self):
        """Test handling of empty segments list."""
        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=[],
            scene_start_s=0.0,
            scene_end_s=5.0,
            video_duration_s=10.0,
            min_chars=0,
        )

        assert result == ""

    def test_segments_out_of_order(self):
        """Test that segments are sorted by start time."""
        segments = [
            {"start": 4.0, "end": 6.0, "text": "Third"},
            {"start": 0.0, "end": 2.0, "text": "First"},
            {"start": 2.0, "end": 4.0, "text": "Second"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=0.0,
            scene_end_s=6.0,
            video_duration_s=10.0,
            min_chars=0,
        )

        # Should be in chronological order regardless of input order
        assert result == "First Second Third"

    def test_whitespace_normalization(self):
        """Test that whitespace is properly normalized."""
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Hello   world  "},
            {"start": 2.0, "end": 4.0, "text": "  with   extra   spaces"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=0.0,
            scene_end_s=4.0,
            video_duration_s=10.0,
            min_chars=0,
        )

        # Should have single spaces between words
        assert "  " not in result  # No double spaces
        assert result == "Hello world with extra spaces"

    def test_multiple_segments_within_scene(self):
        """Test extraction with multiple segments fully within scene."""
        segments = [
            {"start": 0.0, "end": 1.0, "text": "Alpha"},
            {"start": 1.0, "end": 2.0, "text": "Bravo"},
            {"start": 2.0, "end": 3.0, "text": "Charlie"},
            {"start": 3.0, "end": 4.0, "text": "Delta"},
            {"start": 4.0, "end": 5.0, "text": "Echo"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=1.5,
            scene_end_s=3.5,
            video_duration_s=10.0,
            min_chars=0,
        )

        # Should include Bravo (1-2), Charlie (2-3), and Delta (3-4)
        assert "Bravo" in result
        assert "Charlie" in result
        assert "Delta" in result
        assert "Alpha" not in result  # Before scene
        assert "Echo" not in result   # After scene

    def test_single_segment_spanning_scene(self):
        """Test when a single long segment spans the entire scene."""
        segments = [
            {"start": 0.0, "end": 10.0, "text": "This is a very long segment that spans the entire scene and then some."},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=2.0,
            scene_end_s=5.0,
            video_duration_s=10.0,
            min_chars=0,
        )

        # Should include the segment since it overlaps
        assert result == "This is a very long segment that spans the entire scene and then some."

    def test_segment_exactly_at_boundaries(self):
        """Test segments that start/end exactly at scene boundaries."""
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Before"},
            {"start": 2.0, "end": 5.0, "text": "During"},  # Exactly at boundaries
            {"start": 5.0, "end": 8.0, "text": "After"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=2.0,
            scene_end_s=5.0,
            video_duration_s=10.0,
            min_chars=0,
        )

        # Should include the segment that exactly matches
        assert result == "During"

    def test_korean_text(self):
        """Test with Korean/CJK text to ensure proper handling."""
        segments = [
            {"start": 0.0, "end": 2.0, "text": "안녕하세요"},
            {"start": 2.0, "end": 4.0, "text": "이것은 테스트입니다"},
            {"start": 4.0, "end": 6.0, "text": "감사합니다"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=1.5,
            scene_end_s=4.5,
            video_duration_s=10.0,
            min_chars=0,
        )

        assert "안녕하세요" in result
        assert "이것은 테스트입니다" in result
        assert "감사합니다" in result

    def test_mixed_language_text(self):
        """Test with mixed English and Korean text."""
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Hello 안녕"},
            {"start": 2.0, "end": 4.0, "text": "World 세계"},
        ]

        result = SidecarBuilder._extract_transcript_segment_from_segments(
            segments=segments,
            scene_start_s=0.0,
            scene_end_s=4.0,
            video_duration_s=10.0,
            min_chars=0,
        )

        assert "Hello 안녕" in result
        assert "World 세계" in result
