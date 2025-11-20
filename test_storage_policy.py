#!/usr/bin/env python3
"""Test if storage policies are correctly configured."""
import os
import sys

# Add the API source to path
sys.path.insert(0, 'services/api/src')

from supabase import create_client

# Load env manually
env_path = '.env'
supabase_url = None
anon_key = None
service_key = None

with open(env_path, 'r') as f:
    for line in f:
        if line.startswith('SUPABASE_URL='):
            supabase_url = line.split('=', 1)[1].strip()
        elif line.startswith('SUPABASE_ANON_KEY='):
            anon_key = line.split('=', 1)[1].strip()
        elif line.startswith('SUPABASE_SERVICE_ROLE_KEY='):
            service_key = line.split('=', 1)[1].strip()

print(f"🔗 Connecting to: {supabase_url}\n")

# Test 1: Service role upload (should work)
print("✅ Test 1: Service role upload (should always work)")
service_client = create_client(supabase_url, service_key)
try:
    result = service_client.storage.from_('videos').upload(
        path='test/service-test.txt',
        file=b'service role test',
        file_options={'content-type': 'text/plain', 'upsert': True}
    )
    print(f"  ✅ SUCCESS: {result}")
    service_client.storage.from_('videos').remove(['test/service-test.txt'])
except Exception as e:
    print(f"  ❌ FAILED: {e}")

# Test 2: Anon key upload (will fail without policies)
print("\n❌ Test 2: Anon key upload to user folder (requires policies)")
anon_client = create_client(supabase_url, anon_key)
try:
    # Simulate a user upload - this will fail if policies aren't set
    result = anon_client.storage.from_('videos').upload(
        path='799f1283-a2d7-4f8a-96e6-faf71a749b64/test.txt',
        file=b'anon test',
        file_options={'content-type': 'text/plain', 'upsert': True}
    )
    print(f"  ✅ SUCCESS: {result}")
    print("  ✅ Policies are configured correctly!")
except Exception as e:
    print(f"  ❌ FAILED: {e}")
    print("\n🚨 STORAGE POLICIES ARE MISSING!")
    print("\nYou need to add policies in Supabase Dashboard:")
    print("1. Go to: https://supabase.com/dashboard/project/oxmfngfqmedbzgknyijj/storage/policies")
    print("2. Click 'New Policy' on the 'videos' bucket")
    print("3. Add INSERT policy:")
    print("   (bucket_id = 'videos'::text) AND ((storage.foldername(name))[1] = (auth.uid())::text)")
    print("4. Add SELECT policy:")
    print("   (bucket_id = 'videos'::text) AND ((storage.foldername(name))[1] = (auth.uid())::text)")

print("\n" + "="*60)
