"""Person-weighted fusion for person-aware search."""
import logging
from typing import Optional

from .fusion import Candidate, FusedCandidate, ScoreType

logger = logging.getLogger(__name__)


def fuse_with_person(
    content_candidates: list[Candidate],
    person_candidates: list[Candidate],
    weight_content: float = 0.35,
    weight_person: float = 0.65,
    eps: float = 1e-9,
    top_k: int = 10,
) -> list[FusedCandidate]:
    """Fuse content and person candidates with person as strong signal.

    Uses weighted min-max normalization fusion where person signal (0.65) dominates
    over content signal (0.35), ensuring person-relevant scenes rank higher while
    still considering content matching.

    Args:
        content_candidates: Candidates from content search (topK, e.g., 200)
        person_candidates: Candidates from person visual search (topK, e.g., 200)
        weight_content: Weight for content signal (default: 0.35)
        weight_person: Weight for person signal (default: 0.65)
        eps: Small epsilon to avoid division by zero
        top_k: Number of results to return after fusion

    Returns:
        list[FusedCandidate]: Fused and sorted candidates with PERSON_CONTENT_FUSION score type
    """
    logger.info(
        f"Fusing person and content: content_n={len(content_candidates)}, "
        f"person_n={len(person_candidates)}, weights=({weight_content:.2f}, {weight_person:.2f})"
    )

    # Validate inputs
    if not content_candidates and not person_candidates:
        logger.warning("No candidates to fuse")
        return []

    # Fallback: content-only
    if not person_candidates:
        logger.info("No person candidates, returning content-only (truncated)")
        return [
            FusedCandidate(
                scene_id=c.scene_id,
                score=c.score,
                score_type=ScoreType.DENSE_ONLY,  # Not person fusion
                channel_scores={"content": c.score},
            )
            for i, c in enumerate(content_candidates[:top_k])
        ]

    # Fallback: person-only
    if not content_candidates:
        logger.info("No content candidates, returning person-only (truncated)")
        return [
            FusedCandidate(
                scene_id=c.scene_id,
                score=c.score,
                score_type=ScoreType.DENSE_ONLY,  # Not person fusion
                channel_scores={"person": c.score},
            )
            for i, c in enumerate(person_candidates[:top_k])
        ]

    # Build dictionaries for fast lookup
    content_scores = {c.scene_id: c.score for c in content_candidates}
    person_scores = {c.scene_id: c.score for c in person_candidates}

    # Get all unique scene IDs
    all_scene_ids = set(content_scores.keys()) | set(person_scores.keys())

    # Min-max normalize content scores
    content_values = list(content_scores.values())
    content_min = min(content_values)
    content_max = max(content_values)
    content_range = content_max - content_min + eps

    normalized_content = {
        scene_id: (score - content_min) / content_range
        for scene_id, score in content_scores.items()
    }

    # Min-max normalize person scores
    person_values = list(person_scores.values())
    person_min = min(person_values)
    person_max = max(person_values)
    person_range = person_max - person_min + eps

    normalized_person = {
        scene_id: (score - person_min) / person_range
        for scene_id, score in person_scores.items()
    }

    # Compute weighted fusion
    fused_results = []
    for scene_id in all_scene_ids:
        # Get normalized scores (default to 0 if not present)
        norm_content = normalized_content.get(scene_id, 0.0)
        norm_person = normalized_person.get(scene_id, 0.0)

        # Weighted sum
        final_score = weight_content * norm_content + weight_person * norm_person

        fused_results.append({
            "scene_id": scene_id,
            "score": final_score,
            "content_score": content_scores.get(scene_id),
            "person_score": person_scores.get(scene_id),
        })

    # Sort by final score DESC
    fused_results.sort(key=lambda x: x["score"], reverse=True)

    # Truncate to top_k
    fused_results = fused_results[:top_k]

    # Build FusedCandidate objects
    output = []
    for rank, result in enumerate(fused_results, start=1):
        channel_scores = {}
        if result["content_score"] is not None:
            channel_scores["content"] = result["content_score"]
        if result["person_score"] is not None:
            channel_scores["person"] = result["person_score"]

        output.append(
            FusedCandidate(
                scene_id=result["scene_id"],
                score=result["score"],
                score_type=ScoreType.PERSON_CONTENT_FUSION,
                channel_scores=channel_scores,
            )
        )

    logger.info(f"Fusion complete: returned {len(output)} candidates")

    return output
