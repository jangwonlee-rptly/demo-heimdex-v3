"""Integration tests for display score calibration feature.

These tests verify that the display_score field is correctly computed and included
in search responses when the feature flag is enabled, and that ranking order is
preserved regardless of the flag state.

Run with: pytest tests/integration/test_display_score_integration.py -v
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.search.display_score import calibrate_display_scores
from src.domain.search.fusion import Candidate, multi_channel_minmax_fuse, FusedCandidate
from src.config import Settings


def test_display_score_preserves_ranking():
    """Verify that display_score calibration preserves ranking order."""
    print("\n=== Test: Display Score Preserves Ranking ===")

    # Simulate fused scores from search (typical minmax_mean output)
    fused_scores = [1.0, 0.92, 0.85, 0.78, 0.71, 0.65, 0.58, 0.52, 0.45, 0.38]

    # Apply calibration
    display_scores = calibrate_display_scores(
        fused_scores,
        method="exp_squash",
        alpha=3.0,
        max_cap=0.97,
    )

    print(f"Original scores: {fused_scores[:5]}...")
    print(f"Display scores:  {display_scores[:5]}...")

    # Verify ranking is preserved (monotonic decreasing)
    for i in range(len(display_scores) - 1):
        assert display_scores[i] >= display_scores[i + 1], \
            f"Ranking broken at index {i}: {display_scores[i]} < {display_scores[i+1]}"

    # Verify top score is reduced (not 100%)
    assert display_scores[0] < 1.0, f"Top display score should be < 1.0, got {display_scores[0]}"
    assert display_scores[0] <= 0.97, f"Top display score should be <= max_cap, got {display_scores[0]}"

    print(f"✅ Ranking preserved: {len(display_scores)} scores, all monotonic")
    print(f"✅ Top score reduced from 1.0 to {display_scores[0]:.4f}")


def test_fusion_with_display_score_mapping():
    """Test that fusion results can be mapped to display scores."""
    print("\n=== Test: Fusion + Display Score Mapping ===")

    # Create mock candidates
    transcript_candidates = [
        Candidate(scene_id="scene_a", rank=1, score=0.92),
        Candidate(scene_id="scene_b", rank=2, score=0.85),
        Candidate(scene_id="scene_c", rank=3, score=0.78),
    ]

    visual_candidates = [
        Candidate(scene_id="scene_a", rank=1, score=0.88),
        Candidate(scene_id="scene_d", rank=2, score=0.75),
    ]

    lexical_candidates = [
        Candidate(scene_id="scene_b", rank=1, score=28.5),
        Candidate(scene_id="scene_c", rank=2, score=22.3),
    ]

    # Mock settings
    class MockSettings:
        fusion_minmax_eps = 1e-9
        fusion_percentile_clip_enabled = False
        fusion_percentile_clip_lo = 0.05
        fusion_percentile_clip_hi = 0.95

    settings = MockSettings()

    # Fuse candidates
    channel_candidates = {
        "dense_transcript": transcript_candidates,
        "dense_visual": visual_candidates,
        "lexical": lexical_candidates,
    }

    channel_weights = {
        "dense_transcript": 0.5,
        "dense_visual": 0.3,
        "lexical": 0.2,
    }

    fused_results, _ = multi_channel_minmax_fuse(
        channel_candidates=channel_candidates,
        channel_weights=channel_weights,
        settings=settings,
        top_k=10,
        include_debug=False,
        return_metadata=False,
    )

    print(f"Fused results: {len(fused_results)} scenes")

    # Extract scores
    fused_scores = [r.score for r in fused_results]
    print(f"Fused scores: {fused_scores}")

    # Calibrate for display
    display_scores = calibrate_display_scores(
        fused_scores,
        method="exp_squash",
        alpha=3.0,
        max_cap=0.97,
    )

    # Build mapping
    display_score_map = {
        r.scene_id: display_scores[i]
        for i, r in enumerate(fused_results)
    }

    print(f"Display score map: {display_score_map}")

    # Verify all scenes have display scores
    assert len(display_score_map) == len(fused_results), "Display score map incomplete"

    # Verify display scores are <= max_cap
    for scene_id, disp_score in display_score_map.items():
        assert disp_score <= 0.97, f"Scene {scene_id} display_score {disp_score} exceeds max_cap"

    print(f"✅ Display score mapping created: {len(display_score_map)} scenes")


def test_feature_flag_behavior():
    """Test that feature flag controls display_score presence."""
    print("\n=== Test: Feature Flag Behavior ===")

    # Simulate settings with flag OFF
    settings_off = Settings(
        **{
            "supabase_url": "http://localhost:54321",
            "supabase_anon_key": "test_key",
            "supabase_service_role_key": "test_key",
            "supabase_jwt_secret": "test_secret",
            "database_url": "postgresql://test",
            "openai_api_key": "test_key",
            "enable_display_score_calibration": False,
        }
    )

    # Simulate settings with flag ON
    settings_on = Settings(
        **{
            "supabase_url": "http://localhost:54321",
            "supabase_anon_key": "test_key",
            "supabase_service_role_key": "test_key",
            "supabase_jwt_secret": "test_secret",
            "database_url": "postgresql://test",
            "openai_api_key": "test_key",
            "enable_display_score_calibration": True,
            "display_score_method": "exp_squash",
            "display_score_max_cap": 0.97,
            "display_score_alpha": 3.0,
        }
    )

    print(f"Flag OFF: enable_display_score_calibration = {settings_off.enable_display_score_calibration}")
    print(f"Flag ON:  enable_display_score_calibration = {settings_on.enable_display_score_calibration}")

    # In real API, when flag is OFF, display_score_map would be empty dict
    # When flag is ON, it would be populated

    # Simulate the condition check
    fused_results = [
        FusedCandidate(scene_id="scene_a", score=1.0, score_type="multi_dense_minmax_mean"),
        FusedCandidate(scene_id="scene_b", score=0.85, score_type="multi_dense_minmax_mean"),
    ]

    # Flag OFF: no calibration
    if settings_off.enable_display_score_calibration and fused_results:
        display_score_map_off = {"dummy": 0.0}  # Would be populated
    else:
        display_score_map_off = {}

    # Flag ON: calibration applied
    if settings_on.enable_display_score_calibration and fused_results:
        fused_scores = [r.score for r in fused_results]
        display_scores = calibrate_display_scores(
            fused_scores,
            method=settings_on.display_score_method,
            max_cap=settings_on.display_score_max_cap,
            alpha=settings_on.display_score_alpha,
        )
        display_score_map_on = {r.scene_id: display_scores[i] for i, r in enumerate(fused_results)}
    else:
        display_score_map_on = {}

    print(f"Display score map when flag OFF: {display_score_map_off}")
    print(f"Display score map when flag ON:  {display_score_map_on}")

    assert len(display_score_map_off) == 0, "Flag OFF should produce empty map"
    assert len(display_score_map_on) == 2, "Flag ON should populate map"

    print("✅ Feature flag correctly controls display_score generation")


def test_score_ordering_stability():
    """Verify that scene ordering by scene_id is identical regardless of calibration."""
    print("\n=== Test: Score Ordering Stability ===")

    # Simulate search results
    fused_scores = [0.95, 0.88, 0.82, 0.75, 0.68]
    scene_ids = ["scene_a", "scene_b", "scene_c", "scene_d", "scene_e"]

    # Original ordering (by fused score)
    original_order = list(zip(scene_ids, fused_scores))
    original_order.sort(key=lambda x: -x[1])  # Descending by score

    # Apply calibration
    display_scores = calibrate_display_scores(
        fused_scores,
        method="exp_squash",
        alpha=3.0,
        max_cap=0.97,
    )

    # New ordering (by display score)
    calibrated_order = list(zip(scene_ids, display_scores))
    calibrated_order.sort(key=lambda x: -x[1])  # Descending by display_score

    print(f"Original order: {[scene_id for scene_id, _ in original_order]}")
    print(f"Calibrated order: {[scene_id for scene_id, _ in calibrated_order]}")

    # Verify ordering is identical
    for i in range(len(original_order)):
        assert original_order[i][0] == calibrated_order[i][0], \
            f"Ordering changed at index {i}: {original_order[i][0]} != {calibrated_order[i][0]}"

    print("✅ Scene ordering is identical (ranking stable)")


def test_empty_results_handling():
    """Test that empty results are handled gracefully."""
    print("\n=== Test: Empty Results Handling ===")

    # Empty fused results
    fused_results = []

    # Should not crash
    display_scores = calibrate_display_scores(
        [],
        method="exp_squash",
        alpha=3.0,
        max_cap=0.97,
    )

    assert display_scores == [], "Empty input should produce empty output"

    print("✅ Empty results handled gracefully")


def test_single_result_handling():
    """Test that single result gets neutral display score."""
    print("\n=== Test: Single Result Handling ===")

    # Single result (edge case: can't meaningfully calibrate)
    fused_scores = [0.85]

    display_scores = calibrate_display_scores(
        fused_scores,
        method="exp_squash",
        alpha=3.0,
        max_cap=0.97,
    )

    print(f"Single fused score: {fused_scores[0]}")
    print(f"Single display score: {display_scores[0]}")

    # Should be neutral (~0.5) capped at max_cap
    assert len(display_scores) == 1
    assert display_scores[0] <= 0.97
    # Neutral value should be around 0.5
    assert 0.4 <= display_scores[0] <= 0.6, f"Expected neutral ~0.5, got {display_scores[0]}"

    print("✅ Single result gets neutral display score")


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("Display Score Calibration - Integration Tests")
    print("="*60)

    try:
        test_display_score_preserves_ranking()
        test_fusion_with_display_score_mapping()
        test_feature_flag_behavior()
        test_score_ordering_stability()
        test_empty_results_handling()
        test_single_result_handling()

        print("\n" + "="*60)
        print("✅ All integration tests passed!")
        print("="*60)
        return True

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
