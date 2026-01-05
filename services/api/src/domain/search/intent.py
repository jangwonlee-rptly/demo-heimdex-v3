"""Query intent detection for search optimization.

This module implements lightweight heuristics to detect whether a query is a:
- "lookup" query: brand names, proper nouns, short identifiers (e.g., "Heimdex", "이장원", "BTS")
- "semantic" query: natural language questions or descriptions (e.g., "영상 편집", "person walking")

The intent detection is used for "soft lexical gating" to reduce false positives when
users search for specific names/brands that should have exact lexical matches.
"""

import re
from typing import Literal

# Korean unicode ranges for Hangul syllables
HANGUL_SYLLABLES_PATTERN = re.compile(r"[\uAC00-\uD7A3]+")


def detect_query_intent(
    query: str,
    language: str | None = None,
) -> Literal["lookup", "semantic"]:
    """Detect whether a query is a lookup (name/brand) or semantic (descriptive) query.

    Heuristics for "lookup" classification:
    - Normalized query has 1-2 tokens AND one of:
      - Contains uppercase letters (e.g., "Heimdex", "OpenAI", "BTS")
      - Looks like a Korean name (2-4 Hangul syllables, no spaces)
      - Very short (<= 6 chars) with mostly alphanumeric characters

    All other queries are classified as "semantic".

    Args:
        query: Raw user query string
        language: Optional language hint (e.g., "ko", "en") - currently unused but reserved

    Returns:
        "lookup" if the query appears to be a brand/name/identifier
        "semantic" if the query appears to be a natural language description

    Examples:
        >>> detect_query_intent("heimdex")
        'lookup'
        >>> detect_query_intent("Heimdex")
        'lookup'
        >>> detect_query_intent("이장원")
        'lookup'
        >>> detect_query_intent("BTS")
        'lookup'
        >>> detect_query_intent("NewJeans")
        'lookup'
        >>> detect_query_intent("NVIDIA")
        'lookup'
        >>> detect_query_intent("영상 편집")
        'semantic'
        >>> detect_query_intent("사람이 걷는 장면")
        'semantic'
        >>> detect_query_intent("studio interview")
        'semantic'
        >>> detect_query_intent("funny moment")
        'semantic'
        >>> detect_query_intent("공원에서 달리는")
        'semantic'
    """
    # Normalize: strip and collapse whitespace
    normalized = " ".join(query.strip().split())

    if not normalized:
        return "semantic"

    # Token count
    tokens = normalized.split()
    token_count = len(tokens)

    # Lookup heuristic 1: 1-2 tokens with uppercase letters
    if token_count <= 2:
        if any(c.isupper() for c in normalized):
            return "lookup"

    # Lookup heuristic 2: Korean name pattern
    # 2-4 Hangul syllables with no spaces (e.g., "이장원", "김철수")
    hangul_only = HANGUL_SYLLABLES_PATTERN.findall(normalized)
    if len(hangul_only) == 1:  # Single contiguous Hangul block
        syllable_count = len(hangul_only[0])
        if 2 <= syllable_count <= 4 and " " not in normalized:
            return "lookup"

    # Lookup heuristic 3: Very short, mostly alphanumeric, 1-2 tokens
    if token_count <= 2 and len(normalized) <= 6:
        # Check if mostly alphanumeric (allows some punctuation like "-")
        alnum_ratio = sum(c.isalnum() for c in normalized) / len(normalized)
        if alnum_ratio >= 0.7:
            return "lookup"

    # Default: semantic
    return "semantic"


def looks_like_korean_name(text: str) -> bool:
    """Helper: Check if text looks like a Korean personal name.

    Korean names are typically 2-4 Hangul syllables with no spaces.

    Args:
        text: Input text to check

    Returns:
        True if text matches Korean name pattern

    Examples:
        >>> looks_like_korean_name("이장원")
        True
        >>> looks_like_korean_name("김철수")
        True
        >>> looks_like_korean_name("홍길동")
        True
        >>> looks_like_korean_name("이")
        False
        >>> looks_like_korean_name("이장원입니다")
        False
        >>> looks_like_korean_name("John Smith")
        False
    """
    # Must be pure Hangul (no spaces, no other characters)
    if not text or " " in text:
        return False

    hangul_blocks = HANGUL_SYLLABLES_PATTERN.findall(text)

    # Must be exactly one contiguous block
    if len(hangul_blocks) != 1:
        return False

    # Must cover entire text
    if hangul_blocks[0] != text:
        return False

    # Must be 2-4 syllables
    syllable_count = len(text)
    return 2 <= syllable_count <= 4
