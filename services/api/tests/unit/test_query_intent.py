"""Unit tests for query intent detection.

Tests the heuristics for classifying queries as "lookup" (brand/name/proper noun)
vs "semantic" (natural language description).
"""

import pytest
from src.domain.search.intent import detect_query_intent, looks_like_korean_name


class TestDetectQueryIntent:
    """Test suite for query intent detection heuristics."""

    # Lookup queries: should be classified as "lookup"
    LOOKUP_QUERIES = [
        # English brand names / proper nouns with uppercase
        "heimdex",
        "Heimdex",
        "HEIMDEX",
        "OpenAI",
        "BTS",
        "NewJeans",
        "NVIDIA",
        "Tesla",
        "SpaceX",
        "GitHub",
        # Korean names (2-4 Hangul syllables, no spaces)
        "이장원",
        "김철수",
        "홍길동",
        "박지성",
        # Short identifiers
        "API",
        "GPU",
        "AWS",
        "iOS",
        # Single-word brands
        "Nike",
        "Sony",
    ]

    # Semantic queries: should be classified as "semantic"
    SEMANTIC_QUERIES = [
        # Korean descriptive phrases
        "영상 편집",
        "사람이 걷는 장면",
        "공원에서 달리는",
        "인터뷰 영상",
        "재미있는 순간",
        "회의 장면",
        # English descriptive phrases
        "studio interview",
        "funny moment",
        "person walking",
        "editing video",
        "running in park",
        "meeting scene",
        # Questions
        "how to edit videos",
        "what is machine learning",
        # Longer sentences
        "show me videos of people talking",
        "find interviews about AI",
        # Lowercase multi-word phrases (no uppercase = not lookup)
        "video editing tutorial",
        "machine learning basics",
    ]

    def test_lookup_queries(self):
        """All LOOKUP_QUERIES should be classified as 'lookup'."""
        for query in self.LOOKUP_QUERIES:
            result = detect_query_intent(query)
            assert result == "lookup", f"Expected 'lookup' for query: {query!r}, got {result!r}"

    def test_semantic_queries(self):
        """All SEMANTIC_QUERIES should be classified as 'semantic'."""
        for query in self.SEMANTIC_QUERIES:
            result = detect_query_intent(query)
            assert result == "semantic", f"Expected 'semantic' for query: {query!r}, got {result!r}"

    def test_empty_query(self):
        """Empty query should default to 'semantic'."""
        assert detect_query_intent("") == "semantic"
        assert detect_query_intent("   ") == "semantic"

    def test_whitespace_normalization(self):
        """Queries with extra whitespace should be normalized correctly."""
        assert detect_query_intent("  Heimdex  ") == "lookup"
        assert detect_query_intent("video  editing") == "semantic"

    def test_case_sensitivity(self):
        """Uppercase triggers lookup for 1-2 token queries."""
        # With uppercase: lookup
        assert detect_query_intent("Heimdex") == "lookup"
        assert detect_query_intent("HEIMDEX") == "lookup"
        assert detect_query_intent("OpenAI") == "lookup"

        # Lowercase, no other lookup signals: semantic
        assert detect_query_intent("heimdex") == "lookup"  # Still short and alnum
        assert detect_query_intent("video editing") == "semantic"

    def test_korean_name_pattern(self):
        """Korean names (2-4 syllables, no spaces) should be lookup."""
        # Valid Korean names
        assert detect_query_intent("이장원") == "lookup"  # 3 syllables
        assert detect_query_intent("김철수") == "lookup"  # 3 syllables
        assert detect_query_intent("홍길동") == "lookup"  # 3 syllables
        assert detect_query_intent("박지성") == "lookup"  # 3 syllables

        # Too short (1 syllable)
        assert detect_query_intent("이") == "semantic"

        # Too long (5+ syllables)
        assert detect_query_intent("이장원입니다") == "semantic"

        # With spaces (not a name)
        assert detect_query_intent("이장원 입니다") == "semantic"

    def test_short_alphanumeric(self):
        """Short alphanumeric queries (1-2 tokens, <= 6 chars) should be lookup."""
        # Short identifiers
        assert detect_query_intent("API") == "lookup"
        assert detect_query_intent("GPU") == "lookup"
        assert detect_query_intent("iOS") == "lookup"
        assert detect_query_intent("AWS") == "lookup"

        # Longer or multi-word: semantic
        assert detect_query_intent("application programming interface") == "semantic"
        assert detect_query_intent("graphics card") == "semantic"

    def test_edge_cases(self):
        """Edge cases and boundary conditions."""
        # Numbers only
        assert detect_query_intent("123") == "lookup"  # Short alnum

        # Special characters
        assert detect_query_intent("C++") == "lookup"  # Short with alnum ratio
        assert detect_query_intent("@username") == "semantic"  # Contains non-alnum

        # Mixed Korean and English
        assert detect_query_intent("BTS 멤버") == "semantic"  # 2 tokens but mixed
        assert detect_query_intent("이장원 interview") == "semantic"  # 2 tokens but mixed


class TestLooksLikeKoreanName:
    """Test suite for Korean name pattern detection."""

    def test_valid_korean_names(self):
        """Valid Korean names (2-4 syllables, no spaces)."""
        assert looks_like_korean_name("이장원") is True
        assert looks_like_korean_name("김철수") is True
        assert looks_like_korean_name("홍길동") is True
        assert looks_like_korean_name("박지성") is True

    def test_invalid_korean_names(self):
        """Invalid patterns that should not be classified as names."""
        # Too short
        assert looks_like_korean_name("이") is False

        # Too long
        assert looks_like_korean_name("이장원입니다") is False

        # With spaces
        assert looks_like_korean_name("이장원 님") is False
        assert looks_like_korean_name("김 철수") is False

        # Mixed characters
        assert looks_like_korean_name("이장원A") is False
        assert looks_like_korean_name("John김") is False

        # Empty or non-Korean
        assert looks_like_korean_name("") is False
        assert looks_like_korean_name("John Smith") is False
        assert looks_like_korean_name("ABC") is False

    def test_boundary_syllable_counts(self):
        """Test boundary cases for syllable count (2-4)."""
        # 2 syllables: valid
        assert looks_like_korean_name("김철") is True

        # 3 syllables: valid
        assert looks_like_korean_name("이장원") is True

        # 4 syllables: valid
        assert looks_like_korean_name("김철수영") is True

        # 1 syllable: invalid
        assert looks_like_korean_name("김") is False

        # 5 syllables: invalid
        assert looks_like_korean_name("김철수영호") is False


class TestIntentDetectionIntegration:
    """Integration-style tests with realistic search scenarios."""

    def test_brand_search_scenarios(self):
        """Realistic brand/product searches."""
        # Tech brands
        assert detect_query_intent("Apple") == "lookup"
        assert detect_query_intent("Google") == "lookup"
        assert detect_query_intent("Microsoft") == "lookup"

        # K-pop groups
        assert detect_query_intent("BTS") == "lookup"
        assert detect_query_intent("BlackPink") == "lookup"
        assert detect_query_intent("NewJeans") == "lookup"

    def test_content_search_scenarios(self):
        """Realistic content description searches."""
        # English content searches
        assert detect_query_intent("funny cat videos") == "semantic"
        assert detect_query_intent("tutorial for beginners") == "semantic"
        assert detect_query_intent("interview with CEO") == "semantic"

        # Korean content searches
        assert detect_query_intent("웃긴 고양이") == "semantic"
        assert detect_query_intent("초보자를 위한") == "semantic"
        assert detect_query_intent("CEO 인터뷰") == "semantic"

    def test_ambiguous_cases(self):
        """Cases that could go either way - verify expected behavior."""
        # Single lowercase word, short: lookup (alphanumeric heuristic)
        assert detect_query_intent("nike") == "lookup"
        assert detect_query_intent("sony") == "lookup"

        # Single lowercase word, longer: semantic
        assert detect_query_intent("tutorial") == "semantic"
        assert detect_query_intent("interview") == "semantic"

        # Two words, no uppercase: semantic
        assert detect_query_intent("funny video") == "semantic"
        assert detect_query_intent("cat moments") == "semantic"
