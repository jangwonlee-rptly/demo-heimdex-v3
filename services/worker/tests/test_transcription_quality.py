"""Tests for transcription quality heuristics."""
import pytest
from unittest.mock import patch, MagicMock

from src.adapters.openai_client import (
    TranscriptionResult,
    is_speech_character,
    calculate_speech_char_ratio,
    is_mostly_music_notation,
    contains_banned_phrases,
    OpenAIClient,
)


class TestIsSpeechCharacter:
    """Tests for is_speech_character function."""

    def test_ascii_letters(self):
        assert is_speech_character("a") is True
        assert is_speech_character("Z") is True

    def test_digits(self):
        assert is_speech_character("5") is True
        assert is_speech_character("0") is True

    def test_hangul(self):
        assert is_speech_character("한") is True
        assert is_speech_character("글") is True

    def test_cjk(self):
        assert is_speech_character("中") is True
        assert is_speech_character("日") is True

    def test_music_symbols(self):
        assert is_speech_character("♪") is False
        assert is_speech_character("♫") is False

    def test_punctuation(self):
        assert is_speech_character(".") is False
        assert is_speech_character(",") is False
        assert is_speech_character("!") is False


class TestCalculateSpeechCharRatio:
    """Tests for calculate_speech_char_ratio function."""

    def test_empty_string(self):
        assert calculate_speech_char_ratio("") == 0.0

    def test_whitespace_only(self):
        assert calculate_speech_char_ratio("   ") == 0.0

    def test_pure_speech(self):
        ratio = calculate_speech_char_ratio("Hello World")
        assert ratio == 1.0  # All alphanumeric

    def test_pure_music(self):
        ratio = calculate_speech_char_ratio("♪♪♪♪♪")
        assert ratio == 0.0

    def test_mixed_content(self):
        # "Hello ♪♪♪" -> 5 letters, 3 music symbols (no whitespace counted)
        ratio = calculate_speech_char_ratio("Hello ♪♪♪")
        assert 0.5 < ratio < 0.7  # 5/8 = 0.625

    def test_korean_text(self):
        ratio = calculate_speech_char_ratio("안녕하세요")
        assert ratio == 1.0

    def test_korean_with_music(self):
        # "안녕 ♪" -> 2 korean chars, 1 music symbol
        ratio = calculate_speech_char_ratio("안녕 ♪")
        assert ratio == pytest.approx(2 / 3, rel=0.01)


class TestIsMostlyMusicNotation:
    """Tests for is_mostly_music_notation function."""

    MUSIC_MARKERS = ["♪", "♫", "[Music]", "[music]"]

    def test_pure_music_notes(self):
        assert is_mostly_music_notation("♪♪♪♪♪", self.MUSIC_MARKERS) is True

    def test_music_tags(self):
        assert is_mostly_music_notation("[Music] [Music]", self.MUSIC_MARKERS) is True

    def test_mixed_music_tags(self):
        assert is_mostly_music_notation("[Music] ♪♪♪", self.MUSIC_MARKERS) is True

    def test_pure_speech(self):
        assert (
            is_mostly_music_notation(
                "This is a normal transcription with speech",
                self.MUSIC_MARKERS,
            )
            is False
        )

    def test_speech_with_some_music(self):
        # Mostly speech with a few music notes
        assert (
            is_mostly_music_notation(
                "The speaker says hello and then ♪ some music plays",
                self.MUSIC_MARKERS,
            )
            is False
        )

    def test_empty_string(self):
        assert is_mostly_music_notation("", self.MUSIC_MARKERS) is False

    def test_korean_with_music(self):
        # Korean text with music - should detect as speech
        assert (
            is_mostly_music_notation(
                "안녕하세요 오늘 좋은 하루 되세요 ♪",
                self.MUSIC_MARKERS,
            )
            is False
        )

    def test_mostly_music_korean(self):
        # Mostly music with minimal text
        assert is_mostly_music_notation("♪♪♪ 아 ♪♪♪", self.MUSIC_MARKERS) is True


class TestContainsBannedPhrases:
    """Tests for contains_banned_phrases function."""

    def test_empty_banned_list(self):
        assert contains_banned_phrases("Any text here", []) is False

    def test_empty_text(self):
        assert contains_banned_phrases("", ["banned"]) is False

    def test_no_banned_phrase(self):
        assert (
            contains_banned_phrases("Normal speech content", ["subscribe", "like"])
            is False
        )

    def test_single_banned_occurrence(self):
        # Single occurrence that doesn't dominate
        assert (
            contains_banned_phrases(
                "This is a long transcription with subscribe mentioned once",
                ["subscribe"],
            )
            is False
        )

    def test_dominant_banned_phrase(self):
        # Banned phrase covers >50% of text
        assert (
            contains_banned_phrases(
                "subscribe subscribe subscribe",
                ["subscribe"],
            )
            is True
        )

    def test_case_insensitive(self):
        assert (
            contains_banned_phrases(
                "SUBSCRIBE SUBSCRIBE SUBSCRIBE",
                ["subscribe"],
            )
            is True
        )


class TestTranscriptionResult:
    """Tests for TranscriptionResult dataclass."""

    def test_creation(self):
        result = TranscriptionResult(
            text="Hello world",
            has_speech=True,
            reason="ok",
        )
        assert result.text == "Hello world"
        assert result.has_speech is True
        assert result.reason == "ok"

    def test_no_speech_result(self):
        result = TranscriptionResult(
            text="",
            has_speech=False,
            reason="music_only",
        )
        assert result.text == ""
        assert result.has_speech is False
        assert result.reason == "music_only"


class TestOpenAIClientAssessQuality:
    """Tests for OpenAIClient._assess_transcription_quality method."""

    @pytest.fixture
    def client(self):
        """Create a mock OpenAI client."""
        with patch("src.adapters.openai_client.OpenAI"):
            # Mock settings
            with patch("src.adapters.openai_client.settings") as mock_settings:
                mock_settings.transcription_min_chars_for_speech = 40
                mock_settings.transcription_min_speech_char_ratio = 0.3
                mock_settings.transcription_max_no_speech_prob = 0.8
                mock_settings.transcription_min_speech_segments_ratio = 0.3
                mock_settings.transcription_music_markers = [
                    "♪",
                    "♫",
                    "[Music]",
                    "[music]",
                ]
                mock_settings.transcription_banned_phrases = []
                mock_settings.openai_api_key = "test-key"
                client = OpenAIClient()
                yield client

    def test_short_music_only(self, client):
        """Pure music notes should be rejected."""
        result = client._assess_transcription_quality("♪♪♪♪♪", [])
        assert result.has_speech is False
        assert result.reason == "music_only"

    def test_valid_speech(self, client):
        """Normal speech should be accepted."""
        text = "This is a normal transcription with meaningful speech content."
        result = client._assess_transcription_quality(text, [])
        assert result.has_speech is True
        assert result.reason == "ok"
        assert result.text == text

    def test_too_short_low_ratio(self, client):
        """Very short text with low speech ratio should be rejected."""
        result = client._assess_transcription_quality("... ...", [])
        assert result.has_speech is False
        assert result.reason == "too_short"

    def test_music_tags(self, client):
        """Music tags should be rejected."""
        result = client._assess_transcription_quality("[Music] [Music] [Music]", [])
        assert result.has_speech is False
        assert result.reason == "music_only"

    def test_high_no_speech_prob_segments(self, client):
        """High no_speech_prob segments should be rejected."""
        segments = [
            {"no_speech_prob": 0.9},
            {"no_speech_prob": 0.95},
            {"no_speech_prob": 0.85},
            {"no_speech_prob": 0.92},
        ]
        text = "This is some text that whisper transcribed but segments say no speech."
        result = client._assess_transcription_quality(text, segments)
        assert result.has_speech is False
        assert result.reason == "high_no_speech_prob"

    def test_low_no_speech_prob_segments(self, client):
        """Low no_speech_prob segments should be accepted."""
        segments = [
            {"no_speech_prob": 0.1},
            {"no_speech_prob": 0.15},
            {"no_speech_prob": 0.2},
            {"no_speech_prob": 0.05},
        ]
        text = "This is valid speech content that was properly transcribed."
        result = client._assess_transcription_quality(text, segments)
        assert result.has_speech is True
        assert result.reason == "ok"

    def test_korean_speech(self, client):
        """Korean speech should be accepted."""
        text = "안녕하세요 오늘 비디오에서는 제가 좋아하는 음식에 대해 이야기해보려고 합니다"
        result = client._assess_transcription_quality(text, [])
        assert result.has_speech is True
        assert result.reason == "ok"

    def test_korean_with_music(self, client):
        """Korean with some music markers should still be accepted if enough speech."""
        text = "안녕하세요 ♪ 오늘은 좋은 날이에요 ♪ 여러분 모두 행복하세요"
        result = client._assess_transcription_quality(text, [])
        assert result.has_speech is True
        assert result.reason == "ok"

    def test_lyrics_only(self, client):
        """Lyrics with low speech ratio should be rejected."""
        text = "♪ la la la ♪ ♫ do re mi ♫ ♪♪♪"
        result = client._assess_transcription_quality(text, [])
        # This has low speech ratio since lyrics are mostly music markers
        assert result.has_speech is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
