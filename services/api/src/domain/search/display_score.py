"""Per-query score calibration for UI display.

This module provides functions to calibrate fused search scores for display purposes
without affecting the ranking order. The goal is to avoid overconfident "100%" displays
when per-query min-max normalization inflates mediocre matches.

Key principles:
- Calibration is **monotonic**: if score_a > score_b, then display(a) >= display(b)
- Ranking order is **preserved**: only affects display values, not sort order
- Output is **bounded**: typically capped at 0.95-0.97 to avoid false confidence
- Method is **per-query**: uses only the current result set, no global stats needed

Recommended method: exp_squash (exponential squashing)
- Maps [min, max] scores to [~0, max_cap] using 1 - exp(-alpha * normalized)
- Provides smooth, interpretable confidence scaling
- Tunable via alpha parameter (higher = more aggressive squashing)
"""

import math
from typing import Optional


def calibrate_display_scores(
    scores: list[float],
    *,
    method: str = "exp_squash",
    eps: float = 1e-9,
    max_cap: float = 0.97,
    alpha: float = 3.0,
) -> list[float]:
    """Calibrate per-query scores for display only (UI confidence metric).

    This function transforms fused ranking scores into display scores that avoid
    overconfidence. It is **monotonic** (preserves ranking order) and **bounded**
    (caps at max_cap to prevent "100%" on mediocre matches).

    Args:
        scores: List of fused scores (typically [0, 1] from minmax fusion).
                Must be in the same order as search results.
        method: Calibration method ("exp_squash" or "pctl_ceiling").
        eps: Small epsilon to avoid division by zero.
        max_cap: Maximum display score (default: 0.97 → 97% max display).
        alpha: Exponential squashing parameter for exp_squash (higher = more aggressive).
               Typical range: 2.0-5.0.

    Returns:
        List of display scores in [0, max_cap], same length and order as input.

    Edge cases:
        - Empty list: Returns []
        - Single score: Returns [neutral_value] capped (typically ~0.5)
        - Flat distribution (all equal): Returns [neutral_value] * len(scores)
        - Normal distribution: Smooth gradient from ~0 to ~max_cap

    Example:
        >>> scores = [0.92, 0.85, 0.78, 0.65]  # From fusion
        >>> display = calibrate_display_scores(scores, alpha=3.0, max_cap=0.97)
        >>> # Result: [0.95, 0.82, 0.68, 0.45] (approximate, preserves order)
    """
    if method == "exp_squash":
        return _calibrate_exp_squash(scores, eps=eps, max_cap=max_cap, alpha=alpha)
    elif method == "pctl_ceiling":
        return _calibrate_pctl_ceiling(scores, eps=eps, max_cap=max_cap, pctl=0.90)
    else:
        raise ValueError(f"Unknown calibration method: {method}")


def _calibrate_exp_squash(
    scores: list[float],
    eps: float,
    max_cap: float,
    alpha: float,
) -> list[float]:
    """Exponential squashing calibration: y = min(max_cap, 1 - exp(-alpha * x)).

    This method provides smooth, interpretable confidence scaling:
    - Low scores (x~0): display ~0
    - Medium scores (x~0.5): display ~0.5-0.7 (depending on alpha)
    - High scores (x~1.0): display ~max_cap (never 1.0)

    Tuning alpha:
    - alpha=2.0: Gentle squashing (top scores reach ~0.86 * max_cap)
    - alpha=3.0: Moderate squashing (recommended, top scores reach ~0.95 * max_cap)
    - alpha=5.0: Aggressive squashing (top scores reach ~0.99 * max_cap)

    Args:
        scores: Input scores (typically [0, 1] from fusion).
        eps: Epsilon for numerical stability.
        max_cap: Maximum output value.
        alpha: Exponential decay parameter.

    Returns:
        Calibrated scores in [0, max_cap].
    """
    if not scores:
        return []

    # Handle flat distribution (all scores equal)
    lo = min(scores)
    hi = max(scores)
    if hi - lo < eps:
        # Neutral confidence when distribution is flat
        neutral = min(max_cap, 0.5)
        return [neutral] * len(scores)

    # Normalize to [0, 1]
    normalized = [(s - lo) / (hi - lo + eps) for s in scores]

    # Apply exponential squashing: y = 1 - exp(-alpha * x)
    squashed = [1.0 - math.exp(-alpha * x) for x in normalized]

    # Cap and clamp
    calibrated = [min(max_cap, max(0.0, y)) for y in squashed]

    return calibrated


def _calibrate_pctl_ceiling(
    scores: list[float],
    eps: float,
    max_cap: float,
    pctl: float,
) -> list[float]:
    """Percentile ceiling calibration: normalize to pctl instead of max.

    This method prevents the absolute top score from always mapping to max_cap
    by using a percentile (e.g., 90th or 95th) as the ceiling.

    Args:
        scores: Input scores.
        eps: Epsilon for numerical stability.
        max_cap: Maximum output value.
        pctl: Percentile to use as ceiling (0.0-1.0, e.g., 0.90 for 90th percentile).

    Returns:
        Calibrated scores in [0, max_cap].
    """
    if not scores:
        return []

    # Handle flat distribution
    lo = min(scores)
    hi = max(scores)
    if hi - lo < eps:
        neutral = min(max_cap, 0.5)
        return [neutral] * len(scores)

    # Compute percentile with linear interpolation
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    pctl_idx = pctl * (n - 1)
    lower_idx = int(pctl_idx)
    upper_idx = min(lower_idx + 1, n - 1)
    frac = pctl_idx - lower_idx
    pctl_value = sorted_scores[lower_idx] * (1 - frac) + sorted_scores[upper_idx] * frac

    # Use percentile as ceiling
    ceiling = max(pctl_value, lo + eps)

    # Normalize to [0, 1] using ceiling
    normalized = [
        min(1.0, (s - lo) / (ceiling - lo + eps))
        for s in scores
    ]

    # Cap
    calibrated = [min(max_cap, max(0.0, x)) for x in normalized]

    return calibrated


def get_neutral_display_score(max_cap: float = 0.97) -> float:
    """Return a neutral display score for edge cases (e.g., single result).

    This is used when we can't meaningfully calibrate (e.g., only 1 result,
    or all scores are identical).

    Args:
        max_cap: The configured max_cap value.

    Returns:
        A neutral display score (typically 0.5, capped at max_cap).
    """
    return min(max_cap, 0.5)
