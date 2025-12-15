"""Hybrid search fusion algorithms.

This module provides two fusion methods for combining dense (vector) and lexical (BM25) search results:

1. Min-Max Weighted Mean (default):
   - Normalizes scores from each system to [0, 1] range using min-max normalization
   - Combines using weighted arithmetic mean: score = w_dense * dense_norm + w_lexical * lexical_norm
   - Best for: Fine-grained score comparisons, tunable weights

2. Reciprocal Rank Fusion (RRF):
   - Combines based on rank position: RRF_score = sum(1 / (k + rank_i))
   - Ignores raw scores, only uses rankings
   - Best for: Stability with outliers, when raw scores are unreliable

Score Scale Incompatibility (why normalization matters):
- Dense scores (cosine similarity): Typically 0.0 to 1.0, with most results 0.3-0.9
- BM25 scores: Unbounded positive, typically 0 to 50+, depends on query/document length
- Without normalization, one system dominates the other in weighted combinations

References:
- Cormack, Clarke & Büttcher (2009) "Reciprocal Rank Fusion outperforms
  Condorcet and individual Rank Learning Methods"
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ScoreType(str, Enum):
    """Type of score returned by fusion."""
    MINMAX_MEAN = "minmax_mean"
    RRF = "rrf"
    DENSE_ONLY = "dense_only"
    LEXICAL_ONLY = "lexical_only"


@dataclass
class Candidate:
    """A candidate result from a single retrieval system."""

    scene_id: str
    rank: int  # 1-indexed rank within the retrieval system
    score: float  # Original score from the retrieval system


@dataclass
class FusedCandidate:
    """A result after fusion.

    Contains both the final fused score and detailed breakdown for debugging.
    """

    scene_id: str
    score: float  # The final ranking score used (unified field name)
    score_type: ScoreType  # Type of fusion that produced this score

    # Rank information (always populated when available)
    dense_rank: Optional[int] = None  # Rank in dense results (1-indexed, None if not present)
    lexical_rank: Optional[int] = None  # Rank in lexical results (1-indexed, None if not present)

    # Raw scores from each system (always populated when available)
    dense_score_raw: Optional[float] = None  # Original dense similarity score
    lexical_score_raw: Optional[float] = None  # Original BM25 score

    # Normalized scores (only populated for minmax_mean fusion)
    dense_score_norm: Optional[float] = None  # Min-max normalized dense score [0, 1]
    lexical_score_norm: Optional[float] = None  # Min-max normalized lexical score [0, 1]

    # Legacy alias for backward compatibility
    @property
    def fused_score(self) -> float:
        """Alias for score (backward compatibility)."""
        return self.score

    @property
    def dense_score(self) -> Optional[float]:
        """Alias for dense_score_raw (backward compatibility)."""
        return self.dense_score_raw

    @property
    def lexical_score(self) -> Optional[float]:
        """Alias for lexical_score_raw (backward compatibility)."""
        return self.lexical_score_raw


def minmax_normalize(
    scores: list[float],
    eps: float = 1e-9,
) -> list[float]:
    """Normalize scores to [0, 1] range using min-max normalization.

    Formula: norm(x) = (x - min) / (max - min + eps)

    Args:
        scores: List of raw scores to normalize.
        eps: Small epsilon to avoid division by zero (default: 1e-9).

    Returns:
        list[float]: Normalized scores in [0, 1] range.

    Edge cases:
        - Empty list: Returns empty list
        - Single element: Returns [1.0] (contributes uniformly)
        - All same value (max == min): Returns all 1.0 (contributes uniformly)

    Example:
        >>> minmax_normalize([10, 20, 30])
        [0.0, 0.5, 1.0]
        >>> minmax_normalize([5, 5, 5])
        [1.0, 1.0, 1.0]
    """
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)

    # If all scores are the same, return 1.0 for all (uniform contribution)
    if max_score - min_score < eps:
        return [1.0] * len(scores)

    # Normalize to [0, 1]
    normalized = []
    for score in scores:
        norm = (score - min_score) / (max_score - min_score + eps)
        # Clamp to [0, 1] for safety
        norm = max(0.0, min(1.0, norm))
        normalized.append(norm)

    return normalized


def minmax_weighted_mean_fuse(
    dense_candidates: list[Candidate],
    lexical_candidates: list[Candidate],
    weight_dense: float = 0.7,
    weight_lexical: float = 0.3,
    eps: float = 1e-9,
    top_k: int = 10,
) -> list[FusedCandidate]:
    """Fuse dense and lexical results using min-max normalization and weighted mean.

    This is the recommended fusion method when you want fine-grained control over
    how much weight each retrieval system contributes to the final ranking.

    Algorithm:
        1. Normalize dense scores within dense candidates using min-max
        2. Normalize lexical scores within lexical candidates using min-max
        3. For each scene in the union:
           - score = w_dense * dense_norm + w_lexical * lexical_norm
           - Missing modality contributes 0.0
        4. Sort by score descending, return top_k

    Args:
        dense_candidates: Results from dense (vector) retrieval, ordered by similarity.
        lexical_candidates: Results from lexical (BM25) retrieval, ordered by score.
        weight_dense: Weight for dense scores (default: 0.7). Must be in [0, 1].
        weight_lexical: Weight for lexical scores (default: 0.3). Must be in [0, 1].
        eps: Epsilon for min-max normalization (default: 1e-9).
        top_k: Number of results to return after fusion.

    Returns:
        list[FusedCandidate]: Top-k results after fusion, sorted by score descending.

    Raises:
        ValueError: If weights don't sum to approximately 1.0 (tolerance 0.01).

    Tuning Guidance:
        - Default (0.7/0.3): Good for semantic queries where meaning > exact keywords
        - (0.5/0.5): Balanced, when both systems perform equally well
        - (0.3/0.7): When keyword matching is critical (e.g., code search, IDs)
        - Adjust based on your query patterns and relevance feedback

    Example:
        >>> dense = [Candidate("a", 1, 0.95), Candidate("b", 2, 0.85)]
        >>> lexical = [Candidate("b", 1, 25.0), Candidate("c", 2, 20.0)]
        >>> results = minmax_weighted_mean_fuse(dense, lexical, weight_dense=0.7, weight_lexical=0.3)
    """
    # Validate weights sum to 1.0 (with tolerance for float error)
    if abs(weight_dense + weight_lexical - 1.0) > 0.01:
        raise ValueError(
            f"Fusion weights must sum to 1.0, got dense={weight_dense}, "
            f"lexical={weight_lexical}, sum={weight_dense + weight_lexical}"
        )

    # Handle edge cases
    if not dense_candidates and not lexical_candidates:
        return []

    # Build lookup tables
    dense_by_id: dict[str, Candidate] = {c.scene_id: c for c in dense_candidates}
    lexical_by_id: dict[str, Candidate] = {c.scene_id: c for c in lexical_candidates}

    # Normalize scores within each system
    dense_scores = [c.score for c in dense_candidates]
    lexical_scores = [c.score for c in lexical_candidates]

    dense_norm_scores = minmax_normalize(dense_scores, eps)
    lexical_norm_scores = minmax_normalize(lexical_scores, eps)

    # Build normalized lookup
    dense_norm_by_id: dict[str, float] = {}
    for i, candidate in enumerate(dense_candidates):
        dense_norm_by_id[candidate.scene_id] = dense_norm_scores[i]

    lexical_norm_by_id: dict[str, float] = {}
    for i, candidate in enumerate(lexical_candidates):
        lexical_norm_by_id[candidate.scene_id] = lexical_norm_scores[i]

    # Get all unique scene IDs
    all_ids = set(dense_by_id.keys()) | set(lexical_by_id.keys())

    # Calculate weighted mean for each scene
    fused_results: list[FusedCandidate] = []

    for scene_id in all_ids:
        # Get normalized scores (0.0 if not in that system)
        dense_norm = dense_norm_by_id.get(scene_id, 0.0)
        lexical_norm = lexical_norm_by_id.get(scene_id, 0.0)

        # Weighted mean
        final_score = weight_dense * dense_norm + weight_lexical * lexical_norm

        # Get raw scores and ranks
        dense_candidate = dense_by_id.get(scene_id)
        lexical_candidate = lexical_by_id.get(scene_id)

        fused_results.append(FusedCandidate(
            scene_id=scene_id,
            score=final_score,
            score_type=ScoreType.MINMAX_MEAN,
            dense_rank=dense_candidate.rank if dense_candidate else None,
            lexical_rank=lexical_candidate.rank if lexical_candidate else None,
            dense_score_raw=dense_candidate.score if dense_candidate else None,
            lexical_score_raw=lexical_candidate.score if lexical_candidate else None,
            dense_score_norm=dense_norm if dense_candidate else None,
            lexical_score_norm=lexical_norm if lexical_candidate else None,
        ))

    # Sort by score descending, with tie-breaking
    def sort_key(candidate: FusedCandidate) -> tuple:
        return (
            -candidate.score,  # Higher score first
            candidate.dense_rank if candidate.dense_rank is not None else float('inf'),
            candidate.lexical_rank if candidate.lexical_rank is not None else float('inf'),
            candidate.scene_id,  # Stable tiebreaker
        )

    fused_results.sort(key=sort_key)

    return fused_results[:top_k]


def rrf_fuse(
    dense_candidates: list[Candidate],
    lexical_candidates: list[Candidate],
    rrf_k: int = 60,
    top_k: int = 10,
) -> list[FusedCandidate]:
    """Fuse dense and lexical retrieval results using Reciprocal Rank Fusion.

    RRF is a robust fusion method that uses rank positions rather than raw scores.
    This makes it less sensitive to score scale differences and outliers.

    Formula: RRF_score = sum(1 / (k + rank_i)) for each system i

    Args:
        dense_candidates: Results from dense (vector) retrieval, ordered by similarity.
        lexical_candidates: Results from lexical (BM25) retrieval, ordered by score.
        rrf_k: The k constant for RRF (default: 60). Higher values reduce the
               difference between top and lower ranks.
        top_k: Number of results to return after fusion.

    Returns:
        list[FusedCandidate]: Top-k results after fusion, sorted by score descending.

    Tuning Guidance:
        - k=60: Standard choice, good balance between top-rank emphasis and smoothness
        - k<60: More emphasis on top ranks (top-1 gets much higher score than top-2)
        - k>60: Smoother decay, less difference between adjacent ranks

    When to use RRF instead of Min-Max Mean:
        - Raw scores from one system are unreliable or have many outliers
        - You don't want to tune weights and prefer rank-based neutrality
        - Both systems are equally trusted (implicit 50/50 weighting)

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
        rrf_score = 0.0
        dense_rank = None
        lexical_rank = None
        dense_score_raw = None
        lexical_score_raw = None

        # Add contribution from dense retrieval
        if scene_id in dense_by_id:
            dense_candidate = dense_by_id[scene_id]
            dense_rank = dense_candidate.rank
            dense_score_raw = dense_candidate.score
            rrf_score += 1.0 / (rrf_k + dense_rank)

        # Add contribution from lexical retrieval
        if scene_id in lexical_by_id:
            lexical_candidate = lexical_by_id[scene_id]
            lexical_rank = lexical_candidate.rank
            lexical_score_raw = lexical_candidate.score
            rrf_score += 1.0 / (rrf_k + lexical_rank)

        fused_results.append(FusedCandidate(
            scene_id=scene_id,
            score=rrf_score,
            score_type=ScoreType.RRF,
            dense_rank=dense_rank,
            lexical_rank=lexical_rank,
            dense_score_raw=dense_score_raw,
            lexical_score_raw=lexical_score_raw,
            # RRF doesn't use normalized scores
            dense_score_norm=None,
            lexical_score_norm=None,
        ))

    # Sort by fused score descending, with tie-breaking:
    # 1. Higher fused score first
    # 2. Better (lower) dense rank first
    # 3. Better (lower) lexical rank first
    # 4. Scene ID as final tiebreaker for stability
    def sort_key(candidate: FusedCandidate) -> tuple:
        return (
            -candidate.score,  # Negative for descending
            candidate.dense_rank if candidate.dense_rank is not None else float('inf'),
            candidate.lexical_rank if candidate.lexical_rank is not None else float('inf'),
            candidate.scene_id,  # Stable tiebreaker
        )

    fused_results.sort(key=sort_key)

    return fused_results[:top_k]


def dense_only_fusion(
    dense_candidates: list[Candidate],
    top_k: int = 10,
    normalize: bool = False,
    eps: float = 1e-9,
) -> list[FusedCandidate]:
    """Create fused results from dense candidates only (fallback mode).

    Used when OpenSearch is unavailable.

    Args:
        dense_candidates: Results from dense retrieval.
        top_k: Number of results to return.
        normalize: If True, apply min-max normalization to scores.
        eps: Epsilon for normalization.

    Returns:
        list[FusedCandidate]: Results with only dense information filled in.
    """
    if not dense_candidates:
        return []

    # Optionally normalize
    if normalize:
        scores = [c.score for c in dense_candidates[:top_k]]
        norm_scores = minmax_normalize(scores, eps)
    else:
        norm_scores = None

    results = []
    for i, candidate in enumerate(dense_candidates[:top_k]):
        score = norm_scores[i] if norm_scores else candidate.score
        results.append(FusedCandidate(
            scene_id=candidate.scene_id,
            score=score,
            score_type=ScoreType.DENSE_ONLY,
            dense_rank=candidate.rank,
            lexical_rank=None,
            dense_score_raw=candidate.score,
            lexical_score_raw=None,
            dense_score_norm=norm_scores[i] if norm_scores else None,
            lexical_score_norm=None,
        ))
    return results


def lexical_only_fusion(
    lexical_candidates: list[Candidate],
    top_k: int = 10,
    normalize: bool = False,
    eps: float = 1e-9,
) -> list[FusedCandidate]:
    """Create fused results from lexical candidates only (fallback mode).

    Used when embedding generation fails.

    Args:
        lexical_candidates: Results from lexical retrieval.
        top_k: Number of results to return.
        normalize: If True, apply min-max normalization to scores.
        eps: Epsilon for normalization.

    Returns:
        list[FusedCandidate]: Results with only lexical information filled in.
    """
    if not lexical_candidates:
        return []

    # Optionally normalize
    if normalize:
        scores = [c.score for c in lexical_candidates[:top_k]]
        norm_scores = minmax_normalize(scores, eps)
    else:
        norm_scores = None

    results = []
    for i, candidate in enumerate(lexical_candidates[:top_k]):
        score = norm_scores[i] if norm_scores else candidate.score
        results.append(FusedCandidate(
            scene_id=candidate.scene_id,
            score=score,
            score_type=ScoreType.LEXICAL_ONLY,
            dense_rank=None,
            lexical_rank=candidate.rank,
            dense_score_raw=None,
            lexical_score_raw=candidate.score,
            dense_score_norm=None,
            lexical_score_norm=norm_scores[i] if norm_scores else None,
        ))
    return results


def fuse(
    dense_candidates: list[Candidate],
    lexical_candidates: list[Candidate],
    method: str = "minmax_mean",
    weight_dense: float = 0.7,
    weight_lexical: float = 0.3,
    rrf_k: int = 60,
    eps: float = 1e-9,
    top_k: int = 10,
) -> list[FusedCandidate]:
    """Unified fusion function that dispatches to the appropriate algorithm.

    This is the main entry point for fusion. It handles method selection and
    provides consistent error handling.

    Args:
        dense_candidates: Results from dense (vector) retrieval.
        lexical_candidates: Results from lexical (BM25) retrieval.
        method: Fusion method - "minmax_mean" (default) or "rrf".
        weight_dense: Weight for dense scores (minmax_mean only).
        weight_lexical: Weight for lexical scores (minmax_mean only).
        rrf_k: K constant for RRF (rrf only).
        eps: Epsilon for min-max normalization.
        top_k: Number of results to return.

    Returns:
        list[FusedCandidate]: Fused results sorted by score descending.

    Raises:
        ValueError: If method is not recognized or weights are invalid.

    Example:
        >>> dense = [Candidate("a", 1, 0.95)]
        >>> lexical = [Candidate("b", 1, 25.0)]
        >>> results = fuse(dense, lexical, method="minmax_mean")
    """
    if method == "minmax_mean":
        return minmax_weighted_mean_fuse(
            dense_candidates=dense_candidates,
            lexical_candidates=lexical_candidates,
            weight_dense=weight_dense,
            weight_lexical=weight_lexical,
            eps=eps,
            top_k=top_k,
        )
    elif method == "rrf":
        return rrf_fuse(
            dense_candidates=dense_candidates,
            lexical_candidates=lexical_candidates,
            rrf_k=rrf_k,
            top_k=top_k,
        )
    else:
        raise ValueError(f"Unknown fusion method: {method}. Use 'minmax_mean' or 'rrf'.")
