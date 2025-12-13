"""Unit tests for RRF fusion module."""
import pytest

from src.domain.search.fusion import (
    rrf_fuse,
    dense_only_fusion,
    lexical_only_fusion,
    Candidate,
    FusedCandidate,
)


class TestRRFFusion:
    """Tests for rrf_fuse function."""

    def test_empty_inputs_returns_empty(self):
        """Empty candidate lists should return empty results."""
        result = rrf_fuse([], [], rrf_k=60, top_k=10)
        assert result == []

    def test_dense_only_candidates(self):
        """When only dense candidates exist, they should still be fused."""
        dense = [
            Candidate(scene_id="a", rank=1, score=0.95),
            Candidate(scene_id="b", rank=2, score=0.85),
        ]
        result = rrf_fuse(dense, [], rrf_k=60, top_k=10)

        assert len(result) == 2
        assert result[0].scene_id == "a"
        assert result[1].scene_id == "b"
        # Check dense_rank is set, lexical_rank is None
        assert result[0].dense_rank == 1
        assert result[0].lexical_rank is None

    def test_lexical_only_candidates(self):
        """When only lexical candidates exist, they should still be fused."""
        lexical = [
            Candidate(scene_id="x", rank=1, score=25.0),
            Candidate(scene_id="y", rank=2, score=20.0),
        ]
        result = rrf_fuse([], lexical, rrf_k=60, top_k=10)

        assert len(result) == 2
        assert result[0].scene_id == "x"
        assert result[1].scene_id == "y"
        # Check lexical_rank is set, dense_rank is None
        assert result[0].lexical_rank == 1
        assert result[0].dense_rank is None

    def test_overlapping_candidates_boost(self):
        """Candidates appearing in both lists should have higher fused scores."""
        dense = [
            Candidate(scene_id="a", rank=1, score=0.95),
            Candidate(scene_id="b", rank=2, score=0.85),
        ]
        lexical = [
            Candidate(scene_id="b", rank=1, score=25.0),  # "b" is top in lexical
            Candidate(scene_id="c", rank=2, score=20.0),
        ]

        result = rrf_fuse(dense, lexical, rrf_k=60, top_k=10)

        # "b" appears in both lists, should be ranked higher
        assert len(result) == 3
        # "b" should be first due to appearing in both lists
        assert result[0].scene_id == "b"
        assert result[0].dense_rank == 2
        assert result[0].lexical_rank == 1

        # Verify fused score calculation for "b": 1/(60+2) + 1/(60+1) = 1/62 + 1/61
        expected_b_score = 1 / 62 + 1 / 61
        assert abs(result[0].fused_score - expected_b_score) < 0.0001

    def test_top_k_limit(self):
        """Should return at most top_k results."""
        dense = [Candidate(scene_id=f"d{i}", rank=i, score=1.0 - i * 0.1) for i in range(1, 11)]
        lexical = [Candidate(scene_id=f"l{i}", rank=i, score=30 - i) for i in range(1, 11)]

        result = rrf_fuse(dense, lexical, rrf_k=60, top_k=5)

        assert len(result) == 5

    def test_tie_breaking_by_dense_rank(self):
        """When fused scores are equal, prefer better dense rank."""
        # Create candidates with same RRF contribution from different sources
        # Scene "a" has dense rank 1, scene "b" has lexical rank 1
        # With k=60: 1/(60+1) = ~0.0164 for rank 1
        dense = [Candidate(scene_id="a", rank=1, score=0.9)]
        lexical = [Candidate(scene_id="b", rank=1, score=25.0)]

        result = rrf_fuse(dense, lexical, rrf_k=60, top_k=10)

        # Both have same fused score, but "a" has dense_rank while "b" doesn't
        assert len(result) == 2
        # "a" should be first because it has a dense_rank (1) vs "b" (None -> inf)
        assert result[0].scene_id == "a"
        assert result[1].scene_id == "b"

    def test_rrf_k_parameter_effect(self):
        """Higher rrf_k should flatten score differences between ranks."""
        dense = [
            Candidate(scene_id="first", rank=1, score=0.99),
            Candidate(scene_id="tenth", rank=10, score=0.7),
        ]

        # With low k, rank 1 has much higher weight
        result_low_k = rrf_fuse(dense, [], rrf_k=1, top_k=10)
        score_diff_low_k = result_low_k[0].fused_score - result_low_k[1].fused_score

        # With high k, scores are more similar
        result_high_k = rrf_fuse(dense, [], rrf_k=100, top_k=10)
        score_diff_high_k = result_high_k[0].fused_score - result_high_k[1].fused_score

        # Low k should have bigger score difference
        assert score_diff_low_k > score_diff_high_k

    def test_preserves_original_scores(self):
        """Fused results should preserve original scores."""
        dense = [Candidate(scene_id="a", rank=1, score=0.95)]
        lexical = [Candidate(scene_id="a", rank=1, score=25.0)]

        result = rrf_fuse(dense, lexical, rrf_k=60, top_k=10)

        assert result[0].dense_score == 0.95
        assert result[0].lexical_score == 25.0


class TestDenseOnlyFusion:
    """Tests for dense_only_fusion fallback."""

    def test_converts_candidates_to_fused(self):
        """Should convert dense candidates to FusedCandidate format."""
        dense = [
            Candidate(scene_id="a", rank=1, score=0.95),
            Candidate(scene_id="b", rank=2, score=0.85),
        ]

        result = dense_only_fusion(dense, top_k=10)

        assert len(result) == 2
        assert result[0].scene_id == "a"
        assert result[0].fused_score == 0.95  # Uses similarity as fused score
        assert result[0].dense_rank == 1
        assert result[0].lexical_rank is None

    def test_respects_top_k(self):
        """Should limit results to top_k."""
        dense = [Candidate(scene_id=f"s{i}", rank=i, score=1.0 / i) for i in range(1, 20)]

        result = dense_only_fusion(dense, top_k=5)

        assert len(result) == 5


class TestLexicalOnlyFusion:
    """Tests for lexical_only_fusion fallback."""

    def test_converts_candidates_to_fused(self):
        """Should convert lexical candidates to FusedCandidate format."""
        lexical = [
            Candidate(scene_id="x", rank=1, score=25.0),
            Candidate(scene_id="y", rank=2, score=20.0),
        ]

        result = lexical_only_fusion(lexical, top_k=10)

        assert len(result) == 2
        assert result[0].scene_id == "x"
        assert result[0].fused_score == 25.0  # Uses BM25 score as fused score
        assert result[0].lexical_rank == 1
        assert result[0].dense_rank is None

    def test_respects_top_k(self):
        """Should limit results to top_k."""
        lexical = [Candidate(scene_id=f"s{i}", rank=i, score=30 - i) for i in range(1, 20)]

        result = lexical_only_fusion(lexical, top_k=5)

        assert len(result) == 5


class TestFusedCandidateDataclass:
    """Tests for FusedCandidate dataclass."""

    def test_all_fields_populated(self):
        """FusedCandidate should store all retrieval information."""
        fused = FusedCandidate(
            scene_id="test",
            fused_score=0.05,
            dense_rank=1,
            lexical_rank=2,
            dense_score=0.95,
            lexical_score=25.0,
        )

        assert fused.scene_id == "test"
        assert fused.fused_score == 0.05
        assert fused.dense_rank == 1
        assert fused.lexical_rank == 2
        assert fused.dense_score == 0.95
        assert fused.lexical_score == 25.0

    def test_optional_fields_default_to_none(self):
        """Optional fields should default to None."""
        fused = FusedCandidate(scene_id="test", fused_score=0.05)

        assert fused.dense_rank is None
        assert fused.lexical_rank is None
        assert fused.dense_score is None
        assert fused.lexical_score is None
