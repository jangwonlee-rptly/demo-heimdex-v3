"""Unit tests for hybrid search fusion module."""
import pytest

from src.domain.search.fusion import (
    minmax_normalize,
    minmax_weighted_mean_fuse,
    rrf_fuse,
    dense_only_fusion,
    lexical_only_fusion,
    fuse,
    multi_channel_minmax_fuse,
    multi_channel_rrf_fuse,
    Candidate,
    FusedCandidate,
    ScoreType,
)


class TestMinMaxNormalization:
    """Tests for minmax_normalize function."""

    def test_basic_normalization(self):
        """Basic normalization should scale to [0, 1]."""
        scores = [10.0, 20.0, 30.0]
        result = minmax_normalize(scores)

        assert len(result) == 3
        assert result[0] == pytest.approx(0.0, abs=0.001)  # min -> 0
        assert result[1] == pytest.approx(0.5, abs=0.001)  # middle -> 0.5
        assert result[2] == pytest.approx(1.0, abs=0.001)  # max -> 1

    def test_single_element_returns_one(self):
        """Single element should return 1.0 (uniform contribution)."""
        result = minmax_normalize([42.0])
        assert result == [1.0]

    def test_constant_scores_returns_ones(self):
        """When all scores are the same (max == min), return all 1.0."""
        result = minmax_normalize([5.0, 5.0, 5.0])
        assert result == [1.0, 1.0, 1.0]

    def test_empty_list_returns_empty(self):
        """Empty input should return empty output."""
        result = minmax_normalize([])
        assert result == []

    def test_negative_scores(self):
        """Should handle negative scores correctly."""
        scores = [-10.0, 0.0, 10.0]
        result = minmax_normalize(scores)

        assert result[0] == pytest.approx(0.0, abs=0.001)  # min
        assert result[1] == pytest.approx(0.5, abs=0.001)  # middle
        assert result[2] == pytest.approx(1.0, abs=0.001)  # max

    def test_large_range(self):
        """Should handle large score ranges (like BM25)."""
        scores = [0.5, 25.0, 50.0]
        result = minmax_normalize(scores)

        assert result[0] == pytest.approx(0.0, abs=0.001)
        assert result[1] == pytest.approx((25.0 - 0.5) / (50.0 - 0.5), abs=0.001)
        assert result[2] == pytest.approx(1.0, abs=0.001)

    def test_near_constant_scores_with_eps(self):
        """Very small differences (< eps) should be treated as constant."""
        scores = [1.0, 1.0 + 1e-12, 1.0 + 2e-12]
        result = minmax_normalize(scores, eps=1e-9)
        # All should be 1.0 since difference < eps
        assert all(s == 1.0 for s in result)

    def test_clamping_behavior(self):
        """Results should always be in [0, 1] range."""
        scores = [0.0, 0.5, 1.0]
        result = minmax_normalize(scores)

        for score in result:
            assert 0.0 <= score <= 1.0


class TestMinMaxWeightedMeanFusion:
    """Tests for minmax_weighted_mean_fuse function."""

    def test_basic_fusion(self):
        """Basic fusion with both dense and lexical candidates."""
        dense = [
            Candidate(scene_id="a", rank=1, score=0.95),
            Candidate(scene_id="b", rank=2, score=0.85),
        ]
        lexical = [
            Candidate(scene_id="b", rank=1, score=25.0),
            Candidate(scene_id="c", rank=2, score=20.0),
        ]

        result = minmax_weighted_mean_fuse(
            dense, lexical,
            weight_dense=0.7, weight_lexical=0.3,
            top_k=10
        )

        assert len(result) == 3  # Union of a, b, c
        # All results should have MINMAX_MEAN score type
        assert all(r.score_type == ScoreType.MINMAX_MEAN for r in result)
        # "b" appears in both lists, should have highest score
        assert result[0].scene_id == "b"

    def test_overlapping_candidates_boost(self):
        """Candidates in both lists should get boosted scores."""
        dense = [Candidate(scene_id="shared", rank=1, score=1.0)]
        lexical = [Candidate(scene_id="shared", rank=1, score=50.0)]

        result = minmax_weighted_mean_fuse(
            dense, lexical,
            weight_dense=0.5, weight_lexical=0.5,
            top_k=10
        )

        assert len(result) == 1
        # Single candidate in each list normalizes to 1.0
        # Combined score should be 0.5 * 1.0 + 0.5 * 1.0 = 1.0
        assert result[0].score == pytest.approx(1.0, abs=0.001)

    def test_missing_dense_scores_treated_as_zero(self):
        """Candidates only in lexical should get 0 for dense contribution."""
        dense = [Candidate(scene_id="dense_only", rank=1, score=0.9)]
        lexical = [
            Candidate(scene_id="lexical_only", rank=1, score=30.0),
            Candidate(scene_id="lexical_only2", rank=2, score=20.0),
        ]

        result = minmax_weighted_mean_fuse(
            dense, lexical,
            weight_dense=0.7, weight_lexical=0.3,
            top_k=10
        )

        # dense_only: 0.7 * 1.0 + 0.3 * 0.0 = 0.7
        # lexical_only: 0.7 * 0.0 + 0.3 * 1.0 = 0.3
        dense_only_result = next(r for r in result if r.scene_id == "dense_only")
        lexical_only_result = next(r for r in result if r.scene_id == "lexical_only")

        assert dense_only_result.score == pytest.approx(0.7, abs=0.001)
        assert lexical_only_result.score == pytest.approx(0.3, abs=0.001)

    def test_weights_sum_validation(self):
        """Should raise ValueError if weights don't sum to 1.0."""
        dense = [Candidate(scene_id="a", rank=1, score=0.9)]
        lexical = [Candidate(scene_id="b", rank=1, score=25.0)]

        with pytest.raises(ValueError, match="sum to 1.0"):
            minmax_weighted_mean_fuse(
                dense, lexical,
                weight_dense=0.7, weight_lexical=0.5,  # Sum is 1.2
                top_k=10
            )

    def test_weights_sum_with_tolerance(self):
        """Should allow small float errors in weight sum."""
        dense = [Candidate(scene_id="a", rank=1, score=0.9)]
        lexical = [Candidate(scene_id="b", rank=1, score=25.0)]

        # This should NOT raise (within 0.01 tolerance)
        result = minmax_weighted_mean_fuse(
            dense, lexical,
            weight_dense=0.699, weight_lexical=0.301,  # Sum is 1.0
            top_k=10
        )
        assert len(result) == 2

    def test_empty_inputs_returns_empty(self):
        """Empty candidate lists should return empty results."""
        result = minmax_weighted_mean_fuse([], [], top_k=10)
        assert result == []

    def test_dense_only_candidates(self):
        """When only dense candidates exist, should still work."""
        dense = [
            Candidate(scene_id="a", rank=1, score=0.95),
            Candidate(scene_id="b", rank=2, score=0.85),
        ]

        result = minmax_weighted_mean_fuse(
            dense, [],
            weight_dense=0.7, weight_lexical=0.3,
            top_k=10
        )

        assert len(result) == 2
        # "a" has normalized score 1.0, gets 0.7 * 1.0 = 0.7
        assert result[0].scene_id == "a"
        assert result[0].score == pytest.approx(0.7, abs=0.001)

    def test_lexical_only_candidates(self):
        """When only lexical candidates exist, should still work."""
        lexical = [
            Candidate(scene_id="x", rank=1, score=25.0),
            Candidate(scene_id="y", rank=2, score=20.0),
        ]

        result = minmax_weighted_mean_fuse(
            [], lexical,
            weight_dense=0.7, weight_lexical=0.3,
            top_k=10
        )

        assert len(result) == 2
        # "x" has normalized score 1.0, gets 0.3 * 1.0 = 0.3
        assert result[0].scene_id == "x"
        assert result[0].score == pytest.approx(0.3, abs=0.001)

    def test_top_k_limit(self):
        """Should return at most top_k results."""
        dense = [Candidate(scene_id=f"d{i}", rank=i, score=1.0 - i * 0.1) for i in range(1, 11)]
        lexical = [Candidate(scene_id=f"l{i}", rank=i, score=30 - i) for i in range(1, 11)]

        result = minmax_weighted_mean_fuse(dense, lexical, top_k=5)

        assert len(result) == 5

    def test_preserves_raw_and_norm_scores(self):
        """Should preserve both raw and normalized scores."""
        dense = [Candidate(scene_id="a", rank=1, score=0.95)]
        lexical = [Candidate(scene_id="a", rank=1, score=25.0)]

        result = minmax_weighted_mean_fuse(dense, lexical, top_k=10)

        assert result[0].dense_score_raw == 0.95
        assert result[0].lexical_score_raw == 25.0
        # Single items normalize to 1.0
        assert result[0].dense_score_norm == 1.0
        assert result[0].lexical_score_norm == 1.0

    def test_tie_breaking_by_dense_rank(self):
        """When scores are equal, prefer better dense rank."""
        # Create candidates where both have same weighted score
        dense = [Candidate(scene_id="a", rank=1, score=1.0)]
        lexical = [Candidate(scene_id="b", rank=1, score=1.0)]

        # Both normalize to 1.0, both get same weighted score
        # a: 0.7 * 1.0 + 0.3 * 0.0 = 0.7
        # b: 0.7 * 0.0 + 0.3 * 1.0 = 0.3
        result = minmax_weighted_mean_fuse(
            dense, lexical,
            weight_dense=0.7, weight_lexical=0.3,
            top_k=10
        )

        # "a" should be first (higher score)
        assert result[0].scene_id == "a"

    def test_deterministic_ordering(self):
        """Results should be deterministically ordered."""
        dense = [Candidate(scene_id="a", rank=1, score=0.9)]
        lexical = [Candidate(scene_id="b", rank=1, score=25.0)]

        # Run multiple times
        results = [
            minmax_weighted_mean_fuse(dense, lexical, top_k=10)
            for _ in range(5)
        ]

        # All runs should produce same order
        for r in results:
            assert [c.scene_id for c in r] == [c.scene_id for c in results[0]]


class TestRRFFusion:
    """Tests for rrf_fuse function (ensure no regression)."""

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
        assert result[0].dense_rank == 1
        assert result[0].lexical_rank is None
        assert result[0].score_type == ScoreType.RRF

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
        assert result[0].scene_id == "b"
        assert result[0].dense_rank == 2
        assert result[0].lexical_rank == 1

        # Verify fused score calculation for "b": 1/(60+2) + 1/(60+1) = 1/62 + 1/61
        expected_b_score = 1 / 62 + 1 / 61
        assert abs(result[0].score - expected_b_score) < 0.0001

    def test_top_k_limit(self):
        """Should return at most top_k results."""
        dense = [Candidate(scene_id=f"d{i}", rank=i, score=1.0 - i * 0.1) for i in range(1, 11)]
        lexical = [Candidate(scene_id=f"l{i}", rank=i, score=30 - i) for i in range(1, 11)]

        result = rrf_fuse(dense, lexical, rrf_k=60, top_k=5)

        assert len(result) == 5

    def test_tie_breaking_by_dense_rank(self):
        """When fused scores are equal, prefer better dense rank."""
        dense = [Candidate(scene_id="a", rank=1, score=0.9)]
        lexical = [Candidate(scene_id="b", rank=1, score=25.0)]

        result = rrf_fuse(dense, lexical, rrf_k=60, top_k=10)

        # Both have same fused score, but "a" has dense_rank (1) vs "b" (None -> inf)
        assert len(result) == 2
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
        score_diff_low_k = result_low_k[0].score - result_low_k[1].score

        # With high k, scores are more similar
        result_high_k = rrf_fuse(dense, [], rrf_k=100, top_k=10)
        score_diff_high_k = result_high_k[0].score - result_high_k[1].score

        # Low k should have bigger score difference
        assert score_diff_low_k > score_diff_high_k

    def test_preserves_original_scores(self):
        """Fused results should preserve original scores."""
        dense = [Candidate(scene_id="a", rank=1, score=0.95)]
        lexical = [Candidate(scene_id="a", rank=1, score=25.0)]

        result = rrf_fuse(dense, lexical, rrf_k=60, top_k=10)

        assert result[0].dense_score_raw == 0.95
        assert result[0].lexical_score_raw == 25.0
        # RRF doesn't use normalized scores
        assert result[0].dense_score_norm is None
        assert result[0].lexical_score_norm is None


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
        assert result[0].score == 0.95  # Uses similarity as score
        assert result[0].score_type == ScoreType.DENSE_ONLY
        assert result[0].dense_rank == 1
        assert result[0].lexical_rank is None

    def test_with_normalization(self):
        """Should normalize scores when requested."""
        dense = [
            Candidate(scene_id="a", rank=1, score=0.95),
            Candidate(scene_id="b", rank=2, score=0.85),
        ]

        result = dense_only_fusion(dense, top_k=10, normalize=True)

        assert result[0].score == pytest.approx(1.0, abs=0.001)  # max -> 1
        assert result[1].score == pytest.approx(0.0, abs=0.001)  # min -> 0
        assert result[0].dense_score_norm == pytest.approx(1.0, abs=0.001)

    def test_respects_top_k(self):
        """Should limit results to top_k."""
        dense = [Candidate(scene_id=f"s{i}", rank=i, score=1.0 / i) for i in range(1, 20)]

        result = dense_only_fusion(dense, top_k=5)

        assert len(result) == 5

    def test_empty_input(self):
        """Should handle empty input gracefully."""
        result = dense_only_fusion([], top_k=10)
        assert result == []


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
        assert result[0].score == 25.0  # Uses BM25 score as score
        assert result[0].score_type == ScoreType.LEXICAL_ONLY
        assert result[0].lexical_rank == 1
        assert result[0].dense_rank is None

    def test_with_normalization(self):
        """Should normalize scores when requested."""
        lexical = [
            Candidate(scene_id="x", rank=1, score=30.0),
            Candidate(scene_id="y", rank=2, score=10.0),
        ]

        result = lexical_only_fusion(lexical, top_k=10, normalize=True)

        assert result[0].score == pytest.approx(1.0, abs=0.001)  # max -> 1
        assert result[1].score == pytest.approx(0.0, abs=0.001)  # min -> 0
        assert result[0].lexical_score_norm == pytest.approx(1.0, abs=0.001)

    def test_respects_top_k(self):
        """Should limit results to top_k."""
        lexical = [Candidate(scene_id=f"s{i}", rank=i, score=30 - i) for i in range(1, 20)]

        result = lexical_only_fusion(lexical, top_k=5)

        assert len(result) == 5

    def test_empty_input(self):
        """Should handle empty input gracefully."""
        result = lexical_only_fusion([], top_k=10)
        assert result == []


class TestUnifiedFuseFunction:
    """Tests for the unified fuse() dispatcher function."""

    def test_dispatches_to_minmax_mean(self):
        """Should dispatch to minmax_weighted_mean_fuse for minmax_mean method."""
        dense = [Candidate(scene_id="a", rank=1, score=0.9)]
        lexical = [Candidate(scene_id="b", rank=1, score=25.0)]

        result = fuse(dense, lexical, method="minmax_mean", top_k=10)

        assert all(r.score_type == ScoreType.MINMAX_MEAN for r in result)

    def test_dispatches_to_rrf(self):
        """Should dispatch to rrf_fuse for rrf method."""
        dense = [Candidate(scene_id="a", rank=1, score=0.9)]
        lexical = [Candidate(scene_id="b", rank=1, score=25.0)]

        result = fuse(dense, lexical, method="rrf", top_k=10)

        assert all(r.score_type == ScoreType.RRF for r in result)

    def test_raises_for_unknown_method(self):
        """Should raise ValueError for unknown fusion method."""
        dense = [Candidate(scene_id="a", rank=1, score=0.9)]

        with pytest.raises(ValueError, match="Unknown fusion method"):
            fuse(dense, [], method="unknown_method", top_k=10)

    def test_passes_weights_to_minmax(self):
        """Should pass weight parameters to minmax fusion."""
        dense = [Candidate(scene_id="a", rank=1, score=1.0)]

        result = fuse(
            dense, [],
            method="minmax_mean",
            weight_dense=0.8,
            weight_lexical=0.2,
            top_k=10
        )

        # Score should reflect the dense weight
        assert result[0].score == pytest.approx(0.8, abs=0.001)

    def test_passes_rrf_k_to_rrf(self):
        """Should pass rrf_k parameter to rrf fusion."""
        dense = [Candidate(scene_id="a", rank=1, score=0.9)]

        result_k_60 = fuse(dense, [], method="rrf", rrf_k=60, top_k=10)
        result_k_10 = fuse(dense, [], method="rrf", rrf_k=10, top_k=10)

        # Different k values should produce different scores
        assert result_k_60[0].score != result_k_10[0].score
        # Lower k gives higher score
        assert result_k_10[0].score > result_k_60[0].score


class TestFusedCandidateDataclass:
    """Tests for FusedCandidate dataclass."""

    def test_all_fields_populated(self):
        """FusedCandidate should store all retrieval information."""
        fused = FusedCandidate(
            scene_id="test",
            score=0.75,
            score_type=ScoreType.MINMAX_MEAN,
            dense_rank=1,
            lexical_rank=2,
            dense_score_raw=0.95,
            lexical_score_raw=25.0,
            dense_score_norm=0.9,
            lexical_score_norm=0.8,
        )

        assert fused.scene_id == "test"
        assert fused.score == 0.75
        assert fused.score_type == ScoreType.MINMAX_MEAN
        assert fused.dense_rank == 1
        assert fused.lexical_rank == 2
        assert fused.dense_score_raw == 0.95
        assert fused.lexical_score_raw == 25.0
        assert fused.dense_score_norm == 0.9
        assert fused.lexical_score_norm == 0.8

    def test_optional_fields_default_to_none(self):
        """Optional fields should default to None."""
        fused = FusedCandidate(
            scene_id="test",
            score=0.05,
            score_type=ScoreType.RRF,
        )

        assert fused.dense_rank is None
        assert fused.lexical_rank is None
        assert fused.dense_score_raw is None
        assert fused.lexical_score_raw is None
        assert fused.dense_score_norm is None
        assert fused.lexical_score_norm is None

    def test_backward_compatibility_aliases(self):
        """Legacy aliases should work for backward compatibility."""
        fused = FusedCandidate(
            scene_id="test",
            score=0.75,
            score_type=ScoreType.MINMAX_MEAN,
            dense_score_raw=0.95,
            lexical_score_raw=25.0,
        )

        # Legacy aliases
        assert fused.fused_score == 0.75  # Alias for score
        assert fused.dense_score == 0.95  # Alias for dense_score_raw
        assert fused.lexical_score == 25.0  # Alias for lexical_score_raw


class TestScoreType:
    """Tests for ScoreType enum."""

    def test_string_values(self):
        """ScoreType should have correct string values."""
        assert ScoreType.MINMAX_MEAN.value == "minmax_mean"
        assert ScoreType.RRF.value == "rrf"
        assert ScoreType.DENSE_ONLY.value == "dense_only"
        assert ScoreType.LEXICAL_ONLY.value == "lexical_only"

    def test_is_string_enum(self):
        """ScoreType should be a string enum (can be used directly as string)."""
        assert str(ScoreType.MINMAX_MEAN) == "ScoreType.MINMAX_MEAN"
        assert ScoreType.MINMAX_MEAN == "minmax_mean"


class TestFusionEdgeCases:
    """Edge case tests for fusion functions."""

    def test_large_candidate_lists(self):
        """Should handle large candidate lists efficiently."""
        dense = [Candidate(scene_id=f"d{i}", rank=i, score=1.0 - i * 0.001) for i in range(1, 1001)]
        lexical = [Candidate(scene_id=f"l{i}", rank=i, score=100 - i * 0.1) for i in range(1, 1001)]

        result = minmax_weighted_mean_fuse(dense, lexical, top_k=10)

        assert len(result) == 10
        # Should not crash or timeout

    def test_duplicate_scene_ids_in_same_list(self):
        """If same scene_id appears twice in one list, last one wins (dict behavior)."""
        # This is an edge case that shouldn't happen in practice
        dense = [
            Candidate(scene_id="dup", rank=1, score=0.95),
            Candidate(scene_id="dup", rank=2, score=0.50),  # Same ID
        ]

        result = minmax_weighted_mean_fuse(dense, [], top_k=10)

        # Dict overwrites, so only one entry for "dup"
        assert len(result) == 1
        assert result[0].scene_id == "dup"

    def test_very_small_scores(self):
        """Should handle very small scores without precision issues."""
        dense = [
            Candidate(scene_id="a", rank=1, score=1e-10),
            Candidate(scene_id="b", rank=2, score=1e-11),
        ]

        result = minmax_weighted_mean_fuse(dense, [], top_k=10)

        assert len(result) == 2
        # Normalization should still work
        assert result[0].dense_score_norm == pytest.approx(1.0, abs=0.001)
        assert result[1].dense_score_norm == pytest.approx(0.0, abs=0.001)

    def test_very_large_scores(self):
        """Should handle very large scores without overflow."""
        lexical = [
            Candidate(scene_id="a", rank=1, score=1e10),
            Candidate(scene_id="b", rank=2, score=1e9),
        ]

        result = minmax_weighted_mean_fuse([], lexical, top_k=10)

        assert len(result) == 2
        assert result[0].lexical_score_norm == pytest.approx(1.0, abs=0.001)
        assert result[1].lexical_score_norm == pytest.approx(0.0, abs=0.001)

    def test_zero_scores(self):
        """Should handle zero scores correctly."""
        dense = [
            Candidate(scene_id="a", rank=1, score=0.0),
            Candidate(scene_id="b", rank=2, score=0.0),
        ]

        result = minmax_weighted_mean_fuse(dense, [], top_k=10)

        # All zeros should normalize to 1.0 (constant case)
        assert all(r.dense_score_norm == 1.0 for r in result)


class TestMultiChannelMinMaxFusion:
    """Tests for multi_channel_minmax_fuse (v3-multi Option B)."""

    def test_basic_multi_channel_fusion(self):
        """Basic fusion with 4 channels (3 dense + 1 lexical)."""
        channels = {
            "dense_transcript": [
                Candidate(scene_id="a", rank=1, score=0.95),
                Candidate(scene_id="b", rank=2, score=0.85),
            ],
            "dense_visual": [
                Candidate(scene_id="b", rank=1, score=0.90),
                Candidate(scene_id="c", rank=2, score=0.80),
            ],
            "dense_summary": [
                Candidate(scene_id="c", rank=1, score=0.88),
            ],
            "lexical": [
                Candidate(scene_id="a", rank=1, score=25.0),
                Candidate(scene_id="d", rank=2, score=20.0),
            ],
        }

        weights = {
            "dense_transcript": 0.45,
            "dense_visual": 0.25,
            "dense_summary": 0.10,
            "lexical": 0.20,
        }

        result = multi_channel_minmax_fuse(
            channel_candidates=channels,
            channel_weights=weights,
            eps=1e-9,
            top_k=10,
            include_debug=False,
        )

        # Should return union of all scenes
        scene_ids = {r.scene_id for r in result}
        assert scene_ids == {"a", "b", "c", "d"}

        # All should have MULTI_DENSE_MINMAX_MEAN score type
        assert all(r.score_type == ScoreType.MULTI_DENSE_MINMAX_MEAN for r in result)

        # "b" appears in both transcript and visual, should rank highly
        assert result[0].scene_id in ["a", "b"]  # Top scores

    def test_weight_redistribution_when_channel_missing(self):
        """Weights should redistribute when a channel has no results."""
        channels = {
            "dense_transcript": [Candidate(scene_id="a", rank=1, score=0.95)],
            "dense_visual": [],  # Empty channel
            "lexical": [Candidate(scene_id="b", rank=1, score=25.0)],
        }

        weights = {
            "dense_transcript": 0.50,
            "dense_visual": 0.30,  # This should be redistributed
            "lexical": 0.20,
        }

        result = multi_channel_minmax_fuse(
            channel_candidates=channels,
            channel_weights=weights,
            top_k=10,
        )

        # Should gracefully handle empty channel
        assert len(result) == 2
        scene_ids = {r.scene_id for r in result}
        assert scene_ids == {"a", "b"}

        # Weights should redistribute: transcript gets 0.50/0.70, lexical gets 0.20/0.70
        # "a": (0.50/0.70) * 1.0 + (0.20/0.70) * 0.0 ≈ 0.714
        # "b": (0.50/0.70) * 0.0 + (0.20/0.70) * 1.0 ≈ 0.286
        assert result[0].scene_id == "a"  # Higher redistributed weight

    def test_weight_validation_must_sum_to_one(self):
        """Weights must sum to 1.0 (within tolerance)."""
        channels = {
            "dense_transcript": [Candidate(scene_id="a", rank=1, score=0.95)],
        }

        invalid_weights = {
            "dense_transcript": 0.60,
            "dense_visual": 0.60,  # Sum is 1.2
        }

        with pytest.raises(ValueError, match="sum to 1.0"):
            multi_channel_minmax_fuse(
                channel_candidates=channels,
                channel_weights=invalid_weights,
                top_k=10,
            )

    def test_debug_mode_includes_channel_scores(self):
        """Debug mode should include per-channel score breakdown."""
        channels = {
            "dense_transcript": [Candidate(scene_id="a", rank=1, score=0.95)],
            "lexical": [Candidate(scene_id="a", rank=1, score=25.0)],
        }

        weights = {
            "dense_transcript": 0.80,
            "lexical": 0.20,
        }

        result = multi_channel_minmax_fuse(
            channel_candidates=channels,
            channel_weights=weights,
            top_k=10,
            include_debug=True,
        )

        assert len(result) == 1
        assert result[0].channel_scores is not None
        assert "dense_transcript" in result[0].channel_scores
        assert "lexical" in result[0].channel_scores

        # Check channel_scores structure
        transcript_scores = result[0].channel_scores["dense_transcript"]
        assert "rank" in transcript_scores
        assert "score_raw" in transcript_scores
        assert "score_norm" in transcript_scores
        assert transcript_scores["rank"] == 1
        assert transcript_scores["score_raw"] == 0.95

    def test_scene_present_in_one_channel_only(self):
        """Scenes appearing in only one channel should still rank correctly."""
        channels = {
            "dense_transcript": [Candidate(scene_id="transcript_only", rank=1, score=0.90)],
            "dense_visual": [Candidate(scene_id="visual_only", rank=1, score=0.85)],
        }

        weights = {
            "dense_transcript": 0.70,
            "dense_visual": 0.30,
        }

        result = multi_channel_minmax_fuse(
            channel_candidates=channels,
            channel_weights=weights,
            top_k=10,
        )

        # transcript_only: 0.70 * 1.0 + 0.30 * 0.0 = 0.70
        # visual_only: 0.70 * 0.0 + 0.30 * 1.0 = 0.30
        assert result[0].scene_id == "transcript_only"  # Higher weight
        assert result[1].scene_id == "visual_only"

    def test_empty_channels_returns_empty_result(self):
        """All empty channels should return empty result."""
        channels = {
            "dense_transcript": [],
            "dense_visual": [],
            "lexical": [],
        }

        weights = {
            "dense_transcript": 0.45,
            "dense_visual": 0.35,
            "lexical": 0.20,
        }

        result = multi_channel_minmax_fuse(
            channel_candidates=channels,
            channel_weights=weights,
            top_k=10,
        )

        assert result == []

    def test_top_k_limit_respected(self):
        """Should return at most top_k results."""
        channels = {
            "dense_transcript": [
                Candidate(scene_id=f"s{i}", rank=i, score=1.0 - i * 0.1)
                for i in range(1, 21)
            ],
        }

        weights = {"dense_transcript": 1.0}

        result = multi_channel_minmax_fuse(
            channel_candidates=channels,
            channel_weights=weights,
            top_k=5,
        )

        assert len(result) == 5

    def test_multi_channel_normalization_independence(self):
        """Each channel should normalize independently."""
        channels = {
            "dense_transcript": [
                Candidate(scene_id="a", rank=1, score=0.90),
                Candidate(scene_id="b", rank=2, score=0.80),
            ],
            "dense_visual": [
                Candidate(scene_id="a", rank=1, score=0.50),  # Lower absolute scores
                Candidate(scene_id="c", rank=2, score=0.40),
            ],
        }

        weights = {
            "dense_transcript": 0.50,
            "dense_visual": 0.50,
        }

        result = multi_channel_minmax_fuse(
            channel_candidates=channels,
            channel_weights=weights,
            top_k=10,
            include_debug=True,
        )

        # Find "a" in results
        result_a = next(r for r in result if r.scene_id == "a")

        # Check that both channels contributed normalized scores
        # transcript: (0.90 - 0.80) / (0.90 - 0.80) = 1.0
        # visual: (0.50 - 0.40) / (0.50 - 0.40) = 1.0
        # Final: 0.50 * 1.0 + 0.50 * 1.0 = 1.0
        assert result_a.score == pytest.approx(1.0, abs=0.01)


class TestMultiChannelRRFFusion:
    """Tests for multi_channel_rrf_fuse (v3-multi Option B with RRF)."""

    def test_basic_multi_channel_rrf(self):
        """Basic RRF fusion with multiple channels."""
        channels = {
            "dense_transcript": [
                Candidate(scene_id="a", rank=1, score=0.95),
                Candidate(scene_id="b", rank=2, score=0.85),
            ],
            "dense_visual": [
                Candidate(scene_id="b", rank=1, score=0.90),
                Candidate(scene_id="c", rank=2, score=0.80),
            ],
            "lexical": [
                Candidate(scene_id="a", rank=1, score=25.0),
            ],
        }

        result = multi_channel_rrf_fuse(
            channel_candidates=channels,
            k=60,
            top_k=10,
            include_debug=False,
        )

        # Should return union of all scenes
        scene_ids = {r.scene_id for r in result}
        assert scene_ids == {"a", "b", "c"}

        # All should have MULTI_DENSE_RRF score type
        assert all(r.score_type == ScoreType.MULTI_DENSE_RRF for r in result)

        # "a" appears in transcript (rank 1) and lexical (rank 1)
        # "b" appears in transcript (rank 2) and visual (rank 1)
        # "a" and "b" should rank highest
        assert result[0].scene_id in ["a", "b"]

    def test_rrf_handles_empty_channels_gracefully(self):
        """RRF should handle empty channels gracefully."""
        channels = {
            "dense_transcript": [Candidate(scene_id="a", rank=1, score=0.95)],
            "dense_visual": [],  # Empty
            "lexical": [Candidate(scene_id="b", rank=1, score=25.0)],
        }

        result = multi_channel_rrf_fuse(
            channel_candidates=channels,
            k=60,
            top_k=10,
        )

        assert len(result) == 2
        scene_ids = {r.scene_id for r in result}
        assert scene_ids == {"a", "b"}

    def test_rrf_k_parameter_effect(self):
        """Higher k should flatten score differences."""
        channels = {
            "dense_transcript": [
                Candidate(scene_id="first", rank=1, score=0.99),
                Candidate(scene_id="tenth", rank=10, score=0.70),
            ],
        }

        result_low_k = multi_channel_rrf_fuse(channels, k=1, top_k=10)
        result_high_k = multi_channel_rrf_fuse(channels, k=100, top_k=10)

        # Low k should have bigger score difference
        score_diff_low_k = result_low_k[0].score - result_low_k[1].score
        score_diff_high_k = result_high_k[0].score - result_high_k[1].score

        assert score_diff_low_k > score_diff_high_k

    def test_rrf_debug_includes_channel_scores(self):
        """Debug mode should include per-channel rank information."""
        channels = {
            "dense_transcript": [Candidate(scene_id="a", rank=1, score=0.95)],
            "lexical": [Candidate(scene_id="a", rank=2, score=20.0)],
        }

        result = multi_channel_rrf_fuse(
            channel_candidates=channels,
            k=60,
            top_k=10,
            include_debug=True,
        )

        assert result[0].channel_scores is not None
        assert "dense_transcript" in result[0].channel_scores
        assert "lexical" in result[0].channel_scores
        assert result[0].channel_scores["dense_transcript"]["rank"] == 1
        assert result[0].channel_scores["lexical"]["rank"] == 2


class TestMultiChannelTenancyInvariants:
    """Tests to ensure multi-channel fusion preserves tenancy safety."""

    def test_fusion_does_not_leak_scene_ids(self):
        """Fusion should only return scene IDs present in input channels."""
        channels = {
            "dense_transcript": [
                Candidate(scene_id="user_a_scene_1", rank=1, score=0.95),
            ],
            "lexical": [
                Candidate(scene_id="user_a_scene_2", rank=1, score=25.0),
            ],
        }

        weights = {
            "dense_transcript": 0.70,
            "lexical": 0.30,
        }

        result = multi_channel_minmax_fuse(
            channel_candidates=channels,
            channel_weights=weights,
            top_k=10,
        )

        # Should only return scenes from input
        result_scene_ids = {r.scene_id for r in result}
        assert result_scene_ids == {"user_a_scene_1", "user_a_scene_2"}

        # Should NOT introduce any new scene IDs
        input_scene_ids = set()
        for candidates in channels.values():
            input_scene_ids.update(c.scene_id for c in candidates)

        assert result_scene_ids.issubset(input_scene_ids)
