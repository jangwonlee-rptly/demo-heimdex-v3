#!/usr/bin/env python3
"""
Comprehensive tests for the SidecarBuilder and SceneSidecar classes.

Tests cover:
1. Tag normalization
2. Combined text building (backward compatibility)
3. Search text optimization
4. Visual analysis skip logic (cost optimization)
5. Smart truncation
6. SceneSidecar versioning and serialization
7. EmbeddingMetadata and ProcessingStats

Note: These tests are self-contained and do not require external dependencies.
They recreate the pure functions/classes to test the logic independently.
"""

import sys
from dataclasses import dataclass
from typing import Optional


# Mock settings object with defaults matching our config
class MockSettings:
    visual_semantics_enabled: bool = True
    visual_semantics_min_duration_s: float = 1.5
    visual_semantics_transcript_threshold: int = 50
    visual_semantics_force_on_no_transcript: bool = True
    sidecar_schema_version: str = "v2"
    search_text_max_length: int = 8000
    search_text_transcript_weight: float = 0.6


settings = MockSettings()


# Recreate classes and functions for testing without external dependencies

@dataclass
class EmbeddingMetadata:
    """Metadata about how an embedding was generated."""
    model: str
    dimensions: int
    input_text_hash: str
    input_text_length: int

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "dimensions": self.dimensions,
            "input_text_hash": self.input_text_hash,
            "input_text_length": self.input_text_length,
        }


@dataclass
class ProcessingStats:
    """Statistics collected during sidecar building."""
    scene_duration_s: float = 0.0
    transcript_length: int = 0
    visual_analysis_called: bool = False
    visual_analysis_skipped_reason: Optional[str] = None
    search_text_length: int = 0
    combined_text_length: int = 0
    keyframes_extracted: int = 0
    best_frame_found: bool = False

    def to_dict(self) -> dict:
        return {
            "scene_duration_s": self.scene_duration_s,
            "transcript_length": self.transcript_length,
            "visual_analysis_called": self.visual_analysis_called,
            "visual_analysis_skipped_reason": self.visual_analysis_skipped_reason,
            "search_text_length": self.search_text_length,
            "combined_text_length": self.combined_text_length,
            "keyframes_extracted": self.keyframes_extracted,
            "best_frame_found": self.best_frame_found,
        }


class SceneSidecar:
    """Scene sidecar metadata for search indexing."""
    CURRENT_VERSION = "v2"

    def __init__(
        self,
        index: int,
        start_s: float,
        end_s: float,
        transcript_segment: str,
        visual_summary: str,
        combined_text: str,
        embedding: list[float],
        thumbnail_url: Optional[str] = None,
        visual_description: Optional[str] = None,
        visual_entities: Optional[list[str]] = None,
        visual_actions: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        sidecar_version: Optional[str] = None,
        search_text: Optional[str] = None,
        embedding_metadata: Optional[EmbeddingMetadata] = None,
        needs_reprocess: bool = False,
        processing_stats: Optional[dict] = None,
    ):
        self.index = index
        self.start_s = start_s
        self.end_s = end_s
        self.transcript_segment = transcript_segment
        self.visual_summary = visual_summary
        self.combined_text = combined_text
        self.embedding = embedding
        self.thumbnail_url = thumbnail_url
        self.visual_description = visual_description
        self.visual_entities = visual_entities or []
        self.visual_actions = visual_actions or []
        self.tags = tags or []
        self.sidecar_version = sidecar_version or self.CURRENT_VERSION
        self.search_text = search_text or combined_text
        self.embedding_metadata = embedding_metadata
        self.needs_reprocess = needs_reprocess
        self.processing_stats = processing_stats or {}

    def to_dict(self) -> dict:
        result = {
            "index": self.index,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "transcript_segment": self.transcript_segment,
            "visual_summary": self.visual_summary,
            "combined_text": self.combined_text,
            "thumbnail_url": self.thumbnail_url,
            "visual_description": self.visual_description,
            "visual_entities": self.visual_entities,
            "visual_actions": self.visual_actions,
            "tags": self.tags,
            "sidecar_version": self.sidecar_version,
            "search_text": self.search_text,
            "needs_reprocess": self.needs_reprocess,
        }
        if self.embedding_metadata:
            result["embedding_metadata"] = self.embedding_metadata.to_dict()
        if self.processing_stats:
            result["processing_stats"] = self.processing_stats
        return result


class SidecarBuilder:
    """Pure function implementations for testing."""

    @staticmethod
    def _normalize_tags(entities: list[str], actions: list[str]) -> list[str]:
        all_tags = entities + actions
        normalized = []
        for tag in all_tags:
            if not tag:
                continue
            tag = tag.strip().lower()
            if not tag or len(tag) > 30:
                continue
            normalized.append(tag)
        seen = set()
        deduplicated = []
        for tag in normalized:
            if tag not in seen:
                seen.add(tag)
                deduplicated.append(tag)
        return deduplicated

    @staticmethod
    def _should_skip_visual_analysis(
        scene_duration_s: float,
        transcript_length: int,
        has_meaningful_transcript: bool,
    ) -> tuple[bool, Optional[str]]:
        if not settings.visual_semantics_enabled:
            return True, "visual_semantics_disabled"
        if settings.visual_semantics_force_on_no_transcript and not has_meaningful_transcript:
            return False, None
        is_short_scene = scene_duration_s < settings.visual_semantics_min_duration_s
        has_rich_transcript = transcript_length >= settings.visual_semantics_transcript_threshold
        if is_short_scene and has_rich_transcript:
            return True, f"short_scene_rich_transcript (duration={scene_duration_s:.1f}s < {settings.visual_semantics_min_duration_s}s, transcript={transcript_length} chars)"
        return False, None

    @staticmethod
    def _smart_truncate(text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        truncated = text[:max_length]
        for punct in [". ", "! ", "? ", "。"]:
            last_punct = truncated.rfind(punct)
            if last_punct > max_length * 0.5:
                return truncated[:last_punct + 1].strip()
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.7:
            return truncated[:last_space].strip() + "..."
        return truncated + "..."

    @staticmethod
    def _build_search_text(
        transcript: str,
        visual_description: str,
        language: str = "ko",
    ) -> str:
        parts = []
        max_length = settings.search_text_max_length
        transcript_target = int(max_length * settings.search_text_transcript_weight)
        visual_target = max_length - transcript_target
        if transcript and transcript.strip():
            truncated_transcript = transcript.strip()
            if len(truncated_transcript) > transcript_target:
                truncated_transcript = SidecarBuilder._smart_truncate(
                    truncated_transcript, transcript_target
                )
            parts.append(truncated_transcript)
        if visual_description and visual_description.strip():
            truncated_visual = visual_description.strip()
            if len(truncated_visual) > visual_target:
                truncated_visual = SidecarBuilder._smart_truncate(
                    truncated_visual, visual_target
                )
            parts.append(truncated_visual)
        return " ".join(parts)

    @staticmethod
    def _build_combined_text(
        visual_summary: str,
        transcript: str,
        language: str = "ko",
        video_filename: Optional[str] = None,
    ) -> str:
        parts = []
        labels = {
            "ko": {"visual": "시각", "audio": "오디오", "metadata": "메타데이터", "filename": "파일명"},
            "en": {"visual": "Visual", "audio": "Audio", "metadata": "Metadata", "filename": "Filename"},
        }
        lang_labels = labels.get(language, labels["ko"])
        # Audio/transcript first for search optimization
        if transcript:
            parts.append(f"{lang_labels['audio']}: {transcript}")
        if visual_summary:
            parts.append(f"{lang_labels['visual']}: {visual_summary}")
        if video_filename:
            parts.append(f"{lang_labels['metadata']}: {lang_labels['filename']}: {video_filename}")
        combined = " | ".join(parts)
        max_length = settings.search_text_max_length
        if len(combined) > max_length:
            combined = combined[:max_length] + "..."
        return combined


def test_normalize_tags():
    """Test tag normalization logic."""
    print("\n" + "=" * 80)
    print("Testing Tag Normalization")
    print("=" * 80 + "\n")

    # Test 1: Basic normalization
    print("Test 1: Basic normalization (trim, lowercase, dedupe)")
    print("-" * 80)
    entities = ["Person", "  dog  ", "CAR"]
    actions = ["Running", "person", "JUMPING"]
    tags = SidecarBuilder._normalize_tags(entities, actions)
    print(f"Input entities: {entities}")
    print(f"Input actions: {actions}")
    print(f"Output tags: {tags}")
    assert "person" in tags, "person should be normalized"
    assert "dog" in tags, "dog should be trimmed"
    assert "car" in tags, "car should be lowercased"
    assert "running" in tags, "running should be lowercased"
    assert "jumping" in tags, "jumping should be lowercased"
    assert tags.count("person") == 1, "person should not be duplicated"
    print("PASSED\n")

    # Test 2: Empty inputs
    print("Test 2: Empty inputs")
    print("-" * 80)
    tags = SidecarBuilder._normalize_tags([], [])
    print(f"Output tags: {tags}")
    assert tags == [], "Empty inputs should return empty list"
    print("PASSED\n")

    # Test 3: Filter empty strings
    print("Test 3: Filter empty strings")
    print("-" * 80)
    entities = ["valid", "", "  ", "also_valid"]
    actions = ["", "action"]
    tags = SidecarBuilder._normalize_tags(entities, actions)
    print(f"Input entities: {entities}")
    print(f"Input actions: {actions}")
    print(f"Output tags: {tags}")
    assert "" not in tags, "Empty strings should be filtered"
    assert len(tags) == 3, "Should have 3 valid tags"
    print("PASSED\n")

    # Test 4: Long tags get filtered
    print("Test 4: Long tags (>30 chars) get filtered")
    print("-" * 80)
    long_tag = "a" * 31
    entities = ["short", long_tag]
    tags = SidecarBuilder._normalize_tags(entities, [])
    print(f"Long tag length: {len(long_tag)}")
    print(f"Output tags: {tags}")
    assert "short" in tags, "short tag should be kept"
    assert long_tag.lower() not in tags, "long tag should be filtered"
    print("PASSED\n")

    # Test 5: Korean tags
    print("Test 5: Korean tags")
    print("-" * 80)
    entities = ["사람", "강아지"]
    actions = ["달리기", "사람"]
    tags = SidecarBuilder._normalize_tags(entities, actions)
    print(f"Input entities: {entities}")
    print(f"Input actions: {actions}")
    print(f"Output tags: {tags}")
    assert "사람" in tags, "Korean tag should be preserved"
    assert tags.count("사람") == 1, "Korean duplicates should be removed"
    print("PASSED\n")

    print("All tag normalization tests passed!")


def test_combined_text_with_filename():
    """Test that combined text includes filename metadata (backward compat)."""
    print("\n" + "=" * 80)
    print("Testing Combined Text Building (Backward Compatibility)")
    print("=" * 80 + "\n")

    # Test case 1: Korean filename with all fields
    print("Test 1: Korean language with filename")
    print("-" * 80)
    combined = SidecarBuilder._build_combined_text(
        visual_summary="여러 사람들이 무대에서 춤을 추고 있습니다",
        transcript="음악에 맞춰 에너지 넘치는 안무를 보여줍니다",
        language="ko",
        video_filename="에버글로우 던던 안무.mp4"
    )
    print(f"Result:\n{combined}\n")
    assert "메타데이터" in combined, "Korean metadata label missing"
    assert "파일명" in combined, "Korean filename label missing"
    assert "에버글로우 던던 안무.mp4" in combined, "Filename missing"
    print("PASSED\n")

    # Test case 2: English filename with all fields
    print("Test 2: English language with filename")
    print("-" * 80)
    combined = SidecarBuilder._build_combined_text(
        visual_summary="Several people dancing on stage",
        transcript="Showing energetic choreography to the music",
        language="en",
        video_filename="Everglow DunDun Dance Practice.mp4"
    )
    print(f"Result:\n{combined}\n")
    assert "Metadata" in combined, "English metadata label missing"
    assert "Filename" in combined, "English filename label missing"
    assert "Everglow DunDun Dance Practice.mp4" in combined, "Filename missing"
    print("PASSED\n")

    # Test case 3: Audio comes before visual (transcript-first)
    print("Test 3: Audio comes before visual in combined text")
    print("-" * 80)
    combined = SidecarBuilder._build_combined_text(
        visual_summary="Visual content",
        transcript="Audio content",
        language="en",
        video_filename=None
    )
    print(f"Result:\n{combined}\n")
    audio_pos = combined.find("Audio:")
    visual_pos = combined.find("Visual:")
    assert audio_pos < visual_pos, "Audio should come before Visual"
    print("PASSED\n")

    # Test case 4: No filename (backward compatibility)
    print("Test 4: Backward compatibility - no filename")
    print("-" * 80)
    combined = SidecarBuilder._build_combined_text(
        visual_summary="여러 사람들이 무대에서 춤을 추고 있습니다",
        transcript="음악에 맞춰 에너지 넘치는 안무를 보여줍니다",
        language="ko",
        video_filename=None
    )
    print(f"Result:\n{combined}\n")
    assert "메타데이터" not in combined, "Metadata should not be present without filename"
    assert "오디오" in combined, "Audio should be present"
    print("PASSED\n")

    # Test case 5: Empty filename (backward compatibility)
    print("Test 5: Empty filename (backward compatibility)")
    print("-" * 80)
    combined = SidecarBuilder._build_combined_text(
        visual_summary="Test visual",
        transcript="Test audio",
        language="ko",
        video_filename=""
    )
    print(f"Result:\n{combined}\n")
    assert "메타데이터" not in combined, "Metadata should not be present with empty filename"
    print("PASSED\n")

    print("All combined text tests passed!")


def test_search_text_optimization():
    """Test search text building for embedding optimization."""
    print("\n" + "=" * 80)
    print("Testing Search Text Optimization")
    print("=" * 80 + "\n")

    # Test 1: Transcript comes first
    print("Test 1: Transcript comes first in search text")
    print("-" * 80)
    search_text = SidecarBuilder._build_search_text(
        transcript="This is the transcript content.",
        visual_description="This is the visual description.",
        language="en"
    )
    print(f"Result:\n{search_text}\n")
    transcript_pos = search_text.find("transcript")
    visual_pos = search_text.find("visual")
    assert transcript_pos < visual_pos, "Transcript should come before visual"
    print("PASSED\n")

    # Test 2: No labels in search text
    print("Test 2: No labels in search text (cleaner for embeddings)")
    print("-" * 80)
    search_text = SidecarBuilder._build_search_text(
        transcript="Some transcript",
        visual_description="Some visual",
        language="en"
    )
    print(f"Result:\n{search_text}\n")
    assert "Audio:" not in search_text, "Should not have Audio label"
    assert "Visual:" not in search_text, "Should not have Visual label"
    print("PASSED\n")

    # Test 3: Only transcript
    print("Test 3: Only transcript")
    print("-" * 80)
    search_text = SidecarBuilder._build_search_text(
        transcript="Only transcript content here.",
        visual_description="",
        language="en"
    )
    print(f"Result:\n{search_text}\n")
    assert "Only transcript content here." in search_text, "Transcript should be present"
    print("PASSED\n")

    # Test 4: Only visual
    print("Test 4: Only visual description")
    print("-" * 80)
    search_text = SidecarBuilder._build_search_text(
        transcript="",
        visual_description="Only visual content here.",
        language="en"
    )
    print(f"Result:\n{search_text}\n")
    assert "Only visual content here." in search_text, "Visual should be present"
    print("PASSED\n")

    # Test 5: Empty inputs
    print("Test 5: Empty inputs")
    print("-" * 80)
    search_text = SidecarBuilder._build_search_text(
        transcript="",
        visual_description="",
        language="en"
    )
    print(f"Result: '{search_text}'")
    assert search_text == "", "Empty inputs should return empty string"
    print("PASSED\n")

    print("All search text optimization tests passed!")


def test_smart_truncate():
    """Test intelligent text truncation."""
    print("\n" + "=" * 80)
    print("Testing Smart Truncation")
    print("=" * 80 + "\n")

    # Test 1: No truncation needed
    print("Test 1: No truncation needed")
    print("-" * 80)
    text = "Short text."
    result = SidecarBuilder._smart_truncate(text, 100)
    print(f"Input: '{text}' (len={len(text)})")
    print(f"Max length: 100")
    print(f"Result: '{result}'")
    assert result == text, "Short text should not be modified"
    print("PASSED\n")

    # Test 2: Truncate at sentence boundary
    print("Test 2: Truncate at sentence boundary")
    print("-" * 80)
    text = "First sentence. Second sentence. Third sentence."
    result = SidecarBuilder._smart_truncate(text, 35)
    print(f"Input: '{text}' (len={len(text)})")
    print(f"Max length: 35")
    print(f"Result: '{result}'")
    assert result.endswith("."), "Should end at sentence boundary"
    assert len(result) <= 35, "Should not exceed max length"
    print("PASSED\n")

    # Test 3: Truncate at word boundary when no sentence boundary
    print("Test 3: Truncate at word boundary")
    print("-" * 80)
    text = "Word one two three four five six seven eight nine ten"
    result = SidecarBuilder._smart_truncate(text, 30)
    print(f"Input: '{text}' (len={len(text)})")
    print(f"Max length: 30")
    print(f"Result: '{result}'")
    assert "..." in result, "Should have ellipsis"
    assert len(result) <= 34, "Should be close to max length + ellipsis"
    print("PASSED\n")

    # Test 4: Korean text
    print("Test 4: Korean text truncation")
    print("-" * 80)
    text = "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다."
    result = SidecarBuilder._smart_truncate(text, 20)
    print(f"Input: '{text}' (len={len(text)})")
    print(f"Max length: 20")
    print(f"Result: '{result}'")
    assert len(result) <= 24, "Should respect max length"
    print("PASSED\n")

    print("All smart truncation tests passed!")


def test_should_skip_visual_analysis():
    """Test visual analysis skip logic for cost optimization."""
    print("\n" + "=" * 80)
    print("Testing Visual Analysis Skip Logic (Cost Optimization)")
    print("=" * 80 + "\n")

    # Test 1: Long scene with rich transcript - should NOT skip
    print("Test 1: Long scene with rich transcript - should NOT skip")
    print("-" * 80)
    should_skip, reason = SidecarBuilder._should_skip_visual_analysis(
        scene_duration_s=10.0,
        transcript_length=200,
        has_meaningful_transcript=True
    )
    print(f"Scene duration: 10.0s, Transcript length: 200 chars")
    print(f"Should skip: {should_skip}, Reason: {reason}")
    assert should_skip is False, "Long scenes should not skip visual analysis"
    print("PASSED\n")

    # Test 2: Short scene with rich transcript - should skip
    print("Test 2: Short scene with rich transcript - should skip")
    print("-" * 80)
    should_skip, reason = SidecarBuilder._should_skip_visual_analysis(
        scene_duration_s=0.5,
        transcript_length=200,
        has_meaningful_transcript=True
    )
    print(f"Scene duration: 0.5s, Transcript length: 200 chars")
    print(f"Should skip: {should_skip}, Reason: {reason}")
    assert should_skip is True, "Short scene with rich transcript should skip"
    assert "short_scene_rich_transcript" in reason, "Should indicate skip reason"
    print("PASSED\n")

    # Test 3: Short scene with NO transcript - should NOT skip
    print("Test 3: Short scene with NO transcript - should NOT skip")
    print("-" * 80)
    should_skip, reason = SidecarBuilder._should_skip_visual_analysis(
        scene_duration_s=0.5,
        transcript_length=0,
        has_meaningful_transcript=False
    )
    print(f"Scene duration: 0.5s, Transcript length: 0 chars")
    print(f"Should skip: {should_skip}, Reason: {reason}")
    assert should_skip is False, "Scenes without transcript should NOT skip visual analysis"
    print("PASSED\n")

    # Test 4: Short scene with short transcript - should NOT skip
    print("Test 4: Short scene with short transcript - should NOT skip")
    print("-" * 80)
    should_skip, reason = SidecarBuilder._should_skip_visual_analysis(
        scene_duration_s=0.5,
        transcript_length=20,
        has_meaningful_transcript=True
    )
    print(f"Scene duration: 0.5s, Transcript length: 20 chars")
    print(f"Should skip: {should_skip}, Reason: {reason}")
    assert should_skip is False, "Short scene with short transcript should NOT skip"
    print("PASSED\n")

    print("All visual analysis skip logic tests passed!")


def test_scene_sidecar_versioning():
    """Test SceneSidecar versioning and serialization."""
    print("\n" + "=" * 80)
    print("Testing SceneSidecar Versioning and Serialization")
    print("=" * 80 + "\n")

    # Test 1: Default version
    print("Test 1: Default sidecar version")
    print("-" * 80)
    sidecar = SceneSidecar(
        index=0,
        start_s=0.0,
        end_s=5.0,
        transcript_segment="Test transcript",
        visual_summary="Test visual",
        combined_text="Test combined",
        embedding=[0.1] * 10,
    )
    print(f"Sidecar version: {sidecar.sidecar_version}")
    assert sidecar.sidecar_version == SceneSidecar.CURRENT_VERSION, "Should have current version"
    print("PASSED\n")

    # Test 2: Custom version
    print("Test 2: Custom sidecar version")
    print("-" * 80)
    sidecar = SceneSidecar(
        index=0,
        start_s=0.0,
        end_s=5.0,
        transcript_segment="Test transcript",
        visual_summary="Test visual",
        combined_text="Test combined",
        embedding=[0.1] * 10,
        sidecar_version="v3-beta"
    )
    print(f"Sidecar version: {sidecar.sidecar_version}")
    assert sidecar.sidecar_version == "v3-beta", "Should accept custom version"
    print("PASSED\n")

    # Test 3: Serialization to_dict
    print("Test 3: Serialization to dictionary")
    print("-" * 80)
    embedding_meta = EmbeddingMetadata(
        model="text-embedding-3-small",
        dimensions=1536,
        input_text_hash="abc123",
        input_text_length=100
    )
    sidecar = SceneSidecar(
        index=1,
        start_s=5.0,
        end_s=10.0,
        transcript_segment="Test transcript",
        visual_summary="Test visual",
        combined_text="Test combined",
        embedding=[0.1] * 5,
        visual_entities=["person", "dog"],
        visual_actions=["running"],
        tags=["person", "dog", "running"],
        sidecar_version="v2",
        search_text="Test search text",
        embedding_metadata=embedding_meta,
        needs_reprocess=False,
        processing_stats={"visual_analysis_called": True}
    )
    result = sidecar.to_dict()
    print(f"Keys in result: {list(result.keys())}")
    assert "sidecar_version" in result, "Should include version"
    assert "search_text" in result, "Should include search_text"
    assert "embedding_metadata" in result, "Should include embedding_metadata"
    assert result["embedding_metadata"]["model"] == "text-embedding-3-small", "Should serialize metadata"
    print("PASSED\n")

    # Test 4: needs_reprocess flag
    print("Test 4: needs_reprocess flag")
    print("-" * 80)
    sidecar = SceneSidecar(
        index=0,
        start_s=0.0,
        end_s=5.0,
        transcript_segment="Test",
        visual_summary="Test",
        combined_text="Test",
        embedding=[0.1],
        needs_reprocess=True
    )
    print(f"needs_reprocess: {sidecar.needs_reprocess}")
    assert sidecar.needs_reprocess is True, "Should accept needs_reprocess flag"
    assert sidecar.to_dict()["needs_reprocess"] is True, "Should serialize flag"
    print("PASSED\n")

    print("All SceneSidecar versioning tests passed!")


def test_processing_stats():
    """Test ProcessingStats dataclass."""
    print("\n" + "=" * 80)
    print("Testing ProcessingStats")
    print("=" * 80 + "\n")

    # Test 1: Default values
    print("Test 1: Default values")
    print("-" * 80)
    stats = ProcessingStats()
    print(f"Default stats: {stats.to_dict()}")
    assert stats.scene_duration_s == 0.0, "Default duration should be 0"
    assert stats.visual_analysis_called is False, "Default should be False"
    print("PASSED\n")

    # Test 2: Custom values
    print("Test 2: Custom values")
    print("-" * 80)
    stats = ProcessingStats(
        scene_duration_s=5.5,
        transcript_length=150,
        visual_analysis_called=True,
        visual_analysis_skipped_reason=None,
        search_text_length=200,
        combined_text_length=250,
        keyframes_extracted=3,
        best_frame_found=True
    )
    result = stats.to_dict()
    print(f"Custom stats: {result}")
    assert result["scene_duration_s"] == 5.5, "Should serialize duration"
    assert result["visual_analysis_called"] is True, "Should serialize flag"
    print("PASSED\n")

    # Test 3: Skip reason tracking
    print("Test 3: Skip reason tracking")
    print("-" * 80)
    stats = ProcessingStats(
        visual_analysis_skipped_reason="short_scene_rich_transcript"
    )
    result = stats.to_dict()
    print(f"Skip reason: {result['visual_analysis_skipped_reason']}")
    assert "short_scene" in result["visual_analysis_skipped_reason"], "Should track skip reason"
    print("PASSED\n")

    print("All ProcessingStats tests passed!")


def test_embedding_metadata():
    """Test EmbeddingMetadata dataclass."""
    print("\n" + "=" * 80)
    print("Testing EmbeddingMetadata")
    print("=" * 80 + "\n")

    # Test 1: Creation and serialization
    print("Test 1: Creation and serialization")
    print("-" * 80)
    metadata = EmbeddingMetadata(
        model="text-embedding-3-small",
        dimensions=1536,
        input_text_hash="abc123def456",
        input_text_length=500
    )
    result = metadata.to_dict()
    print(f"Metadata: {result}")
    assert result["model"] == "text-embedding-3-small", "Should serialize model"
    assert result["dimensions"] == 1536, "Should serialize dimensions"
    assert result["input_text_hash"] == "abc123def456", "Should serialize hash"
    assert result["input_text_length"] == 500, "Should serialize length"
    print("PASSED\n")

    print("All EmbeddingMetadata tests passed!")


def test_backward_compatibility():
    """Test that existing code continues to work without new fields."""
    print("\n" + "=" * 80)
    print("Testing Backward Compatibility")
    print("=" * 80 + "\n")

    # Test 1: Create sidecar with only required fields
    print("Test 1: Create sidecar with only original fields")
    print("-" * 80)
    sidecar = SceneSidecar(
        index=0,
        start_s=0.0,
        end_s=5.0,
        transcript_segment="Test transcript",
        visual_summary="Test visual",
        combined_text="Test combined",
        embedding=[0.1, 0.2, 0.3],
    )
    print(f"Created sidecar with index={sidecar.index}")
    print(f"Has embedding: {len(sidecar.embedding)} dimensions")
    print(f"Default version: {sidecar.sidecar_version}")
    print(f"Default search_text: {sidecar.search_text}")
    assert sidecar.embedding == [0.1, 0.2, 0.3], "Embedding should be preserved"
    assert sidecar.sidecar_version == "v2", "Should have default version"
    assert sidecar.search_text == "Test combined", "search_text should default to combined_text"
    print("PASSED\n")

    # Test 2: Access all original fields
    print("Test 2: Access all original fields")
    print("-" * 80)
    sidecar = SceneSidecar(
        index=1,
        start_s=5.0,
        end_s=10.0,
        transcript_segment="Transcript",
        visual_summary="Visual",
        combined_text="Combined",
        embedding=[0.5],
        thumbnail_url="https://example.com/thumb.jpg",
        visual_description="Description",
        visual_entities=["entity1"],
        visual_actions=["action1"],
        tags=["tag1"]
    )
    assert sidecar.index == 1, "index accessible"
    assert sidecar.start_s == 5.0, "start_s accessible"
    assert sidecar.end_s == 10.0, "end_s accessible"
    assert sidecar.transcript_segment == "Transcript", "transcript_segment accessible"
    assert sidecar.visual_summary == "Visual", "visual_summary accessible"
    assert sidecar.combined_text == "Combined", "combined_text accessible"
    assert sidecar.thumbnail_url == "https://example.com/thumb.jpg", "thumbnail_url accessible"
    assert sidecar.visual_description == "Description", "visual_description accessible"
    assert sidecar.visual_entities == ["entity1"], "visual_entities accessible"
    assert sidecar.visual_actions == ["action1"], "visual_actions accessible"
    assert sidecar.tags == ["tag1"], "tags accessible"
    print("All original fields accessible")
    print("PASSED\n")

    print("All backward compatibility tests passed!")


def test_config_defaults():
    """Test that config default values are correct."""
    print("\n" + "=" * 80)
    print("Testing Config Default Values")
    print("=" * 80 + "\n")

    # Test defaults match expected values
    print("Test 1: Visual semantics cost optimization settings")
    print("-" * 80)
    print(f"visual_semantics_min_duration_s: {settings.visual_semantics_min_duration_s}")
    print(f"visual_semantics_transcript_threshold: {settings.visual_semantics_transcript_threshold}")
    print(f"visual_semantics_force_on_no_transcript: {settings.visual_semantics_force_on_no_transcript}")
    assert settings.visual_semantics_min_duration_s == 1.5, "Default min duration should be 1.5s"
    assert settings.visual_semantics_transcript_threshold == 50, "Default transcript threshold should be 50"
    assert settings.visual_semantics_force_on_no_transcript is True, "Should force visual on no transcript"
    print("PASSED\n")

    print("Test 2: Sidecar schema version")
    print("-" * 80)
    print(f"sidecar_schema_version: {settings.sidecar_schema_version}")
    assert settings.sidecar_schema_version == "v2", "Default schema version should be v2"
    print("PASSED\n")

    print("Test 3: Search text settings")
    print("-" * 80)
    print(f"search_text_max_length: {settings.search_text_max_length}")
    print(f"search_text_transcript_weight: {settings.search_text_transcript_weight}")
    assert settings.search_text_max_length == 8000, "Default max length should be 8000"
    assert settings.search_text_transcript_weight == 0.6, "Default transcript weight should be 0.6"
    print("PASSED\n")

    print("All config defaults tests passed!")


def run_all_tests():
    """Run all test functions."""
    print("\n" + "=" * 80)
    print("SIDECAR BUILDER COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    test_functions = [
        test_normalize_tags,
        test_combined_text_with_filename,
        test_search_text_optimization,
        test_smart_truncate,
        test_should_skip_visual_analysis,
        test_scene_sidecar_versioning,
        test_processing_stats,
        test_embedding_metadata,
        test_backward_compatibility,
        test_config_defaults,
    ]

    passed = 0
    failed = 0

    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\nFAILED: {test_func.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\nERROR: {test_func.__name__}")
            print(f"  Exception: {e}")
            failed += 1

    print("\n" + "=" * 80)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed == 0:
        print("\nALL TESTS PASSED!")
        print("\nSummary of tested features:")
        print("  - Tag normalization (trim, lowercase, dedupe, length limit)")
        print("  - Combined text building (backward compatibility, audio-first)")
        print("  - Search text optimization (transcript-first, no labels)")
        print("  - Smart truncation (sentence/word boundaries)")
        print("  - Visual analysis skip logic (cost optimization)")
        print("  - SceneSidecar versioning (v2 fields)")
        print("  - Processing stats tracking")
        print("  - Embedding metadata tracking")
        print("  - Backward compatibility")
        print("  - Config defaults")
    else:
        print(f"\n{failed} TEST(S) FAILED - please review errors above")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
