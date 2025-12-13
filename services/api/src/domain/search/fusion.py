"""Reciprocal Rank Fusion (RRF) for hybrid search.

RRF combines results from multiple retrieval systems by giving each result
a score based on its rank in each system's result list:

    RRF_score = sum(1 / (k + rank_i)) for each system i

Where k is a constant (typically 60) that controls how much weight
is given to top-ranked results vs. lower-ranked ones.

References:
- Cormack, Clarke & Büttcher (2009) "Reciprocal Rank Fusion outperforms
  Condorcet and individual Rank Learning Methods"
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Candidate:
    """A candidate result from a single retrieval system."""

    scene_id: str
    rank: int  # 1-indexed rank within the retrieval system
    score: float  # Original score from the retrieval system


@dataclass
class FusedCandidate:
    """A result after RRF fusion."""

    scene_id: str
    fused_score: float  # Combined RRF score
    dense_rank: Optional[int] = None  # Rank in dense results (1-indexed, None if not present)
    lexical_rank: Optional[int] = None  # Rank in lexical results (1-indexed, None if not present)
    dense_score: Optional[float] = None  # Original dense similarity score
    lexical_score: Optional[float] = None  # Original BM25 score


def rrf_fuse(
    dense_candidates: list[Candidate],
    lexical_candidates: list[Candidate],
    rrf_k: int = 60,
    top_k: int = 10,
) -> list[FusedCandidate]:
    """Fuse dense and lexical retrieval results using Reciprocal Rank Fusion.

    Args:
        dense_candidates: Results from dense (vector) retrieval, ordered by similarity.
        lexical_candidates: Results from lexical (BM25) retrieval, ordered by score.
        rrf_k: The k constant for RRF (default: 60). Higher values reduce the
               difference between top and lower ranks.
        top_k: Number of results to return after fusion.

    Returns:
        list[FusedCandidate]: Top-k results after fusion, sorted by fused score descending.

    Example:
        >>> dense = [Candidate("a", 1, 0.95), Candidate("b", 2, 0.85)]
        >>> lexical = [Candidate("b", 1, 25.0), Candidate("c", 2, 20.0)]
        >>> results = rrf_fuse(dense, lexical, rrf_k=60, top_k=3)
        >>> # "b" appears in both lists, so gets highest fused score
    """
    # Build lookup tables for each retrieval system
    dense_by_id: dict[str, Candidate] = {c.scene_id: c for c in dense_candidates}
    lexical_by_id: dict[str, Candidate] = {c.scene_id: c for c in lexical_candidates}

    # Get all unique scene IDs
    all_ids = set(dense_by_id.keys()) | set(lexical_by_id.keys())

    # Calculate RRF score for each scene
    fused_results: list[FusedCandidate] = []

    for scene_id in all_ids:
        fused_score = 0.0
        dense_rank = None
        lexical_rank = None
        dense_score = None
        lexical_score = None

        # Add contribution from dense retrieval
        if scene_id in dense_by_id:
            dense_candidate = dense_by_id[scene_id]
            dense_rank = dense_candidate.rank
            dense_score = dense_candidate.score
            fused_score += 1.0 / (rrf_k + dense_rank)

        # Add contribution from lexical retrieval
        if scene_id in lexical_by_id:
            lexical_candidate = lexical_by_id[scene_id]
            lexical_rank = lexical_candidate.rank
            lexical_score = lexical_candidate.score
            fused_score += 1.0 / (rrf_k + lexical_rank)

        fused_results.append(FusedCandidate(
            scene_id=scene_id,
            fused_score=fused_score,
            dense_rank=dense_rank,
            lexical_rank=lexical_rank,
            dense_score=dense_score,
            lexical_score=lexical_score,
        ))

    # Sort by fused score descending, with tie-breaking:
    # 1. Higher fused score first
    # 2. Better (lower) dense rank first
    # 3. Better (lower) lexical rank first
    # 4. Scene ID as final tiebreaker for stability
    def sort_key(candidate: FusedCandidate) -> tuple:
        return (
            -candidate.fused_score,  # Negative for descending
            candidate.dense_rank if candidate.dense_rank is not None else float('inf'),
            candidate.lexical_rank if candidate.lexical_rank is not None else float('inf'),
            candidate.scene_id,  # Stable tiebreaker
        )

    fused_results.sort(key=sort_key)

    return fused_results[:top_k]


def dense_only_fusion(
    dense_candidates: list[Candidate],
    top_k: int = 10,
) -> list[FusedCandidate]:
    """Create fused results from dense candidates only (fallback mode).

    Used when OpenSearch is unavailable.

    Args:
        dense_candidates: Results from dense retrieval.
        top_k: Number of results to return.

    Returns:
        list[FusedCandidate]: Results with only dense information filled in.
    """
    results = []
    for candidate in dense_candidates[:top_k]:
        results.append(FusedCandidate(
            scene_id=candidate.scene_id,
            fused_score=candidate.score,  # Use similarity as fused score
            dense_rank=candidate.rank,
            lexical_rank=None,
            dense_score=candidate.score,
            lexical_score=None,
        ))
    return results


def lexical_only_fusion(
    lexical_candidates: list[Candidate],
    top_k: int = 10,
) -> list[FusedCandidate]:
    """Create fused results from lexical candidates only (fallback mode).

    Used when embedding generation fails.

    Args:
        lexical_candidates: Results from lexical retrieval.
        top_k: Number of results to return.

    Returns:
        list[FusedCandidate]: Results with only lexical information filled in.
    """
    results = []
    for candidate in lexical_candidates[:top_k]:
        results.append(FusedCandidate(
            scene_id=candidate.scene_id,
            fused_score=candidate.score,  # Use BM25 score as fused score
            dense_rank=None,
            lexical_rank=candidate.rank,
            dense_score=None,
            lexical_score=candidate.score,
        ))
    return results
