"""Unit tests for lookup fallback absolute display score calibration.

These tests verify the new absolute display score calibration logic for
lookup fallback cases (lexical_hits=0).

Run in Docker:
    docker-compose run --rm api pytest tests/unit/test_lookup_fallback_display.py -v
"""

import pytest
from src.routes.search import _build_raw_dense_by_id, _compute_best_guess_display_scores
from src.domain.search.fusion import Candidate, FusedCandidate, ScoreType


class TestBuildRawDenseById:
    """Tests for _build_raw_dense_by_id helper function."""

    def test_single_channel_single_scene(self):
        """Test with single dense channel and single scene."""
        channel_candidates = {
            "transcript": [
                Candidate(scene_id="scene_1", rank=1, score=0.85),
            ],
        }

        raw_dense_by_id = _build_raw_dense_by_id(channel_candidates)

        assert len(raw_dense_by_id) == 1
        assert raw_dense_by_id["scene_1"] == 0.85

    def test_multiple_channels_takes_max(self):
        """Test that max similarity is taken across channels."""
        channel_candidates = {
            "transcript": [
                Candidate(scene_id="scene_1", rank=1, score=0.75),
            ],
            "visual": [
                Candidate(scene_id="scene_1", rank=1, score=0.90),  # Higher
            ],
            "summary": [
                Candidate(scene_id="scene_1", rank=1, score=0.60),
            ],
        }

        raw_dense_by_id = _build_raw_dense_by_id(channel_candidates)

        assert raw_dense_by_id["scene_1"] == 0.90  # Should take max

    def test_lexical_channel_ignored(self):
        """Test that lexical channel is ignored (BM25 scores not cosine sim)."""
        channel_candidates = {
            "transcript": [
                Candidate(scene_id="scene_1", rank=1, score=0.75),
            ],
            "lexical": [
                Candidate(scene_id="scene_1", rank=1, score=25.5),  # BM25 score
            ],
        }

        raw_dense_by_id = _build_raw_dense_by_id(channel_candidates)

        assert raw_dense_by_id["scene_1"] == 0.75  # Should ignore lexical

    def test_multiple_scenes(self):
        """Test with multiple scenes across channels."""
        channel_candidates = {
            "transcript": [
                Candidate(scene_id="scene_1", rank=1, score=0.85),
                Candidate(scene_id="scene_2", rank=2, score=0.70),
            ],
            "visual": [
                Candidate(scene_id="scene_2", rank=1, score=0.80),  # Higher for scene_2
                Candidate(scene_id="scene_3", rank=2, score=0.60),
            ],
        }

        raw_dense_by_id = _build_raw_dense_by_id(channel_candidates)

        assert len(raw_dense_by_id) == 3
        assert raw_dense_by_id["scene_1"] == 0.85  # Only transcript
        assert raw_dense_by_id["scene_2"] == 0.80  # Max of 0.70 and 0.80
        assert raw_dense_by_id["scene_3"] == 0.60  # Only visual

    def test_empty_channels(self):
        """Test with empty channel candidates."""
        channel_candidates = {
            "transcript": [],
            "visual": [],
            "summary": [],
        }

        raw_dense_by_id = _build_raw_dense_by_id(channel_candidates)

        assert len(raw_dense_by_id) == 0


class TestComputeBestGuessDisplayScores:
    """Tests for _compute_best_guess_display_scores helper function."""

    def test_linear_mapping_basic(self):
        """Test basic linear mapping from [floor, ceil] to [0, cap]."""
        fused_results = [
            FusedCandidate(
                scene_id="scene_1",
                score=1.0,  # Fused score (not used)
                score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN,
            ),
        ]
        raw_dense_by_id = {
            "scene_1": 0.30,  # Mid-range between 0.20 and 0.55
        }

        display_scores = _compute_best_guess_display_scores(
            fused_results=fused_results,
            raw_dense_by_id=raw_dense_by_id,
            floor=0.20,
            ceil=0.55,
            cap=0.65,
        )

        # 0.30 is at (0.30 - 0.20) / (0.55 - 0.20) = 0.10 / 0.35 = ~0.286
        # 0.286 * 0.65 = ~0.186
        assert "scene_1" in display_scores
        assert 0.18 < display_scores["scene_1"] < 0.20

    def test_below_floor_clamps_to_zero(self):
        """Test that abs_sim below floor clamps to 0."""
        fused_results = [
            FusedCandidate(
                scene_id="scene_1",
                score=1.0,
                score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN,
            ),
        ]
        raw_dense_by_id = {
            "scene_1": 0.10,  # Below floor of 0.20
        }

        display_scores = _compute_best_guess_display_scores(
            fused_results=fused_results,
            raw_dense_by_id=raw_dense_by_id,
            floor=0.20,
            ceil=0.55,
            cap=0.65,
        )

        assert display_scores["scene_1"] == 0.0

    def test_above_ceil_clamps_to_cap(self):
        """Test that abs_sim above ceil clamps to cap."""
        fused_results = [
            FusedCandidate(
                scene_id="scene_1",
                score=1.0,
                score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN,
            ),
        ]
        raw_dense_by_id = {
            "scene_1": 0.80,  # Above ceil of 0.55
        }

        display_scores = _compute_best_guess_display_scores(
            fused_results=fused_results,
            raw_dense_by_id=raw_dense_by_id,
            floor=0.20,
            ceil=0.55,
            cap=0.65,
        )

        assert display_scores["scene_1"] == 0.65  # Capped at cap

    def test_at_floor(self):
        """Test abs_sim exactly at floor."""
        fused_results = [
            FusedCandidate(
                scene_id="scene_1",
                score=1.0,
                score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN,
            ),
        ]
        raw_dense_by_id = {
            "scene_1": 0.20,  # Exactly at floor
        }

        display_scores = _compute_best_guess_display_scores(
            fused_results=fused_results,
            raw_dense_by_id=raw_dense_by_id,
            floor=0.20,
            ceil=0.55,
            cap=0.65,
        )

        # At floor -> normalized = 0 -> display = 0
        assert display_scores["scene_1"] == 0.0

    def test_at_ceil(self):
        """Test abs_sim exactly at ceil."""
        fused_results = [
            FusedCandidate(
                scene_id="scene_1",
                score=1.0,
                score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN,
            ),
        ]
        raw_dense_by_id = {
            "scene_1": 0.55,  # Exactly at ceil
        }

        display_scores = _compute_best_guess_display_scores(
            fused_results=fused_results,
            raw_dense_by_id=raw_dense_by_id,
            floor=0.20,
            ceil=0.55,
            cap=0.65,
        )

        # At ceil -> normalized = 1 -> display = cap
        assert display_scores["scene_1"] == 0.65

    def test_monotonicity(self):
        """Test that higher abs_sim produces higher display_score."""
        fused_results = [
            FusedCandidate(scene_id="scene_1", score=1.0, score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN),
            FusedCandidate(scene_id="scene_2", score=1.0, score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN),
            FusedCandidate(scene_id="scene_3", score=1.0, score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN),
        ]
        raw_dense_by_id = {
            "scene_1": 0.30,
            "scene_2": 0.40,
            "scene_3": 0.50,
        }

        display_scores = _compute_best_guess_display_scores(
            fused_results=fused_results,
            raw_dense_by_id=raw_dense_by_id,
            floor=0.20,
            ceil=0.55,
            cap=0.65,
        )

        # Should be monotonically increasing
        assert display_scores["scene_1"] < display_scores["scene_2"]
        assert display_scores["scene_2"] < display_scores["scene_3"]

    def test_missing_scene_defaults_to_zero(self):
        """Test that scenes not in raw_dense_by_id get display_score=0."""
        fused_results = [
            FusedCandidate(
                scene_id="scene_unknown",
                score=1.0,
                score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN,
            ),
        ]
        raw_dense_by_id = {}  # Empty

        display_scores = _compute_best_guess_display_scores(
            fused_results=fused_results,
            raw_dense_by_id=raw_dense_by_id,
            floor=0.20,
            ceil=0.55,
            cap=0.65,
        )

        assert display_scores["scene_unknown"] == 0.0

    def test_cap_enforced(self):
        """Test that all display scores are <= cap."""
        fused_results = [
            FusedCandidate(scene_id="scene_1", score=1.0, score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN),
            FusedCandidate(scene_id="scene_2", score=1.0, score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN),
            FusedCandidate(scene_id="scene_3", score=1.0, score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN),
        ]
        raw_dense_by_id = {
            "scene_1": 0.25,
            "scene_2": 0.45,
            "scene_3": 0.90,  # Way above ceil
        }

        cap = 0.65
        display_scores = _compute_best_guess_display_scores(
            fused_results=fused_results,
            raw_dense_by_id=raw_dense_by_id,
            floor=0.20,
            ceil=0.55,
            cap=cap,
        )

        for scene_id, score in display_scores.items():
            assert score <= cap, f"Display score for {scene_id} exceeds cap: {score} > {cap}"

    def test_realistic_scenario(self):
        """Test realistic scenario from bug report (abs_sim ~0.33 should not show as ~95%)."""
        fused_results = [
            FusedCandidate(
                scene_id="scene_1",
                score=0.98,  # High fused score (min-max normalized)
                score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN,
            ),
        ]
        raw_dense_by_id = {
            "scene_1": 0.33,  # Weak absolute similarity
        }

        display_scores = _compute_best_guess_display_scores(
            fused_results=fused_results,
            raw_dense_by_id=raw_dense_by_id,
            floor=0.20,
            ceil=0.55,
            cap=0.65,
        )

        # With abs_sim=0.33:
        # normalized = (0.33 - 0.20) / (0.55 - 0.20) = 0.13 / 0.35 = 0.371
        # display = 0.371 * 0.65 = 0.241
        assert display_scores["scene_1"] < 0.30  # Should be much lower than 0.95
        assert 0.20 < display_scores["scene_1"] < 0.30
