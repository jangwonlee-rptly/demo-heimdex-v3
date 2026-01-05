"""Unit tests for person-weighted fusion."""
import pytest

from src.domain.search.fusion import Candidate, FusedCandidate, ScoreType
from src.domain.search.person_fusion import fuse_with_person


class TestPersonFusionBasic:
    """Tests for basic person fusion functionality."""

    def test_person_dominant_ranking(self):
        """Person signal (0.65) should dominate content signal (0.35)."""
        # Scene A: high content (0.9), low person (0.3)
        # Scene B: low content (0.3), high person (0.9)
        # Expected: Scene B ranks higher due to person weight (0.65)

        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.9),
            Candidate(scene_id="scene_b", rank=2, score=0.3),
        ]

        person_candidates = [
            Candidate(scene_id="scene_b", rank=1, score=0.9),
            Candidate(scene_id="scene_a", rank=2, score=0.3),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        # Scene B should rank #1 (person signal dominates)
        assert len(result) == 2
        assert result[0].scene_id == "scene_b"
        assert result[1].scene_id == "scene_a"

    def test_overlapping_scenes_fusion(self):
        """Scenes appearing in both channels get combined scores."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.8),
            Candidate(scene_id="scene_b", rank=2, score=0.6),
        ]

        person_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.9),
            Candidate(scene_id="scene_c", rank=2, score=0.7),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        # All 3 unique scenes should be in results
        assert len(result) == 3
        scene_ids = [r.scene_id for r in result]
        assert "scene_a" in scene_ids
        assert "scene_b" in scene_ids
        assert "scene_c" in scene_ids

        # Scene A appears in both, should have highest combined score
        assert result[0].scene_id == "scene_a"


class TestPersonFusionFallbacks:
    """Tests for fallback behaviors when one channel is empty."""

    def test_content_only_fallback(self):
        """When person_candidates is empty, return content-only."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.9),
            Candidate(scene_id="scene_b", rank=2, score=0.8),
            Candidate(scene_id="scene_c", rank=3, score=0.7),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=[],  # Empty person candidates
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        # Should return content results with DENSE_ONLY score type
        assert len(result) == 3
        assert result[0].scene_id == "scene_a"
        assert result[0].score == pytest.approx(0.9)
        assert result[0].score_type == ScoreType.DENSE_ONLY
        assert "content" in result[0].channel_scores
        assert result[0].channel_scores["content"] == pytest.approx(0.9)

    def test_person_only_fallback(self):
        """When content_candidates is empty, return person-only."""
        person_candidates = [
            Candidate(scene_id="scene_x", rank=1, score=0.85),
            Candidate(scene_id="scene_y", rank=2, score=0.75),
        ]

        result = fuse_with_person(
            content_candidates=[],  # Empty content candidates
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        # Should return person results with DENSE_ONLY score type
        assert len(result) == 2
        assert result[0].scene_id == "scene_x"
        assert result[0].score == pytest.approx(0.85)
        assert result[0].score_type == ScoreType.DENSE_ONLY
        assert "person" in result[0].channel_scores
        assert result[0].channel_scores["person"] == pytest.approx(0.85)

    def test_both_empty_returns_empty(self):
        """When both candidates lists are empty, return empty list."""
        result = fuse_with_person(
            content_candidates=[],
            person_candidates=[],
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        assert result == []


class TestPersonFusionScoreType:
    """Tests for ScoreType correctness."""

    def test_fusion_score_type(self):
        """Fused results should have PERSON_CONTENT_FUSION score type."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.8),
        ]

        person_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.9),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        assert len(result) == 1
        assert result[0].score_type == ScoreType.PERSON_CONTENT_FUSION

    def test_content_only_score_type(self):
        """Content-only fallback uses DENSE_ONLY score type."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.8),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=[],
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        assert result[0].score_type == ScoreType.DENSE_ONLY

    def test_person_only_score_type(self):
        """Person-only fallback uses DENSE_ONLY score type."""
        person_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.9),
        ]

        result = fuse_with_person(
            content_candidates=[],
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        assert result[0].score_type == ScoreType.DENSE_ONLY


class TestPersonFusionChannelScores:
    """Tests for channel_scores population."""

    def test_channel_scores_both_present(self):
        """When scene appears in both channels, both scores are present."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.75),
        ]

        person_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.85),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        assert len(result) == 1
        assert "content" in result[0].channel_scores
        assert "person" in result[0].channel_scores
        assert result[0].channel_scores["content"] == 0.75
        assert result[0].channel_scores["person"] == 0.85

    def test_channel_scores_content_only_scene(self):
        """Scene only in content has content score, no person score."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.8),
            Candidate(scene_id="scene_b", rank=2, score=0.7),
        ]

        person_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.9),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        # Find scene_b in results
        scene_b = next(r for r in result if r.scene_id == "scene_b")
        assert "content" in scene_b.channel_scores
        assert "person" not in scene_b.channel_scores

    def test_channel_scores_person_only_scene(self):
        """Scene only in person has person score, no content score."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.8),
        ]

        person_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.9),
            Candidate(scene_id="scene_c", rank=2, score=0.85),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        # Find scene_c in results
        scene_c = next(r for r in result if r.scene_id == "scene_c")
        assert "person" in scene_c.channel_scores
        assert "content" not in scene_c.channel_scores


class TestPersonFusionNormalization:
    """Tests for min-max normalization stability."""

    def test_single_candidate_per_channel(self):
        """Single candidate per channel should not cause division by zero."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.8),
        ]

        person_candidates = [
            Candidate(scene_id="scene_b", rank=1, score=0.9),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        # Should not crash, both scenes present
        assert len(result) == 2
        assert not any(r.score != r.score for r in result)  # No NaN

    def test_constant_scores_per_channel(self):
        """Constant scores (max == min) should normalize to 1.0."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.5),
            Candidate(scene_id="scene_b", rank=2, score=0.5),
        ]

        person_candidates = [
            Candidate(scene_id="scene_c", rank=1, score=0.8),
            Candidate(scene_id="scene_d", rank=2, score=0.8),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            eps=1e-9,
            top_k=10,
        )

        # All scenes present, no NaN
        assert len(result) == 4
        assert not any(r.score != r.score for r in result)

    def test_large_score_range_difference(self):
        """Different score ranges between channels should normalize correctly."""
        # Content: small range (0.5-0.6)
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.6),
            Candidate(scene_id="scene_b", rank=2, score=0.5),
        ]

        # Person: large range (0.1-0.9)
        person_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.9),
            Candidate(scene_id="scene_b", rank=2, score=0.1),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        # Min-max normalization should handle different ranges
        assert len(result) == 2
        assert result[0].scene_id == "scene_a"  # High person score dominates
        assert 0.0 <= result[0].score <= 1.0
        assert 0.0 <= result[1].score <= 1.0


class TestPersonFusionTopK:
    """Tests for top_k truncation."""

    def test_top_k_truncation(self):
        """Results should be truncated to top_k."""
        content_candidates = [
            Candidate(scene_id=f"scene_{i}", rank=i, score=1.0 - i * 0.1)
            for i in range(10)
        ]

        person_candidates = [
            Candidate(scene_id=f"scene_{i}", rank=i, score=0.9 - i * 0.1)
            for i in range(10)
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=3,  # Only return top 3
        )

        assert len(result) == 3
        # Ranks are implicit in list position (0-indexed)

    def test_top_k_larger_than_results(self):
        """When top_k > total scenes, return all scenes."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.8),
            Candidate(scene_id="scene_b", rank=2, score=0.7),
        ]

        person_candidates = [
            Candidate(scene_id="scene_c", rank=1, score=0.9),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=100,  # Much larger than result count
        )

        # Should return all 3 unique scenes
        assert len(result) == 3

    def test_content_fallback_respects_top_k(self):
        """Content-only fallback should respect top_k."""
        content_candidates = [
            Candidate(scene_id=f"scene_{i}", rank=i, score=1.0 - i * 0.1)
            for i in range(10)
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=[],
            weight_content=0.35,
            weight_person=0.65,
            top_k=5,
        )

        assert len(result) == 5


class TestPersonFusionResultOrdering:
    """Tests for result ordering."""

    def test_results_sorted_by_score(self):
        """Results should be sorted by descending fused score."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.8),
            Candidate(scene_id="scene_b", rank=2, score=0.6),
        ]

        person_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.9),
            Candidate(scene_id="scene_b", rank=2, score=0.7),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        # Results should be in descending score order
        assert len(result) >= 2
        assert result[0].score >= result[1].score

    def test_rank_implicit_in_position(self):
        """Rank is implicit: result[0] = rank 1, result[1] = rank 2, etc."""
        content_candidates = [
            Candidate(scene_id=f"scene_{i}", rank=i, score=1.0 - i * 0.1)
            for i in range(5)
        ]

        person_candidates = [
            Candidate(scene_id=f"scene_{i}", rank=i, score=0.9 - i * 0.1)
            for i in range(5)
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.35,
            weight_person=0.65,
            top_k=10,
        )

        # Verify list is sorted (implicit ranks)
        for i in range(len(result) - 1):
            assert result[i].score >= result[i + 1].score


class TestPersonFusionWeights:
    """Tests for weight parameter effects."""

    def test_custom_weights(self):
        """Custom weights should be respected."""
        # Scene A: high content, low person
        # Scene B: low content, high person

        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.9),
            Candidate(scene_id="scene_b", rank=2, score=0.1),
        ]

        person_candidates = [
            Candidate(scene_id="scene_b", rank=1, score=0.9),
            Candidate(scene_id="scene_a", rank=2, score=0.1),
        ]

        # Test with content-dominant weights (0.8, 0.2)
        result_content_dominant = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.8,
            weight_person=0.2,
            top_k=10,
        )

        # Scene A should rank higher (content dominates)
        assert result_content_dominant[0].scene_id == "scene_a"

        # Test with person-dominant weights (0.2, 0.8)
        result_person_dominant = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.2,
            weight_person=0.8,
            top_k=10,
        )

        # Scene B should rank higher (person dominates)
        assert result_person_dominant[0].scene_id == "scene_b"

    def test_equal_weights(self):
        """Equal weights (0.5, 0.5) should balance both signals."""
        content_candidates = [
            Candidate(scene_id="scene_a", rank=1, score=0.8),
            Candidate(scene_id="scene_b", rank=2, score=0.6),
        ]

        person_candidates = [
            Candidate(scene_id="scene_b", rank=1, score=0.8),
            Candidate(scene_id="scene_a", rank=2, score=0.6),
        ]

        result = fuse_with_person(
            content_candidates=content_candidates,
            person_candidates=person_candidates,
            weight_content=0.5,
            weight_person=0.5,
            top_k=10,
        )

        # With equal weights and symmetrical scores, order may vary
        # but both scenes should have similar fused scores
        assert len(result) == 2
        # Scores should be close (both scenes have same pattern)
        assert abs(result[0].score - result[1].score) < 0.1
