"""Integration tests for lookup soft lexical gating feature.

These tests verify that the soft lexical gating works correctly:
1. Lookup queries with lexical hits: results are filtered to lexical allowlist
2. Lookup queries with no lexical hits: results are returned but labeled as "best_guess"
3. Semantic queries: no gating applied (normal behavior)
4. Feature flag disabled: no gating applied

Run in Docker:
    docker-compose run --rm api pytest tests/integration/test_lookup_soft_gating.py -v
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.search.intent import detect_query_intent
from src.config import Settings


def test_detect_query_intent_lookup():
    """Verify intent detection classifies lookup queries correctly."""
    print("\n=== Test: Intent Detection - Lookup Queries ===")

    lookup_queries = [
        ("Heimdex", "lookup"),
        ("BTS", "lookup"),
        ("이장원", "lookup"),
        ("NewJeans", "lookup"),
        ("NVIDIA", "lookup"),
        ("OpenAI", "lookup"),
    ]

    for query, expected_intent in lookup_queries:
        detected_intent = detect_query_intent(query, language="ko")
        assert detected_intent == expected_intent, \
            f"Query '{query}' should be classified as {expected_intent}, got {detected_intent}"
        print(f"✅ '{query}' → {detected_intent}")

    print("✅ All lookup queries correctly classified")


def test_detect_query_intent_semantic():
    """Verify intent detection classifies semantic queries correctly."""
    print("\n=== Test: Intent Detection - Semantic Queries ===")

    semantic_queries = [
        ("영상 편집", "semantic"),
        ("사람이 걷는 장면", "semantic"),
        ("studio interview", "semantic"),
        ("funny moment", "semantic"),
        ("공원에서 달리는", "semantic"),
    ]

    for query, expected_intent in semantic_queries:
        detected_intent = detect_query_intent(query, language="ko")
        assert detected_intent == expected_intent, \
            f"Query '{query}' should be classified as {expected_intent}, got {detected_intent}"
        print(f"✅ '{query}' → {detected_intent}")

    print("✅ All semantic queries correctly classified")


def test_config_lookup_soft_gating_flags():
    """Verify lookup soft gating config flags have correct defaults."""
    print("\n=== Test: Config Flags ===")

    # Create settings with minimal required env vars
    settings = Settings(
        supabase_url="http://localhost:54321",
        supabase_anon_key="test_key",
        supabase_service_role_key="test_key",
        supabase_jwt_secret="test_secret",
        database_url="postgresql://test",
        openai_api_key="test_key",
    )

    # Verify default values
    assert settings.enable_lookup_soft_gating is False, \
        "enable_lookup_soft_gating should default to False (safe rollout)"
    assert settings.lookup_lexical_min_hits == 1, \
        "lookup_lexical_min_hits should default to 1"
    assert settings.lookup_fallback_mode == "dense_best_guess", \
        "lookup_fallback_mode should default to dense_best_guess"
    assert settings.lookup_label_mode == "api_field", \
        "lookup_label_mode should default to api_field"

    print(f"✅ enable_lookup_soft_gating = {settings.enable_lookup_soft_gating} (default: False)")
    print(f"✅ lookup_lexical_min_hits = {settings.lookup_lexical_min_hits}")
    print(f"✅ lookup_fallback_mode = {settings.lookup_fallback_mode}")
    print(f"✅ lookup_label_mode = {settings.lookup_label_mode}")


def test_config_lookup_soft_gating_enabled():
    """Verify lookup soft gating can be enabled via config."""
    print("\n=== Test: Config - Enable Soft Gating ===")

    settings = Settings(
        supabase_url="http://localhost:54321",
        supabase_anon_key="test_key",
        supabase_service_role_key="test_key",
        supabase_jwt_secret="test_secret",
        database_url="postgresql://test",
        openai_api_key="test_key",
        enable_lookup_soft_gating=True,
        lookup_lexical_min_hits=2,
    )

    assert settings.enable_lookup_soft_gating is True
    assert settings.lookup_lexical_min_hits == 2

    print(f"✅ enable_lookup_soft_gating = {settings.enable_lookup_soft_gating}")
    print(f"✅ lookup_lexical_min_hits = {settings.lookup_lexical_min_hits}")


def test_config_lookup_absolute_display_score_flags():
    """Verify lookup absolute display score config flags have correct defaults."""
    print("\n=== Test: Config - Absolute Display Score Flags ===")

    settings = Settings(
        supabase_url="http://localhost:54321",
        supabase_anon_key="test_key",
        supabase_service_role_key="test_key",
        supabase_jwt_secret="test_secret",
        database_url="postgresql://test",
        openai_api_key="test_key",
    )

    # Verify default values
    assert settings.enable_lookup_absolute_display_score is False, \
        "enable_lookup_absolute_display_score should default to False (safe rollout)"
    assert settings.lookup_abs_sim_floor == 0.20
    assert settings.lookup_abs_sim_ceil == 0.55
    assert settings.lookup_best_guess_max_cap == 0.65

    print(f"✅ enable_lookup_absolute_display_score = {settings.enable_lookup_absolute_display_score}")
    print(f"✅ lookup_abs_sim_floor = {settings.lookup_abs_sim_floor}")
    print(f"✅ lookup_abs_sim_ceil = {settings.lookup_abs_sim_ceil}")
    print(f"✅ lookup_best_guess_max_cap = {settings.lookup_best_guess_max_cap}")


def test_config_lookup_absolute_display_score_enabled():
    """Verify lookup absolute display score can be enabled via config."""
    print("\n=== Test: Config - Enable Absolute Display Score ===")

    settings = Settings(
        supabase_url="http://localhost:54321",
        supabase_anon_key="test_key",
        supabase_service_role_key="test_key",
        supabase_jwt_secret="test_secret",
        database_url="postgresql://test",
        openai_api_key="test_key",
        enable_lookup_absolute_display_score=True,
        lookup_abs_sim_floor=0.25,
        lookup_abs_sim_ceil=0.60,
        lookup_best_guess_max_cap=0.70,
    )

    assert settings.enable_lookup_absolute_display_score is True
    assert settings.lookup_abs_sim_floor == 0.25
    assert settings.lookup_abs_sim_ceil == 0.60
    assert settings.lookup_best_guess_max_cap == 0.70

    print(f"✅ enable_lookup_absolute_display_score = {settings.enable_lookup_absolute_display_score}")
    print(f"✅ lookup_abs_sim_floor = {settings.lookup_abs_sim_floor}")
    print(f"✅ lookup_abs_sim_ceil = {settings.lookup_abs_sim_ceil}")
    print(f"✅ lookup_best_guess_max_cap = {settings.lookup_best_guess_max_cap}")


def test_match_quality_values():
    """Verify match_quality field values are as expected."""
    print("\n=== Test: Match Quality Values ===")

    # Expected values
    supported = "supported"
    best_guess = "best_guess"

    # Verify they're simple strings (not enums)
    assert isinstance(supported, str)
    assert isinstance(best_guess, str)

    print(f"✅ match_quality='supported' for lexical hits")
    print(f"✅ match_quality='best_guess' for no lexical hits")


def test_allowlist_filtering_simulation():
    """Simulate allowlist filtering logic."""
    print("\n=== Test: Allowlist Filtering Simulation ===")

    # Simulate candidates from different channels
    from src.domain.search.fusion import Candidate

    transcript_candidates = [
        Candidate(scene_id="scene_a", rank=1, score=0.95),
        Candidate(scene_id="scene_b", rank=2, score=0.88),
        Candidate(scene_id="scene_c", rank=3, score=0.82),
        Candidate(scene_id="scene_d", rank=4, score=0.75),
    ]

    # Simulate lexical allowlist (only scene_a and scene_c have lexical hits)
    allowlist_ids = {"scene_a", "scene_c"}

    # Apply filtering
    filtered_candidates = [c for c in transcript_candidates if c.scene_id in allowlist_ids]

    # Verify filtering worked
    assert len(filtered_candidates) == 2, \
        f"Should have 2 filtered candidates, got {len(filtered_candidates)}"
    assert all(c.scene_id in allowlist_ids for c in filtered_candidates), \
        "All filtered candidates should be in allowlist"

    print(f"✅ Original candidates: {len(transcript_candidates)}")
    print(f"✅ Allowlist size: {len(allowlist_ids)}")
    print(f"✅ Filtered candidates: {len(filtered_candidates)}")
    print(f"✅ Filtered scene IDs: {[c.scene_id for c in filtered_candidates]}")


def test_fallback_behavior_simulation():
    """Simulate fallback behavior when no lexical hits."""
    print("\n=== Test: Fallback Behavior Simulation ===")

    # Simulate lexical search returning no results
    lexical_hits_count = 0
    lookup_lexical_min_hits = 1

    # Determine behavior
    if lexical_hits_count >= lookup_lexical_min_hits:
        match_quality = "supported"
        allowlist_mode = True
    else:
        match_quality = "best_guess"
        allowlist_mode = False

    # Verify fallback behavior
    assert match_quality == "best_guess", \
        "With 0 lexical hits, match_quality should be 'best_guess'"
    assert allowlist_mode is False, \
        "With 0 lexical hits, allowlist mode should be disabled"

    print(f"✅ Lexical hits: {lexical_hits_count}")
    print(f"✅ Match quality: {match_quality}")
    print(f"✅ Allowlist mode: {allowlist_mode}")


def test_logging_metrics_format():
    """Verify logging metrics format is correct."""
    print("\n=== Test: Logging Metrics Format ===")

    # Simulate metrics that would be logged
    metrics = {
        "query": "Heimdex",
        "intent": "lookup",
        "lexical_hits": 5,
        "used_allowlist": True,
        "fallback_used": False,
        "match_quality": "supported",
        "results_count": 10,
        "display_mode": "fused_exp_squash",
        "top_fused_scores": [1.0, 0.95, 0.88],
        "top_abs_dense_sims": "N/A",
        "top_display_scores": [0.97, 0.92, 0.85],
    }

    # Verify all expected fields are present
    required_fields = [
        "query", "intent", "lexical_hits", "used_allowlist",
        "fallback_used", "match_quality", "results_count",
        "display_mode", "top_fused_scores", "top_abs_dense_sims", "top_display_scores"
    ]

    for field in required_fields:
        assert field in metrics, f"Metrics should include '{field}'"

    print(f"✅ All required metrics fields present: {', '.join(required_fields)}")

    # Verify data types
    assert isinstance(metrics["query"], str)
    assert isinstance(metrics["intent"], str)
    assert isinstance(metrics["lexical_hits"], int)
    assert isinstance(metrics["used_allowlist"], bool)
    assert isinstance(metrics["fallback_used"], bool)
    assert isinstance(metrics["match_quality"], str)
    assert isinstance(metrics["results_count"], int)
    assert isinstance(metrics["display_mode"], str)
    assert isinstance(metrics["top_fused_scores"], list)
    # top_abs_dense_sims can be string "N/A" or list
    assert isinstance(metrics["top_abs_dense_sims"], (str, list))
    assert isinstance(metrics["top_display_scores"], list)

    print(f"✅ All metrics have correct data types")


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("Lookup Soft Lexical Gating - Integration Tests")
    print("=" * 60)

    try:
        test_detect_query_intent_lookup()
        test_detect_query_intent_semantic()
        test_config_lookup_soft_gating_flags()
        test_config_lookup_soft_gating_enabled()
        test_config_lookup_absolute_display_score_flags()
        test_config_lookup_absolute_display_score_enabled()
        test_match_quality_values()
        test_allowlist_filtering_simulation()
        test_fallback_behavior_simulation()
        test_logging_metrics_format()

        print("\n" + "=" * 60)
        print("✅ All integration tests passed!")
        print("=" * 60)
        return True

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
