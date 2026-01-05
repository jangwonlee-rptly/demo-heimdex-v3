"""Unit tests for display score calibration."""
import pytest
from src.domain.search.display_score import (
    calibrate_display_scores,
    get_neutral_display_score,
    _calibrate_exp_squash,
    _calibrate_pctl_ceiling,
)


class TestCalibrateDisplayScores:
    """Test suite for display score calibration functions."""

    def test_empty_list(self):
        """Empty list should return empty list."""
        result = calibrate_display_scores([], method="exp_squash")
        assert result == []

    def test_single_score_neutral(self):
        """Single score should return neutral value (capped)."""
        result = calibrate_display_scores([0.85], method="exp_squash", max_cap=0.97)
        assert len(result) == 1
        # Should be neutral (~0.5) capped at max_cap
        assert result[0] == pytest.approx(0.5, abs=0.05)
        assert result[0] <= 0.97

    def test_flat_distribution_all_equal(self):
        """Flat distribution (all equal) should return neutral values."""
        scores = [0.75, 0.75, 0.75, 0.75]
        result = calibrate_display_scores(scores, method="exp_squash", max_cap=0.97)
        assert len(result) == 4
        # All should be equal and neutral
        assert all(r == pytest.approx(0.5, abs=0.05) for r in result)
        assert all(r <= 0.97 for r in result)

    def test_monotonic_increasing(self):
        """If score_a > score_b, then calibrated(a) >= calibrated(b)."""
        scores = [0.92, 0.85, 0.78, 0.65, 0.52, 0.40]
        result = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)

        # Check monotonicity
        for i in range(len(result) - 1):
            assert result[i] >= result[i + 1], f"Monotonicity violated at index {i}: {result}"

    def test_extremes_min_near_zero(self):
        """Minimum score should map near 0."""
        scores = [0.95, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35]
        result = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)

        # Min score should be close to 0
        assert result[-1] < 0.15, f"Minimum score should be near 0, got {result[-1]}"

    def test_extremes_max_near_cap(self):
        """Maximum score should map near max_cap (not 1.0)."""
        scores = [0.95, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35]
        result = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)

        # Max score should be close to max_cap
        assert result[0] >= 0.85, f"Maximum score should be near max_cap, got {result[0]}"
        assert result[0] <= 0.97, f"Maximum score should not exceed max_cap, got {result[0]}"

    def test_never_reaches_100(self):
        """Even perfect scores should be capped below 1.0."""
        scores = [1.0, 0.98, 0.95, 0.92]
        result = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)

        # No score should reach 1.0
        assert all(r < 1.0 for r in result), f"Scores should never reach 1.0: {result}"
        assert all(r <= 0.97 for r in result), f"Scores should not exceed max_cap: {result}"

    def test_alpha_tuning_aggressive(self):
        """Higher alpha should produce more aggressive squashing."""
        scores = [0.92, 0.85, 0.78, 0.65]

        result_gentle = calibrate_display_scores(scores, method="exp_squash", alpha=2.0, max_cap=0.97)
        result_aggressive = calibrate_display_scores(scores, method="exp_squash", alpha=5.0, max_cap=0.97)

        # Higher alpha should push top scores closer to max_cap
        assert result_aggressive[0] >= result_gentle[0], "Higher alpha should increase top score"

    def test_pctl_ceiling_method(self):
        """Percentile ceiling method should work correctly."""
        scores = [0.95, 0.88, 0.82, 0.75, 0.68, 0.60, 0.52, 0.45, 0.38, 0.30]
        result = calibrate_display_scores(scores, method="pctl_ceiling", max_cap=0.97)

        assert len(result) == len(scores)
        # Should preserve monotonicity
        for i in range(len(result) - 1):
            assert result[i] >= result[i + 1], f"Monotonicity violated: {result}"
        # Should be bounded
        assert all(0.0 <= r <= 0.97 for r in result)

    def test_unknown_method_raises_error(self):
        """Unknown method should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown calibration method"):
            calibrate_display_scores([0.5], method="unknown_method")

    def test_typical_search_results(self):
        """Test with typical search result scores (fused minmax_mean)."""
        # Simulate scores from minmax fusion where top result got 1.0
        scores = [1.0, 0.92, 0.85, 0.78, 0.71, 0.65, 0.58, 0.52, 0.45, 0.38]
        result = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)

        # Top score should be < 1.0 (avoiding 100% display)
        assert result[0] < 1.0, "Top score should not be 1.0"
        assert result[0] >= 0.90, "Top score should still be high"

        # Scores should be well-distributed
        assert result[0] - result[-1] >= 0.5, "Should have good score spread"


class TestExpSquash:
    """Test suite for exponential squashing calibration."""

    def test_basic_squashing(self):
        """Test basic exponential squashing behavior."""
        scores = [0.9, 0.7, 0.5, 0.3]
        result = _calibrate_exp_squash(scores, eps=1e-9, max_cap=0.97, alpha=3.0)

        assert len(result) == 4
        # Should be monotonic
        assert result[0] >= result[1] >= result[2] >= result[3]
        # Should be bounded
        assert all(0.0 <= r <= 0.97 for r in result)

    def test_zero_variance_handling(self):
        """Test handling of zero-variance (flat) distributions."""
        scores = [0.5, 0.5, 0.5]
        result = _calibrate_exp_squash(scores, eps=1e-9, max_cap=0.97, alpha=3.0)

        # All should be neutral
        assert all(r == pytest.approx(0.5, abs=0.01) for r in result)


class TestPctlCeiling:
    """Test suite for percentile ceiling calibration."""

    def test_basic_percentile_ceiling(self):
        """Test basic percentile ceiling behavior."""
        scores = [0.95, 0.88, 0.82, 0.75, 0.68, 0.60, 0.52, 0.45, 0.38, 0.30]
        result = _calibrate_pctl_ceiling(scores, eps=1e-9, max_cap=0.97, pctl=0.90)

        assert len(result) == 10
        # Should be monotonic
        for i in range(len(result) - 1):
            assert result[i] >= result[i + 1]
        # Should be bounded
        assert all(0.0 <= r <= 0.97 for r in result)

    def test_percentile_prevents_100(self):
        """Percentile ceiling should prevent top score from reaching 1.0."""
        scores = [1.0, 0.95, 0.90, 0.85, 0.80]
        result = _calibrate_pctl_ceiling(scores, eps=1e-9, max_cap=0.97, pctl=0.90)

        # Top score should be capped below 1.0
        assert result[0] < 1.0
        assert result[0] <= 0.97


class TestGetNeutralDisplayScore:
    """Test suite for neutral display score utility."""

    def test_neutral_default(self):
        """Neutral score should be 0.5 by default."""
        neutral = get_neutral_display_score(max_cap=0.97)
        assert neutral == 0.5

    def test_neutral_respects_cap(self):
        """Neutral score should respect low max_cap."""
        neutral = get_neutral_display_score(max_cap=0.3)
        assert neutral == 0.3


class TestRankingPreservation:
    """Test suite to verify ranking order is always preserved."""

    def test_ranking_preserved_across_methods(self):
        """Verify both methods preserve ranking order."""
        scores = [0.95, 0.88, 0.82, 0.75, 0.68, 0.60, 0.52]

        result_exp = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)
        result_pctl = calibrate_display_scores(scores, method="pctl_ceiling", max_cap=0.97)

        # Both should preserve strict descending order
        for i in range(len(result_exp) - 1):
            assert result_exp[i] >= result_exp[i + 1], f"exp_squash broke ranking at {i}"
        for i in range(len(result_pctl) - 1):
            assert result_pctl[i] >= result_pctl[i + 1], f"pctl_ceiling broke ranking at {i}"

    def test_ranking_preserved_with_ties(self):
        """Ties in input should produce ties in output."""
        scores = [0.85, 0.85, 0.70, 0.70, 0.55]
        result = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)

        # Ties should be preserved
        assert result[0] == pytest.approx(result[1], abs=1e-9), "First tie broken"
        assert result[2] == pytest.approx(result[3], abs=1e-9), "Second tie broken"


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_very_small_range(self):
        """Small score range should still work."""
        scores = [0.801, 0.800, 0.799, 0.798]
        result = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)

        # Should still be monotonic
        for i in range(len(result) - 1):
            assert result[i] >= result[i + 1]

    def test_very_large_range(self):
        """Large score range should still work."""
        scores = [1.0, 0.9, 0.5, 0.1, 0.01]
        result = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)

        # Should have good spread
        assert result[0] - result[-1] > 0.6

    def test_negative_scores_clamped(self):
        """Negative scores should be clamped to 0."""
        scores = [0.5, 0.0, -0.1]  # Shouldn't happen in practice, but test safety
        result = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)

        # All should be >= 0
        assert all(r >= 0.0 for r in result)

    def test_scores_above_one_clamped(self):
        """Scores above 1.0 should be handled gracefully."""
        scores = [1.2, 1.0, 0.9, 0.8]  # Shouldn't happen in minmax fusion
        result = calibrate_display_scores(scores, method="exp_squash", alpha=3.0, max_cap=0.97)

        # All should be <= max_cap
        assert all(r <= 0.97 for r in result)
