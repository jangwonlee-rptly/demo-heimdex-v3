#!/usr/bin/env python3
"""Test script to check Supabase storage configuration."""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Get Supabase credentials
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    exit(1)

print(f"🔗 Connecting to Supabase: {supabase_url}")

# Create client
client: Client = create_client(supabase_url, supabase_key)

# List all buckets
print("\n📦 Listing all storage buckets:")
try:
    buckets = client.storage.list_buckets()
    if buckets:
        for bucket in buckets:
            print(f"  - {bucket['name']}: public={bucket.get('public', False)}, id={bucket.get('id', 'N/A')}")
    else:
        print("  No buckets found!")
except Exception as e:
    print(f"  ❌ Error listing buckets: {e}")

# Check if 'videos' bucket exists
print("\n🎬 Checking 'videos' bucket:")
try:
    # Try to list files in videos bucket
    result = client.storage.from_('videos').list()
    print(f"  ✅ 'videos' bucket exists! Contains {len(result)} items at root level")

    # Get bucket details
    buckets = client.storage.list_buckets()
    videos_bucket = next((b for b in buckets if b['name'] == 'videos'), None)
    if videos_bucket:
        print(f"  - Public: {videos_bucket.get('public', False)}")
        print(f"  - File size limit: {videos_bucket.get('file_size_limit', 'None')}")
        print(f"  - Allowed MIME types: {videos_bucket.get('allowed_mime_types', 'All')}")
except Exception as e:
    print(f"  ❌ Error accessing 'videos' bucket: {e}")
    print("\n💡 The bucket might not exist. Creating it...")

    try:
        # Try to create the bucket
        client.storage.create_bucket(
            'videos',
            options={'public': False}  # Private bucket
        )
        print("  ✅ Created 'videos' bucket!")
    except Exception as create_error:
        print(f"  ❌ Error creating bucket: {create_error}")

print("\n✨ Done!")
