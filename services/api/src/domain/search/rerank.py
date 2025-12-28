"""CLIP visual reranking utilities.

Rerank mode: Instead of using CLIP for retrieval (recall), use it to rerank
candidates retrieved by other channels (transcript, summary, lexical).
This is more stable when visual intent is weak or ambiguous.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from .fusion import FusedCandidate, ScoreType

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """Result of CLIP reranking."""

    reranked_candidates: list[FusedCandidate]  # Final reranked results
    clip_scores: dict[str, float]  # scene_id → CLIP score
    clip_score_range: tuple[float, float]  # (min, max) CLIP scores
    clip_weight_used: float  # Effective weight used for blending
    clip_skipped: bool  # True if CLIP was skipped (flat scores, error, etc.)
    skip_reason: Optional[str]  # Reason for skipping CLIP
    candidates_scored: int  # Number of candidates that had CLIP scores


def rerank_with_clip(
    base_candidates: list[FusedCandidate],
    clip_scores: dict[str, float],
    clip_weight: float = 0.3,
    min_score_range: float = 0.05,
    eps: float = 1e-9,
) -> RerankResult:
    """Rerank candidates by blending base fusion scores with CLIP scores.

    Args:
        base_candidates: Candidates from non-CLIP channels (already fused and ranked).
        clip_scores: Map of scene_id → CLIP similarity score (0.0-1.0).
        clip_weight: Weight for CLIP contribution (0.0-1.0). 0.3 means 30% CLIP, 70% base.
        min_score_range: Skip CLIP if score range (max-min) < this (flat scores).
        eps: Small epsilon for numerical stability.

    Returns:
        RerankResult with reranked candidates and metadata.
    """
    if not base_candidates:
        return RerankResult(
            reranked_candidates=[],
            clip_scores={},
            clip_score_range=(0.0, 0.0),
            clip_weight_used=0.0,
            clip_skipped=True,
            skip_reason="No base candidates to rerank",
            candidates_scored=0,
        )

    if not clip_scores:
        logger.warning("CLIP rerank: No CLIP scores available, returning base ranking")
        return RerankResult(
            reranked_candidates=base_candidates,
            clip_scores={},
            clip_score_range=(0.0, 0.0),
            clip_weight_used=0.0,
            clip_skipped=True,
            skip_reason="No CLIP scores returned",
            candidates_scored=0,
        )

    # Check CLIP score distribution (detect flat/weak scores)
    clip_values = list(clip_scores.values())
    clip_min = min(clip_values)
    clip_max = max(clip_values)
    clip_range = clip_max - clip_min

    if clip_range < min_score_range:
        logger.info(
            f"CLIP rerank: Skipping due to flat scores "
            f"(range={clip_range:.4f} < threshold={min_score_range})"
        )
        return RerankResult(
            reranked_candidates=base_candidates,
            clip_scores=clip_scores,
            clip_score_range=(clip_min, clip_max),
            clip_weight_used=0.0,
            clip_skipped=True,
            skip_reason=f"Flat CLIP scores (range={clip_range:.4f})",
            candidates_scored=len(clip_scores),
        )

    # Normalize CLIP scores to [0, 1] using min-max
    normalized_clip = {}
    for scene_id, score in clip_scores.items():
        norm_score = (score - clip_min) / (clip_range + eps)
        normalized_clip[scene_id] = norm_score

    # Normalize base scores to [0, 1] (they should already be normalized, but double-check)
    base_scores_raw = [c.score for c in base_candidates]
    if base_scores_raw:
        base_min = min(base_scores_raw)
        base_max = max(base_scores_raw)
        base_range = base_max - base_min
    else:
        base_min = base_max = base_range = 0.0

    # Blend scores: final = (1 - clip_weight) * base + clip_weight * clip
    reranked = []
    candidates_scored = 0

    for candidate in base_candidates:
        scene_id = candidate.scene_id

        # Normalize base score
        if base_range > eps:
            norm_base = (candidate.score - base_min) / (base_range + eps)
        else:
            norm_base = 1.0  # All base scores are equal

        # Get CLIP score (or 0 if missing)
        norm_clip = normalized_clip.get(scene_id, 0.0)

        # Track how many candidates have CLIP scores
        if scene_id in clip_scores:
            candidates_scored += 1

        # Blend
        blended_score = (1.0 - clip_weight) * norm_base + clip_weight * norm_clip

        # Create reranked candidate
        reranked_candidate = FusedCandidate(
            scene_id=scene_id,
            score=blended_score,
            score_type=ScoreType.RERANK_CLIP,
            # Preserve debug fields from base candidate
            dense_score_raw=candidate.dense_score_raw,
            lexical_score_raw=candidate.lexical_score_raw,
            dense_score_norm=candidate.dense_score_norm,
            lexical_score_norm=candidate.lexical_score_norm,
            dense_rank=candidate.dense_rank,
            lexical_rank=candidate.lexical_rank,
            channel_scores=candidate.channel_scores,
        )

        # Add CLIP score to channel_scores for debugging
        if reranked_candidate.channel_scores is None:
            reranked_candidate.channel_scores = {}
        reranked_candidate.channel_scores["clip_rerank"] = {
            "raw": clip_scores.get(scene_id, 0.0),
            "norm": norm_clip,
            "weight": clip_weight,
        }

        reranked.append(reranked_candidate)

    # Re-sort by blended score (descending)
    reranked.sort(key=lambda c: c.score, reverse=True)

    logger.info(
        f"CLIP rerank: Reranked {len(reranked)} candidates, "
        f"CLIP weight={clip_weight}, scored={candidates_scored}/{len(base_candidates)}, "
        f"CLIP range=[{clip_min:.4f}, {clip_max:.4f}]"
    )

    return RerankResult(
        reranked_candidates=reranked,
        clip_scores=clip_scores,
        clip_score_range=(clip_min, clip_max),
        clip_weight_used=clip_weight,
        clip_skipped=False,
        skip_reason=None,
        candidates_scored=candidates_scored,
    )
