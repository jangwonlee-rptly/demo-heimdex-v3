"""
Diagnostic script to check thumbnail status for videos.

Usage:
    python -m src.scripts.check_thumbnails
"""
import logging
from uuid import UUID
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.adapters.database import db
from src.adapters.supabase import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_video_thumbnails():
    """Check thumbnail status for all videos."""

    print("\n" + "="*80)
    print("THUMBNAIL DIAGNOSTIC REPORT")
    print("="*80 + "\n")

    # Get all videos (you'll need to implement get_all_videos or pass a user_id)
    # For now, let's check using SQL directly

    videos_response = db.client.table("videos").select("*").execute()
    videos = videos_response.data

    print(f"Found {len(videos)} videos\n")

    for video in videos:
        video_id = video['id']
        print(f"\n📹 Video: {video_id}")
        print(f"   Status: {video['status']}")
        print(f"   Thumbnail URL: {video.get('thumbnail_url', 'MISSING')}")

        # Check scenes
        scenes_response = db.client.table("video_scenes").select("id, index, thumbnail_url").eq("video_id", video_id).execute()
        scenes = scenes_response.data

        print(f"   Scenes: {len(scenes)}")

        if scenes:
            scenes_with_thumbnails = [s for s in scenes if s.get('thumbnail_url')]
            print(f"   Scenes with thumbnails: {len(scenes_with_thumbnails)}/{len(scenes)}")

            # Check if thumbnails are accessible
            if scenes_with_thumbnails:
                first_thumbnail = scenes_with_thumbnails[0]['thumbnail_url']
                print(f"   Sample thumbnail: {first_thumbnail[:100]}...")
        else:
            print(f"   ⚠️  No scenes found for this video")

    print("\n" + "="*80)
    print("RECOMMENDATIONS:")
    print("="*80)
    print("""
    If thumbnails are MISSING:
    1. Check worker logs during video processing
    2. Verify Supabase storage bucket 'videos' exists and is public
    3. Check storage permissions (service role should have upload access)
    4. Reprocess video: POST /videos/{video_id}/process

    If thumbnails exist but don't display:
    1. Check CORS settings on Supabase storage
    2. Verify bucket is set to public
    3. Check thumbnail URLs are accessible in browser
    """)
    print("="*80 + "\n")


if __name__ == "__main__":
    check_video_thumbnails()
