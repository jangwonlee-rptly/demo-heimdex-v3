"""Unit tests for visual intent router."""
import pytest
from src.domain.visual_router import VisualIntentRouter


class TestVisualIntentRouter:
    """Test visual intent routing logic."""

    @pytest.fixture
    def router(self):
        """Create router instance."""
        return VisualIntentRouter()

    def test_strong_visual_intent(self, router):
        """Test queries with strong visual intent."""
        test_cases = [
            "show me scenes with a red car",
            "find footage of a person walking",
            "close-up of face",
            "scenes with bright colors and blue sky",
            "person wearing red shirt in crowd",
        ]

        for query in test_cases:
            result = router.analyze(query)
            assert result.has_visual_intent, f"Query should have visual intent: {query}"
            assert result.suggested_mode in ("recall", "rerank"), f"Unexpected mode for: {query}"
            assert result.confidence >= 0.5, f"Low confidence for visual query: {query}"
            assert len(result.matched_visual_terms) >= 1, f"Should match visual terms: {query}"

    def test_strong_speech_intent(self, router):
        """Test queries with strong speech/dialogue intent."""
        test_cases = [
            "the line where he says we're in this together",
            "when she says hello",
            "find the quote about love",
            "the part where they discuss the plan",
            '"I have a dream" speech',
        ]

        for query in test_cases:
            result = router.analyze(query)
            assert result.has_speech_intent, f"Query should have speech intent: {query}"
            assert result.suggested_mode == "skip", f"Should skip CLIP for: {query}"
            assert len(result.matched_speech_terms) >= 1, f"Should match speech terms: {query}"

    def test_mixed_intent(self, router):
        """Test queries with both visual and speech signals."""
        query = "scene where person says tteokbokki"

        result = router.analyze(query)
        assert result.has_visual_intent or result.has_speech_intent
        # Mixed queries should use rerank mode (safer)
        assert result.suggested_mode in ("rerank", "skip")

    def test_korean_food_terms(self, router):
        """Test Korean visual terms."""
        test_cases = [
            "떡볶이 scene",
            "tteokbokki on plate",
            "김치 in background",
        ]

        for query in test_cases:
            result = router.analyze(query)
            assert result.has_visual_intent, f"Korean term should trigger visual: {query}"

    def test_empty_query(self, router):
        """Test empty query handling."""
        result = router.analyze("")
        assert result.suggested_mode == "skip"
        assert result.confidence == 0.0
        assert not result.has_visual_intent
        assert not result.has_speech_intent

    def test_deterministic(self, router):
        """Test that router is deterministic."""
        query = "red car driving fast"

        # Run multiple times
        results = [router.analyze(query) for _ in range(3)]

        # All results should be identical
        assert all(r.suggested_mode == results[0].suggested_mode for r in results)
        assert all(r.confidence == results[0].confidence for r in results)
        assert all(r.has_visual_intent == results[0].has_visual_intent for r in results)

    def test_visual_attributes(self, router):
        """Test color and visual attribute matching."""
        query = "bright scene with green background"

        result = router.analyze(query)
        assert result.has_visual_intent
        # Should match: bright, green, background
        assert len(result.matched_visual_terms) >= 2

    def test_visual_actions(self, router):
        """Test action detection."""
        query = "person running and jumping"

        result = router.analyze(query)
        assert result.has_visual_intent
        # Should match: person, running, jumping
        assert len(result.matched_visual_terms) >= 2

    def test_long_question_detection(self, router):
        """Test that long questions are treated as speech intent."""
        query = "What is the main argument presented in the discussion about climate change?"

        result = router.analyze(query)
        # Long questions likely seek meaning/dialogue, not visuals
        assert "long_question" in result.matched_speech_terms or result.suggested_mode == "skip"

    def test_quote_detection(self, router):
        """Test quote detection."""
        queries_with_quotes = [
            '"hello world" in speech',
            "he said 'goodbye'",
            "the line "we have a dream"",
        ]

        for query in queries_with_quotes:
            result = router.analyze(query)
            assert result.has_speech_intent, f"Should detect quotes in: {query}"
            assert any("quote" in term for term in result.matched_speech_terms), f"Missing quote detection: {query}"
