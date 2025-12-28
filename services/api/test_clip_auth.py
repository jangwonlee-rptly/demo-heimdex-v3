#!/usr/bin/env python3
"""
Quick test script to verify CLIP client HMAC authentication works.

Run this to test the CLIP client without running a full search.
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from adapters.clip_client import get_clip_client, is_clip_available, ClipClientError


def main():
    print("=" * 60)
    print("CLIP Client Authentication Test")
    print("=" * 60)

    # Check if CLIP is configured
    if not is_clip_available():
        print("❌ CLIP not configured")
        print("Set CLIP_RUNPOD_URL and CLIP_RUNPOD_SECRET environment variables")
        return 1

    print("✅ CLIP client is configured")

    # Get client
    try:
        clip_client = get_clip_client()
        print(f"Client: {clip_client.base_url}")
        print(f"Timeout: {clip_client.timeout_s}s")
        print(f"Max retries: {clip_client.max_retries}")
    except Exception as e:
        print(f"❌ Failed to create CLIP client: {e}")
        return 1

    # Test with a simple query
    test_text = "red car"
    print(f"\nTesting with text: '{test_text}'")

    try:
        embedding = clip_client.create_text_embedding(test_text, normalize=True)

        print("\n✅ SUCCESS!")
        print(f"Embedding dimension: {len(embedding)}")
        print(f"L2 norm: {sum(x*x for x in embedding)**0.5:.4f}")
        print(f"First 5 values: {embedding[:5]}")

        # Verify properties
        assert len(embedding) == 512, f"Expected 512d, got {len(embedding)}"
        l2_norm = sum(x*x for x in embedding)**0.5
        assert 0.99 <= l2_norm <= 1.01, f"Expected normalized, got norm={l2_norm}"

        print("\n🎉 All checks passed!")
        return 0

    except ClipClientError as e:
        print(f"\n❌ CLIP client error: {e}")
        print("\nPossible issues:")
        print("1. CLIP_RUNPOD_SECRET doesn't match the service")
        print("2. CLIP service is not running")
        print("3. HMAC signature format mismatch")
        return 1

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
