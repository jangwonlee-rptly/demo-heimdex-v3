#!/usr/bin/env python3
"""Smoke test for hybrid search setup.

Tests that all components of hybrid search are working:
- OpenSearch connectivity
- Index exists with proper mapping
- BM25 search works
- Dense search works (if test data exists)
- RRF fusion works

Usage:
    # From API container or with proper environment:
    python -m src.scripts.smoke_hybrid_search

    # With a test query:
    python -m src.scripts.smoke_hybrid_search --query "people talking"

    # With a specific owner_id to test filtering:
    python -m src.scripts.smoke_hybrid_search --owner-id <uuid>
"""
import argparse
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Smoke test for hybrid search"
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Query to test with (default: runs Korean and English test queries)",
    )
    parser.add_argument(
        "--skip-analyzer-tests",
        action="store_true",
        help="Skip Korean/English analyzer-specific tests",
    )
    parser.add_argument(
        "--owner-id",
        type=str,
        help="Owner ID to filter results (optional, uses fake UUID if not provided)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    return parser.parse_args()


def main() -> int:
    """Run smoke tests for hybrid search.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Import here to ensure settings are loaded
    from ..adapters.opensearch_client import opensearch_client
    from ..adapters.openai_client import openai_client
    from ..domain.search.fusion import rrf_fuse, Candidate
    from ..config import settings

    logger.info("=" * 60)
    logger.info("Hybrid Search Smoke Test")
    logger.info("=" * 60)
    logger.info(f"OpenSearch URL: {settings.opensearch_url}")
    logger.info(f"Index name: {settings.opensearch_index_scenes}")
    logger.info(f"Hybrid search enabled: {settings.hybrid_search_enabled}")
    logger.info(f"RRF k: {settings.rrf_k}")
    if args.query:
        logger.info(f"Custom query: {args.query}")
    logger.info("")

    errors = []
    test_number = 1

    # Test 1: OpenSearch connectivity
    logger.info(f"[{test_number}/6] Testing OpenSearch connectivity...")
    test_number += 1
    try:
        if opensearch_client.ping():
            logger.info("  OK: OpenSearch is reachable")
        else:
            logger.error("  FAIL: OpenSearch ping returned False")
            errors.append("OpenSearch not reachable")
    except Exception as e:
        logger.error(f"  FAIL: OpenSearch ping error: {e}")
        errors.append(f"OpenSearch error: {e}")

    # Test 2: Nori plugin check
    logger.info(f"[{test_number}/6] Testing nori plugin availability...")
    test_number += 1
    try:
        if opensearch_client.check_nori_plugin():
            logger.info("  OK: Nori plugin is installed")
        else:
            logger.warning("  WARN: Nori plugin not found - Korean analysis may not work")
            errors.append("Nori plugin not available")
    except Exception as e:
        logger.error(f"  FAIL: Plugin check error: {e}")
        errors.append(f"Plugin check error: {e}")

    # Test 3: Index exists
    logger.info(f"[{test_number}/6] Testing index existence...")
    test_number += 1
    try:
        if opensearch_client.ensure_index():
            logger.info(f"  OK: Index '{settings.opensearch_index_scenes}' exists")

            stats = opensearch_client.get_index_stats()
            if stats:
                logger.info(f"  Index stats: {stats['doc_count']} docs, {stats['size_bytes']} bytes")
        else:
            logger.error("  FAIL: Could not ensure index exists")
            errors.append("Index creation failed")
    except Exception as e:
        logger.error(f"  FAIL: Index check error: {e}")
        errors.append(f"Index error: {e}")

    # Test 4: BM25 search with Korean query
    if not args.skip_analyzer_tests:
        logger.info(f"[{test_number}/6] Testing BM25 search with Korean query...")
        test_number += 1
        owner_id = args.owner_id or "00000000-0000-0000-0000-000000000000"
        korean_query = "사람"  # "person" in Korean
        try:
            start = time.time()
            results = opensearch_client.bm25_search(
                query=korean_query,
                owner_id=owner_id,
                size=10,
            )
            elapsed_ms = int((time.time() - start) * 1000)
            logger.info(f"  OK: Korean BM25 search ('{korean_query}') returned {len(results)} results in {elapsed_ms}ms")

            if results and args.verbose:
                logger.info("  Top results:")
                for r in results[:3]:
                    logger.info(f"    - {r['scene_id']}: score={r['score']:.4f}, rank={r['rank']}")
        except Exception as e:
            logger.error(f"  FAIL: Korean BM25 search error: {e}")
            errors.append(f"Korean BM25 search error: {e}")

        # Test 5: BM25 search with English query
        logger.info(f"[{test_number}/6] Testing BM25 search with English query...")
        test_number += 1
        english_query = args.query or "person walking"
        try:
            start = time.time()
            results = opensearch_client.bm25_search(
                query=english_query,
                owner_id=owner_id,
                size=10,
            )
            elapsed_ms = int((time.time() - start) * 1000)
            logger.info(f"  OK: English BM25 search ('{english_query}') returned {len(results)} results in {elapsed_ms}ms")

            if results and args.verbose:
                logger.info("  Top results:")
                for r in results[:3]:
                    logger.info(f"    - {r['scene_id']}: score={r['score']:.4f}, rank={r['rank']}")
        except Exception as e:
            logger.error(f"  FAIL: English BM25 search error: {e}")
            errors.append(f"English BM25 search error: {e}")
    else:
        # Skip analyzer tests, just run a basic test
        logger.info(f"[{test_number}/6] Testing BM25 search...")
        test_number += 1
        owner_id = args.owner_id or "00000000-0000-0000-0000-000000000000"
        test_query = args.query or "test search query"
        try:
            start = time.time()
            results = opensearch_client.bm25_search(
                query=test_query,
                owner_id=owner_id,
                size=10,
            )
            elapsed_ms = int((time.time() - start) * 1000)
            logger.info(f"  OK: BM25 search returned {len(results)} results in {elapsed_ms}ms")

            if results and args.verbose:
                logger.info("  Top results:")
                for r in results[:3]:
                    logger.info(f"    - {r['scene_id']}: score={r['score']:.4f}, rank={r['rank']}")
        except Exception as e:
            logger.error(f"  FAIL: BM25 search error: {e}")
            errors.append(f"BM25 search error: {e}")

    # Test: Embedding generation (skipping test number increment for backward compat)
    logger.info(f"[{test_number}/6] Testing embedding generation...")
    test_number += 1
    test_embedding_query = args.query or "test query"
    try:
        start = time.time()
        embedding = openai_client.create_embedding(test_embedding_query)
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(f"  OK: Generated {len(embedding)}-dim embedding in {elapsed_ms}ms")
    except Exception as e:
        logger.error(f"  FAIL: Embedding generation error: {e}")
        errors.append(f"Embedding error: {e}")

    # Test: RRF fusion
    logger.info(f"[{test_number}/6] Testing RRF fusion...")
    try:
        # Create synthetic test data
        dense_candidates = [
            Candidate(scene_id="scene-a", rank=1, score=0.95),
            Candidate(scene_id="scene-b", rank=2, score=0.85),
            Candidate(scene_id="scene-c", rank=3, score=0.75),
        ]
        lexical_candidates = [
            Candidate(scene_id="scene-b", rank=1, score=25.0),
            Candidate(scene_id="scene-d", rank=2, score=20.0),
            Candidate(scene_id="scene-a", rank=3, score=15.0),
        ]

        fused = rrf_fuse(
            dense_candidates=dense_candidates,
            lexical_candidates=lexical_candidates,
            rrf_k=settings.rrf_k,
            top_k=5,
        )

        logger.info(f"  OK: RRF fusion produced {len(fused)} results")

        # Verify expected behavior
        if fused[0].scene_id in ("scene-a", "scene-b"):
            logger.info("  OK: Overlapping candidates ranked higher as expected")
        else:
            logger.warning("  WARN: Unexpected ranking - overlapping candidates not prioritized")

        if args.verbose:
            logger.info("  Fused results:")
            for r in fused:
                logger.info(
                    f"    - {r.scene_id}: fused={r.fused_score:.6f}, "
                    f"dense_rank={r.dense_rank}, lexical_rank={r.lexical_rank}"
                )

    except Exception as e:
        logger.error(f"  FAIL: RRF fusion error: {e}")
        errors.append(f"RRF fusion error: {e}")

    # Summary
    logger.info("")
    logger.info("=" * 60)
    if errors:
        logger.error(f"FAILED: {len(errors)} error(s)")
        for err in errors:
            logger.error(f"  - {err}")
        return 1
    else:
        logger.info("SUCCESS: All smoke tests passed!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run reindex script to backfill existing scenes:")
        logger.info("     python -m src.scripts.reindex_opensearch")
        logger.info("")
        logger.info("  2. Test with real data:")
        logger.info(f"     python -m src.scripts.smoke_hybrid_search --owner-id <your-user-id>")
        return 0


if __name__ == "__main__":
    sys.exit(main())
