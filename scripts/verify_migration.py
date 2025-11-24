#!/usr/bin/env python3
"""Verify that the Visual Semantics v2 migration has been applied.

This script checks if the database schema includes the new columns
required for Visual Semantics v2.

Usage:
    python scripts/verify_migration.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
if not env_path.exists():
    print(f"❌ Environment file not found at {env_path}")
    sys.exit(1)

load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
    sys.exit(1)


def verify_migration() -> bool:
    """Verify that the migration has been applied.

    Returns:
        True if migration is applied, False otherwise
    """
    print("=" * 80)
    print("Verifying Visual Semantics v2 Migration")
    print("=" * 80)

    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # Check video_scenes columns
    print("\n[1/2] Checking video_scenes table columns...")

    try:
        # Try to query with new columns
        response = supabase.table("video_scenes").select(
            "visual_description,visual_entities,visual_actions,tags"
        ).limit(1).execute()

        print("✅ All video_scenes columns exist:")
        print("   - visual_description (TEXT)")
        print("   - visual_entities (text[])")
        print("   - visual_actions (text[])")
        print("   - tags (text[])")

    except Exception as e:
        print(f"❌ Missing video_scenes columns: {e}")
        print("\nThe migration has NOT been applied yet.")
        print("Please apply: infra/migrations/009_add_rich_semantics.sql")
        return False

    # Check videos columns
    print("\n[2/2] Checking videos table columns...")

    try:
        # Try to query with new columns
        response = supabase.table("videos").select(
            "video_summary,has_rich_semantics"
        ).limit(1).execute()

        print("✅ All videos columns exist:")
        print("   - video_summary (TEXT)")
        print("   - has_rich_semantics (BOOLEAN)")

    except Exception as e:
        print(f"❌ Missing videos columns: {e}")
        print("\nThe migration has NOT been applied yet.")
        print("Please apply: infra/migrations/009_add_rich_semantics.sql")
        return False

    print("\n" + "=" * 80)
    print("✅ Migration verification PASSED")
    print("=" * 80)
    print("\nAll required columns are present. You can now:")
    print("1. Run the bulk reprocessing script:")
    print("   python scripts/reprocess_all_videos.py --dry-run")
    print("2. Upload new videos to get Visual Semantics v2 automatically")
    print()

    return True


if __name__ == '__main__':
    success = verify_migration()
    sys.exit(0 if success else 1)
