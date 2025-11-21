#!/usr/bin/env python3
"""
Test script to verify metadata-aware search implementation.
Tests that filenames are correctly included in combined text.
"""

from src.domain.sidecar_builder import SidecarBuilder


def test_combined_text_with_filename():
    """Test that combined text includes filename metadata."""

    print("\n" + "=" * 80)
    print("Testing Metadata-Aware Search Implementation")
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
    print("✅ PASSED\n")

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
    print("✅ PASSED\n")

    # Test case 3: Korean with filename only (no visual/audio)
    print("Test 3: Korean with only filename (no visual/audio)")
    print("-" * 80)
    combined = SidecarBuilder._build_combined_text(
        visual_summary="",
        transcript="",
        language="ko",
        video_filename="에버글로우 던던 안무.mp4"
    )
    print(f"Result:\n{combined}\n")
    assert "메타데이터" in combined, "Metadata should be present"
    assert "에버글로우 던던 안무.mp4" in combined, "Filename should be present"
    assert "시각" not in combined, "Visual label should not be present"
    assert "오디오" not in combined, "Audio label should not be present"
    print("✅ PASSED\n")

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
    assert "시각" in combined, "Visual should be present"
    assert "오디오" in combined, "Audio should be present"
    print("✅ PASSED\n")

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
    print("✅ PASSED\n")

    # Test case 6: Verify proper formatting with all three sections
    print("Test 6: Verify proper formatting with all sections")
    print("-" * 80)
    combined = SidecarBuilder._build_combined_text(
        visual_summary="Visual content",
        transcript="Audio content",
        language="en",
        video_filename="test_video.mp4"
    )
    print(f"Result:\n{combined}\n")
    parts = combined.split(" | ")
    assert len(parts) == 3, f"Expected 3 parts, got {len(parts)}"
    assert parts[0].startswith("Visual:"), "First part should be visual"
    assert parts[1].startswith("Audio:"), "Second part should be audio"
    assert parts[2].startswith("Metadata:"), "Third part should be metadata"
    print("✅ PASSED\n")

    print("=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print("\n📋 Summary:")
    print("  • Filenames are correctly included in combined text")
    print("  • Korean and English labels work correctly")
    print("  • Backward compatibility maintained (filename is optional)")
    print("  • Format: 'Metadata: Filename: <filename>' or '메타데이터: 파일명: <filename>'")
    print("  • Proper ordering: Visual | Audio | Metadata")
    print("\n")


if __name__ == "__main__":
    test_combined_text_with_filename()
