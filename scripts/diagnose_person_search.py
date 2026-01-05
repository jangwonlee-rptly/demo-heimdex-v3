#!/usr/bin/env python3
"""Diagnostic script for person search feature."""
import os
import sys
from supabase import create_client, Client

def main():
    # Get Supabase credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables")
        sys.exit(1)

    # Create Supabase client
    supabase: Client = create_client(supabase_url, supabase_key)

    print("=" * 80)
    print("Person Search Diagnostic Report")
    print("=" * 80)
    print()

    # 1. Check persons table
    print("1. Person Profiles:")
    print("-" * 80)
    persons_response = supabase.table("persons").select("*").execute()
    persons = persons_response.data

    if not persons:
        print("   ❌ No person profiles found in database")
        print()
        print("   ACTION REQUIRED:")
        print("   - Navigate to /people in the frontend")
        print("   - Create a person profile")
        print("   - Upload 3+ reference photos")
        sys.exit(0)

    for person in persons:
        print(f"   Person: {person['display_name']} (ID: {person['id']})")
        print(f"   Status: {person['status']}")
        print(f"   Photos: {person['ready_photos_count']}/{person['total_photos_count']} ready")
        print(f"   Has Query Embedding: {person['has_query_embedding']}")

        if person['query_embedding']:
            embedding_dim = len(person['query_embedding']) if isinstance(person['query_embedding'], list) else 0
            print(f"   Query Embedding Dim: {embedding_dim}")
        else:
            print(f"   Query Embedding: None")

        print()

    # 2. Check person reference photos
    print("2. Reference Photos:")
    print("-" * 80)
    photos_response = supabase.table("person_reference_photos").select("*").execute()
    photos = photos_response.data

    if not photos:
        print("   ❌ No reference photos found")
        print("   ACTION: Upload reference photos for each person")
        print()
    else:
        photo_states = {}
        for photo in photos:
            state = photo['state']
            photo_states[state] = photo_states.get(state, 0) + 1

        print(f"   Total Photos: {len(photos)}")
        for state, count in sorted(photo_states.items()):
            print(f"   {state}: {count} photos")
        print()

        # Show sample photos by person
        from collections import defaultdict
        photos_by_person = defaultdict(list)
        for photo in photos:
            photos_by_person[photo['person_id']].append(photo)

        for person_id, person_photos in photos_by_person.items():
            person = next((p for p in persons if p['id'] == person_id), None)
            person_name = person['display_name'] if person else 'Unknown'

            ready_count = sum(1 for p in person_photos if p['state'] == 'READY')
            failed_count = sum(1 for p in person_photos if p['state'] == 'FAILED')
            processing_count = sum(1 for p in person_photos if p['state'] in ('UPLOADED', 'PROCESSING'))

            print(f"   {person_name}:")
            print(f"     Ready: {ready_count}, Processing: {processing_count}, Failed: {failed_count}")

            if failed_count > 0:
                failed_photos = [p for p in person_photos if p['state'] == 'FAILED']
                for fp in failed_photos[:2]:  # Show first 2 failures
                    print(f"     ❌ Failed: {fp['id']} - {fp.get('error_message', 'No error message')}")

            print()

    # 3. Check video scenes with CLIP embeddings
    print("3. Video Scenes (CLIP Embeddings):")
    print("-" * 80)
    scenes_response = supabase.table("video_scenes").select("id, video_id, visual_clip_embedding").limit(100).execute()
    scenes = scenes_response.data

    if not scenes:
        print("   ❌ No video scenes found")
        print("   ACTION: Upload and process a video")
        print()
    else:
        scenes_with_clip = sum(1 for s in scenes if s.get('visual_clip_embedding') is not None)
        print(f"   Total Scenes (sampled): {len(scenes)}")
        print(f"   Scenes with CLIP embedding: {scenes_with_clip}")
        print(f"   Scenes without CLIP embedding: {len(scenes) - scenes_with_clip}")
        print()

        if scenes_with_clip == 0:
            print("   ❌ WARNING: No scenes have CLIP embeddings!")
            print("   This means visual search (including person search) won't work.")
            print()
            print("   POSSIBLE CAUSES:")
            print("   - Videos were processed before CLIP was enabled")
            print("   - CLIP_ENABLED=false in worker environment")
            print("   - Scene processing failed during CLIP embedding generation")
            print()
            print("   SOLUTION:")
            print("   1. Check worker settings: CLIP_ENABLED=true")
            print("   2. Reprocess existing videos using the 'Reprocess' button")
            print("   3. Or upload a new video to test")
            print()
        elif scenes_with_clip < len(scenes):
            print(f"   ⚠️  WARNING: Only {scenes_with_clip}/{len(scenes)} scenes have CLIP embeddings")
            print("   Some videos may have been processed without CLIP enabled.")
            print()

    # 4. Check search configuration
    print("4. Search Configuration Check:")
    print("-" * 80)

    # Try to make a simple API call to check if person search is enabled
    print("   Backend person search settings (from config.py):")
    print("   - candidate_k_person: 200")
    print("   - threshold_person: 0.3")
    print("   - weight_content_person_search: 0.35")
    print("   - weight_person_person_search: 0.65")
    print()

    # 5. Summary and recommendations
    print("=" * 80)
    print("SUMMARY & RECOMMENDATIONS:")
    print("=" * 80)
    print()

    # Check if person search can work
    has_persons = len(persons) > 0
    has_ready_persons = any(p['has_query_embedding'] for p in persons)
    has_clip_scenes = scenes_with_clip > 0 if scenes else False

    if not has_persons:
        print("❌ BLOCKER: No person profiles found")
        print("   → Create a person profile at /people")
        print()
    elif not has_ready_persons:
        print("❌ BLOCKER: No person profiles have query embeddings yet")
        ready_photo_counts = {p['display_name']: p['ready_photos_count'] for p in persons}
        print(f"   Ready photo counts: {ready_photo_counts}")
        print()
        if all(count == 0 for count in ready_photo_counts.values()):
            print("   → No photos have been processed. Upload reference photos and wait for processing.")
        else:
            print("   → Some photos are ready but query embedding not generated yet.")
            print("   → Check worker logs for embedding aggregation errors.")
        print()
    elif not has_clip_scenes:
        print("❌ BLOCKER: No video scenes have CLIP embeddings")
        print("   → Videos must have CLIP embeddings for person search to work")
        print("   → Reprocess videos or upload new videos with CLIP enabled")
        print()
    else:
        print("✅ All prerequisites met for person search!")
        print()
        print("NEXT STEPS:")
        print("1. Test search with person name at start of query:")
        for person in persons:
            if person['has_query_embedding']:
                print(f"   Example: \"{person['display_name']} presentation\"")
        print()
        print("2. Check frontend console and API logs while searching:")
        print("   Frontend: Look for 'Person detected: <name>' message")
        print("   API logs: docker-compose logs api -f | grep -i person")
        print()
        print("3. If no results, check:")
        print("   - Is the person actually visible in your videos?")
        print("   - Are the reference photos good quality (clear face, well-lit)?")
        print("   - Try lowering threshold_person (currently 0.3) in config.py")
        print()

if __name__ == "__main__":
    main()
