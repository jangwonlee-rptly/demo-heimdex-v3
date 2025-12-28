"""Weight resolution and management for multi-channel search.

This module provides the single source of truth for:
- Channel weight precedence (request > saved > defaults)
- Weight normalization and validation
- Channel mapping (user keys -> fusion keys)
- Guardrails (clamping, redistribution, visual mode conflicts)
"""
import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


# Canonical channel names (user-facing)
USER_CHANNELS = {"transcript", "visual", "summary", "lexical"}

# Mapping: user channel name -> fusion channel key
CHANNEL_MAPPING = {
    "transcript": "dense_transcript",
    "visual": "dense_visual",
    "summary": "dense_summary",
    "lexical": "lexical",
}

# Inverse mapping for response formatting
FUSION_TO_USER_MAPPING = {v: k for k, v in CHANNEL_MAPPING.items()}


@dataclass
class WeightResolutionResult:
    """Result of weight resolution process.

    Tracks the complete weight resolution pipeline for transparency and debugging.
    """

    # Requested weights (from request, or None if not provided)
    weights_requested: Optional[dict[str, float]]

    # Resolved weights (after precedence, normalized)
    weights_resolved: dict[str, float]

    # Applied weights (after channel disable/redistribution, in fusion keys)
    weights_applied: dict[str, float]

    # Source of weights
    source: str  # "request" | "saved" | "default"

    # Channels that were disabled (missing data or flat scores)
    channels_disabled: list[str]

    # Whether weights were clamped due to guardrails
    weights_clamped: bool

    # Warning messages (if any)
    warnings: list[str]


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize weights to sum to 1.0.

    Args:
        weights: Raw weights (may not sum to 1.0)

    Returns:
        Normalized weights that sum to 1.0

    Raises:
        ValueError: If all weights are zero or negative
    """
    # Filter positive weights
    positive_weights = {k: v for k, v in weights.items() if v > 0.0}

    if not positive_weights:
        raise ValueError("At least one weight must be > 0")

    total = sum(positive_weights.values())

    if total <= 0.0:
        raise ValueError(f"Total weight must be positive, got {total}")

    # Normalize
    normalized = {k: v / total for k, v in positive_weights.items()}

    return normalized


def validate_user_weights(weights: dict[str, float]) -> tuple[bool, str]:
    """Validate user-provided channel weights.

    Args:
        weights: User weights dict with keys from USER_CHANNELS

    Returns:
        (is_valid, error_message)
    """
    # Check keys
    invalid_keys = set(weights.keys()) - USER_CHANNELS
    if invalid_keys:
        return False, f"Invalid channel keys: {invalid_keys}. Allowed: {USER_CHANNELS}"

    # Check all in [0, 1]
    for channel, weight in weights.items():
        if not (0.0 <= weight <= 1.0):
            return False, f"Weight for '{channel}' must be in [0, 1], got {weight}"

    # Check at least one > 0
    if all(w <= 0.0 for w in weights.values()):
        return False, "At least one weight must be > 0"

    return True, ""


def apply_weight_guardrails(
    weights: dict[str, float],
    max_visual_weight: float = 0.8,
    min_lexical_weight: float = 0.05,
) -> tuple[dict[str, float], bool, list[str]]:
    """Apply safety guardrails to weights.

    Clamps weights to safe ranges and renormalizes.

    Args:
        weights: Normalized user weights
        max_visual_weight: Maximum allowed visual weight
        min_lexical_weight: Minimum lexical weight (if lexical > 0)

    Returns:
        (clamped_weights, was_clamped, warnings)
    """
    clamped = weights.copy()
    was_clamped = False
    warnings = []

    # Clamp visual weight
    if "visual" in clamped and clamped["visual"] > max_visual_weight:
        old_val = clamped["visual"]
        clamped["visual"] = max_visual_weight
        was_clamped = True
        warnings.append(
            f"Visual weight clamped from {old_val:.2f} to {max_visual_weight:.2f} "
            f"(prevent sparse match over-reliance)"
        )

    # Enforce minimum lexical if present
    if "lexical" in clamped and 0.0 < clamped["lexical"] < min_lexical_weight:
        old_val = clamped["lexical"]
        clamped["lexical"] = min_lexical_weight
        was_clamped = True
        warnings.append(
            f"Lexical weight boosted from {old_val:.2f} to {min_lexical_weight:.2f} "
            f"(preserve keyword signal)"
        )

    # Renormalize if clamped
    if was_clamped:
        clamped = normalize_weights(clamped)

    return clamped, was_clamped, warnings


def map_to_fusion_keys(weights: dict[str, float]) -> dict[str, float]:
    """Map user channel names to internal fusion keys.

    Args:
        weights: User weights with keys from USER_CHANNELS

    Returns:
        Fusion weights with keys like "dense_transcript", "lexical"
    """
    fusion_weights = {}

    for user_key, weight in weights.items():
        fusion_key = CHANNEL_MAPPING.get(user_key)
        if fusion_key:
            fusion_weights[fusion_key] = weight

    return fusion_weights


def map_to_user_keys(weights: dict[str, float]) -> dict[str, float]:
    """Map fusion channel keys back to user-facing names.

    Args:
        weights: Fusion weights with keys like "dense_transcript"

    Returns:
        User weights with keys from USER_CHANNELS
    """
    user_weights = {}

    for fusion_key, weight in weights.items():
        user_key = FUSION_TO_USER_MAPPING.get(fusion_key, fusion_key)
        user_weights[user_key] = weight

    return user_weights


def redistribute_weights(
    weights: dict[str, float],
    disabled_channels: set[str],
) -> dict[str, float]:
    """Redistribute weights when channels are disabled.

    Args:
        weights: Current weights (fusion keys)
        disabled_channels: Set of fusion keys to disable

    Returns:
        Redistributed weights with disabled channels removed
    """
    # Remove disabled channels
    active_weights = {
        k: v for k, v in weights.items()
        if k not in disabled_channels
    }

    if not active_weights:
        raise ValueError("Cannot redistribute: all channels disabled")

    # Renormalize
    total = sum(active_weights.values())
    redistributed = {k: v / total for k, v in active_weights.items()}

    return redistributed


def resolve_weights(
    request_weights: Optional[dict[str, float]],
    saved_weights: Optional[dict[str, float]],
    default_weights: dict[str, float],
    use_saved_preferences: bool = True,
    visual_mode: Optional[str] = None,
    enable_guardrails: bool = True,
) -> WeightResolutionResult:
    """Resolve final weights with 3-tier precedence.

    Precedence order:
    1. Per-request weights (highest priority)
    2. Saved user preferences (if use_saved_preferences=True)
    3. System defaults

    Args:
        request_weights: Weights from request.channel_weights (user keys)
        saved_weights: Weights from user preferences (user keys)
        default_weights: System defaults (user keys)
        use_saved_preferences: Whether to use saved prefs if available
        visual_mode: Visual search mode ("skip" disables visual)
        enable_guardrails: Whether to apply weight clamping

    Returns:
        WeightResolutionResult with complete resolution trace
    """
    weights_requested = None
    source = "default"
    warnings = []

    # Tier 1: Per-request override
    if request_weights is not None:
        # Validate
        is_valid, error_msg = validate_user_weights(request_weights)
        if not is_valid:
            raise ValueError(f"Invalid request weights: {error_msg}")

        weights = request_weights.copy()
        weights_requested = request_weights.copy()
        source = "request"

    # Tier 2: Saved preferences
    elif use_saved_preferences and saved_weights is not None:
        # Validate (in case stored data is corrupted)
        is_valid, error_msg = validate_user_weights(saved_weights)
        if not is_valid:
            logger.warning(f"Saved preferences invalid, falling back to defaults: {error_msg}")
            weights = default_weights.copy()
            source = "default"
        else:
            weights = saved_weights.copy()
            source = "saved"

    # Tier 3: System defaults
    else:
        weights = default_weights.copy()
        source = "default"

    # Normalize weights (in case they don't sum to 1.0)
    try:
        weights = normalize_weights(weights)
    except ValueError as e:
        raise ValueError(f"Weight normalization failed: {e}")

    # Apply guardrails
    weights_clamped = False
    if enable_guardrails:
        weights, weights_clamped, clamp_warnings = apply_weight_guardrails(weights)
        warnings.extend(clamp_warnings)

    # Visual mode conflict handling
    if visual_mode == "skip" and "visual" in weights and weights["visual"] > 0.0:
        logger.info(
            f"visual_mode='skip' detected, forcing visual weight to 0.0 "
            f"(was {weights['visual']:.2f})"
        )
        weights["visual"] = 0.0
        weights = normalize_weights(weights)
        warnings.append("Visual weight forced to 0 (visual_mode='skip')")

    # Store resolved weights (user keys)
    weights_resolved = weights.copy()

    # Map to fusion keys
    weights_fusion = map_to_fusion_keys(weights)

    # No channels disabled yet (will be done during fusion based on actual data)
    channels_disabled = []

    return WeightResolutionResult(
        weights_requested=weights_requested,
        weights_resolved=weights_resolved,
        weights_applied=weights_fusion,
        source=source,
        channels_disabled=channels_disabled,
        weights_clamped=weights_clamped,
        warnings=warnings,
    )


def get_default_weights() -> dict[str, float]:
    """Get default channel weights (user keys).

    Returns:
        Default weights matching system config
    """
    # Import here to avoid circular dependency
    from ...config import settings

    return {
        "transcript": settings.weight_transcript,
        "visual": settings.weight_visual,
        "summary": settings.weight_summary,
        "lexical": settings.weight_lexical_multi,
    }
