#!/usr/bin/env python3
"""
Debug script to investigate why summary-based search is not working.

This script verifies:
1. Whether scenes have the visual_summary field populated
2. Whether scenes have embedding_summary vectors generated
3. Whether the summary text matches what's displayed in the UI

Usage:
    docker-compose run --rm api python /app/scripts/debug_summary_search.py --summary-text "비디오는 밤의 파리..."
"""
import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "api" / "src"))

from adapters.database import Database
from config import settings


def main():
    parser = argparse.ArgumentParser(description="Debug summary search issue")
    parser.add_argument(
        "--summary-text",
        type=str,
        help="The exact summary text to search for (Korean)",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        help="User ID to filter scenes (optional)",
    )
    parser.add_argument(
        "--video-id",
        type=str,
        help="Video ID to filter scenes (optional)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of scenes to check (default: 10)",
    )
    args = parser.parse_args()

    # Initialize database
    db = Database(settings.supabase_url, settings.supabase_service_key)

    print("=" * 80)
    print("SUMMARY SEARCH DEBUG REPORT")
    print("=" * 80)
    print()

    # Query scenes with visual_summary populated
    print("[1] Checking scene summary data...")
    query = db.client.table("video_scenes").select(
        "id, index, visual_summary, embedding_summary, embedding_version, "
        "transcript_segment, video_id"
    )

    if args.user_id:
        # Need to join with videos table to filter by user
        query = (
            db.client.table("video_scenes")
            .select("*, videos!inner(owner_id)")
            .eq("videos.owner_id", args.user_id)
        )

    if args.video_id:
        query = query.eq("video_id", args.video_id)

    response = query.order("index").limit(args.limit).execute()

    scenes = response.data
    print(f"Found {len(scenes)} scenes")
    print()

    # Statistics
    has_visual_summary = 0
    has_embedding_summary = 0
    has_v3_multi = 0
    exact_match_found = False
    exact_match_scene_id = None

    for scene in scenes:
        visual_summary = scene.get("visual_summary")
        embedding_summary = scene.get("embedding_summary")
        embedding_version = scene.get("embedding_version")

        if visual_summary and visual_summary.strip():
            has_visual_summary += 1

        if embedding_summary is not None:
            has_embedding_summary += 1

        if embedding_version == "v3-multi":
            has_v3_multi += 1

        # Check for exact match
        if args.summary_text and visual_summary:
            if args.summary_text.strip() == visual_summary.strip():
                exact_match_found = True
                exact_match_scene_id = scene.get("id")
                print(f"[EXACT MATCH FOUND] Scene ID: {exact_match_scene_id}")
                print(f"  Scene index: {scene.get('index')}")
                print(f"  Video ID: {scene.get('video_id')}")
                print(f"  Has embedding_summary: {embedding_summary is not None}")
                print(f"  Embedding version: {embedding_version}")
                print(f"  Visual summary (first 100 chars): {visual_summary[:100]}...")
                print()

    print("[2] Summary Statistics:")
    print(f"  Total scenes checked: {len(scenes)}")
    print(f"  Scenes with visual_summary text: {has_visual_summary} ({has_visual_summary/len(scenes)*100:.1f}%)")
    print(f"  Scenes with embedding_summary vector: {has_embedding_summary} ({has_embedding_summary/len(scenes)*100 if scenes else 0:.1f}%)")
    print(f"  Scenes with v3-multi embedding version: {has_v3_multi} ({has_v3_multi/len(scenes)*100 if scenes else 0:.1f}%)")
    print()

    if args.summary_text:
        if exact_match_found:
            print("[3] Exact Match Analysis:")
            print(f"  ✅ Found scene with exact summary match: {exact_match_scene_id}")
            print(f"  ⚠️  Has embedding_summary: {embedding_summary is not None}")
            if embedding_summary is None:
                print("  ❌ ROOT CAUSE: Scene has visual_summary text but NO embedding_summary vector!")
                print("     → Summary weight cannot retrieve this scene (no vector to search)")
        else:
            print("[3] Exact Match Analysis:")
            print(f"  ❌ No scene found with exact summary text match")
            print(f"  Query text (first 100 chars): {args.summary_text[:100]}...")
            print()
            print("  Possible reasons:")
            print("    1. Summary text has different whitespace/normalization")
            print("    2. Summary text was truncated in display")
            print("    3. Wrong user/video filter applied")

    print()
    print("[4] Configuration Check:")
    print(f"  multi_embedding_enabled: {settings.multi_embedding_enabled}")
    print(f"  embedding_summary_enabled: {settings.embedding_summary_enabled}")
    print(f"  embedding_version: {settings.embedding_version}")
    print()

    if not settings.embedding_summary_enabled:
        print("  ❌ CRITICAL: embedding_summary_enabled = False in worker config!")
        print("     → No summary embeddings are being generated during video processing")

    print()
    print("[5] Sample Scene Details:")
    for i, scene in enumerate(scenes[:3], 1):
        print(f"  Scene {i} (index={scene.get('index')}):")
        print(f"    Scene ID: {scene.get('id')}")
        print(f"    Has visual_summary: {bool(scene.get('visual_summary'))}")
        print(f"    Has embedding_summary: {scene.get('embedding_summary') is not None}")
        print(f"    Embedding version: {scene.get('embedding_version')}")
        if scene.get("visual_summary"):
            summary_text = scene.get("visual_summary")
            print(f"    Summary (first 150 chars): {summary_text[:150]}...")
        print()

    print("=" * 80)
    print("END OF REPORT")
    print("=" * 80)


if __name__ == "__main__":
    main()
