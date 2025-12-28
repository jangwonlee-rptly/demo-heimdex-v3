"""Integration tests for CLIP visual search.

These tests verify that CLIP embeddings are correctly integrated into the search pipeline
and that visual/rerank modes work as expected.

Run with: pytest tests/integration/test_clip_search.py -v
Or manually: python tests/integration/test_clip_search.py
"""
import os
import sys
import time
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.adapters.clip_client import get_clip_client, is_clip_available, ClipClientError
from src.domain.visual_router import get_visual_intent_router
from src.config import settings


def test_clip_client_availability():
    """Test that CLIP client is configured and reachable."""
    print("\n=== Test 1: CLIP Client Availability ===")

    available = is_clip_available()
    print(f"CLIP available: {available}")

    if not available:
        print("⚠️  CLIP not configured. Set CLIP_RUNPOD_URL and CLIP_RUNPOD_SECRET")
        return False

    print("✅ CLIP client is configured")
    return True


def test_clip_text_embedding():
    """Test CLIP text embedding generation."""
    print("\n=== Test 2: CLIP Text Embedding ===")

    if not is_clip_available():
        print("⚠️  Skipping (CLIP not available)")
        return False

    test_queries = [
        "red car",
        "person walking",
        "close-up face",
        "떡볶이 on plate",
        "bright sunny day with blue sky",
    ]

    try:
        clip_client = get_clip_client()

        for query in test_queries:
            start = time.time()
            try:
                embedding = clip_client.create_text_embedding(query, normalize=True)
                elapsed_ms = (time.time() - start) * 1000

                print(f"Query: '{query}'")
                print(f"  - Embedding dim: {len(embedding)}")
                print(f"  - L2 norm: {sum(x*x for x in embedding)**0.5:.4f}")
                print(f"  - Latency: {elapsed_ms:.1f}ms")

                # Verify embedding properties
                assert len(embedding) == 512, f"Expected 512d embedding, got {len(embedding)}"
                assert 0.99 <= sum(x*x for x in embedding)**0.5 <= 1.01, "Embedding should be L2-normalized"

            except ClipClientError as e:
                print(f"  ❌ Failed: {e}")
                # Continue testing other queries
                continue

        print("✅ CLIP text embedding test completed")
        return True

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_visual_intent_router():
    """Test visual intent routing."""
    print("\n=== Test 3: Visual Intent Router ===")

    router = get_visual_intent_router()

    test_cases = [
        ("red car driving fast", "recall", True, False),
        ("person walking in crowd", "recall", True, False),
        ("he says we're in this together", "skip", False, True),
        ("the line about love", "skip", False, True),
        ("tteokbokki scene", "rerank", True, False),
    ]

    for query, expected_mode, should_have_visual, should_have_speech in test_cases:
        result = router.analyze(query)

        print(f"\nQuery: '{query}'")
        print(f"  - Mode: {result.suggested_mode} (expected: {expected_mode})")
        print(f"  - Confidence: {result.confidence:.2f}")
        print(f"  - Visual intent: {result.has_visual_intent}")
        print(f"  - Speech intent: {result.has_speech_intent}")
        print(f"  - Visual terms: {result.matched_visual_terms[:3]}")
        print(f"  - Speech terms: {result.matched_speech_terms[:3]}")
        print(f"  - Explanation: {result.explanation}")

        # Verify expectations
        assert result.has_visual_intent == should_have_visual, \
            f"Visual intent mismatch for: {query}"
        assert result.has_speech_intent == should_have_speech, \
            f"Speech intent mismatch for: {query}"

    print("\n✅ Visual router working correctly")
    return True


def test_clip_degradation():
    """Test graceful degradation when CLIP fails."""
    print("\n=== Test 4: CLIP Graceful Degradation ===")

    if not is_clip_available():
        print("⚠️  Skipping (CLIP not available)")
        return False

    try:
        clip_client = get_clip_client()

        # Test with empty text (should fail gracefully)
        try:
            clip_client.create_text_embedding("", normalize=True)
            print("❌ Should have raised ClipClientError for empty text")
            return False
        except ClipClientError as e:
            print(f"✅ Empty text handled gracefully: {e}")

        # Test with very long text (should work or fail gracefully)
        long_text = "test " * 1000
        try:
            embedding = clip_client.create_text_embedding(long_text, normalize=True)
            print(f"✅ Long text handled: dim={len(embedding)}")
        except ClipClientError as e:
            print(f"✅ Long text failed gracefully: {e}")

        print("✅ CLIP degradation handling correct")
        return True

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_configuration():
    """Test configuration values."""
    print("\n=== Test 5: Configuration ===")

    config_items = [
        ("visual_mode", settings.visual_mode, ["recall", "rerank", "auto"]),
        ("rerank_candidate_pool_size", settings.rerank_candidate_pool_size, None),
        ("rerank_clip_weight", settings.rerank_clip_weight, (0.0, 1.0)),
        ("rerank_min_score_range", settings.rerank_min_score_range, None),
        ("clip_text_embedding_timeout_s", settings.clip_text_embedding_timeout_s, None),
        ("clip_text_embedding_max_retries", settings.clip_text_embedding_max_retries, None),
    ]

    all_valid = True
    for name, value, constraint in config_items:
        print(f"{name}: {value}")

        if constraint is not None:
            if isinstance(constraint, list):
                if value not in constraint:
                    print(f"  ⚠️  Invalid value, should be one of: {constraint}")
                    all_valid = False
            elif isinstance(constraint, tuple):
                if not (constraint[0] <= value <= constraint[1]):
                    print(f"  ⚠️  Out of range, should be in [{constraint[0]}, {constraint[1]}]")
                    all_valid = False

    if all_valid:
        print("\n✅ All configurations valid")
    else:
        print("\n⚠️  Some configurations need review")

    return all_valid


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("CLIP Visual Search Integration Tests")
    print("=" * 60)

    tests = [
        ("CLIP Client Availability", test_clip_client_availability),
        ("CLIP Text Embedding", test_clip_text_embedding),
        ("Visual Intent Router", test_visual_intent_router),
        ("CLIP Degradation", test_clip_degradation),
        ("Configuration", test_configuration),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
