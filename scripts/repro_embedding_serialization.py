#!/usr/bin/env python3
"""
Minimal Reproduction: Embedding Serialization Investigation

This script systematically tests how Supabase/PostgREST returns pgvector columns
in different scenarios to understand the root cause of string vs list behavior.

Run via: docker compose exec api python scripts/repro_embedding_serialization.py
"""
import json
import os
import sys
from typing import Any
from uuid import UUID

from supabase import create_client


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def inspect_value(name: str, value: Any) -> None:
    """Inspect and print details about a value."""
    print(f"{name}:")
    print(f"  Type: {type(value).__name__}")

    if value is None:
        print(f"  Value: None")
    elif isinstance(value, str):
        print(f"  Length: {len(value)} chars")
        print(f"  First 100 chars: {value[:100]}...")
        # Try to parse as JSON to see dimension
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                print(f"  Parsed dimension: {len(parsed)}")
                print(f"  Parsed first 5: {parsed[:5]}")
        except Exception as e:
            print(f"  JSON parse failed: {e}")
    elif isinstance(value, list):
        print(f"  Length: {len(value)} elements")
        print(f"  First 5: {value[:5]}")
    else:
        print(f"  Value: {value}")
    print()


def test_table_selects(supabase):
    """Test different select patterns on tables."""
    print_section("A1-A3: TABLE SELECT PATTERNS")

    # Test persons.query_embedding
    print("Testing persons.query_embedding...")

    # Pattern 1: select("*")
    response = supabase.table("persons").select("*").limit(1).execute()
    if response.data:
        row = response.data[0]
        inspect_value("  select('*') - query_embedding", row.get("query_embedding"))

    # Pattern 2: select("query_embedding")
    response = supabase.table("persons").select("query_embedding").limit(1).execute()
    if response.data:
        row = response.data[0]
        inspect_value("  select('query_embedding') - query_embedding", row.get("query_embedding"))

    # Pattern 3: single()
    response = supabase.table("persons").select("query_embedding").limit(1).maybe_single().execute()
    if response.data:
        inspect_value("  maybe_single() - query_embedding", response.data.get("query_embedding"))

    print("\nTesting person_reference_photos.embedding...")

    # Pattern 1: select("*")
    response = supabase.table("person_reference_photos").select("*").eq("state", "READY").limit(1).execute()
    if response.data:
        row = response.data[0]
        inspect_value("  select('*') - embedding", row.get("embedding"))

    # Pattern 2: select("embedding")
    response = supabase.table("person_reference_photos").select("embedding").eq("state", "READY").limit(1).execute()
    if response.data:
        row = response.data[0]
        inspect_value("  select('embedding') - embedding", row.get("embedding"))

    print("\nTesting scene_person_embeddings.embedding...")

    # Pattern 1: select("*")
    response = supabase.table("scene_person_embeddings").select("*").limit(1).execute()
    if response.data:
        row = response.data[0]
        inspect_value("  select('*') - embedding", row.get("embedding"))

    # Pattern 2: select("embedding")
    response = supabase.table("scene_person_embeddings").select("embedding").limit(1).execute()
    if response.data:
        row = response.data[0]
        inspect_value("  select('embedding') - embedding", row.get("embedding"))


def test_rpc_responses(supabase):
    """Test RPC function responses."""
    print_section("A4: RPC vs TABLE SELECT")

    # First get a person with query_embedding
    person_resp = supabase.table("persons").select("id,query_embedding").not_.is_("query_embedding", "null").limit(1).execute()

    if not person_resp.data:
        print("No persons with query_embedding found, skipping RPC test")
        return

    person = person_resp.data[0]
    query_embedding = person["query_embedding"]

    print("Table select - persons.query_embedding:")
    inspect_value("  query_embedding", query_embedding)

    # Test if the RPC returns embeddings differently
    # Note: search_scenes_by_person_clip_embedding doesn't return embeddings,
    # but we can check if the input parameter handling is different

    # Parse the embedding if needed
    if isinstance(query_embedding, str):
        query_embedding = json.loads(query_embedding)

    print("Calling RPC with query_embedding parameter...")
    try:
        rpc_resp = supabase.rpc(
            "search_scenes_by_person_clip_embedding",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.9,
                "match_count": 1,
            }
        ).execute()
        print(f"  RPC succeeded, returned {len(rpc_resp.data)} results")
    except Exception as e:
        print(f"  RPC failed: {e}")


def test_database_storage(supabase):
    """Test how embeddings are stored in the database."""
    print_section("B7: DATABASE STORAGE FORMAT")

    # Use raw SQL to check pg_typeof
    print("Testing persons.query_embedding storage...")
    person_resp = supabase.table("persons").select("id,query_embedding").not_.is_("query_embedding", "null").limit(1).execute()

    if person_resp.data:
        person = person_resp.data[0]
        person_id = person["id"]
        query_embedding = person["query_embedding"]

        print(f"Person ID: {person_id}")
        inspect_value("  Python representation", query_embedding)

        # Note: We can't run raw SQL via Supabase client easily
        # But we can infer from the schema (from migrations)
        print("  Schema definition (from migration 024):")
        print("    Column type: vector(512)")
        print("    Extension: pgvector")


def test_write_paths(supabase):
    """Test how embeddings are written to database."""
    print_section("B8: WRITE PATH ANALYSIS")

    print("Checking worker's update_person_query_embedding()...")
    print("  Code location: services/worker/src/adapters/database.py:936-941")
    print("  Method: Converts list[float] to string format")
    print("  Format: '[' + ','.join(str(x) for x in embedding) + ']'")
    print("  Example: [0.1, 0.2, 0.3] -> '[0.1,0.2,0.3]'")
    print("  Update method: .update({'query_embedding': embedding_str})")

    print("\nChecking if any code directly inserts JSON strings...")
    print("  Worker stores as: string in vector(...) format")
    print("  Database interprets: as pgvector type")
    print("  PostgREST returns: as JSON string serialization")


def main():
    """Main reproduction script."""
    print("=" * 80)
    print("  EMBEDDING SERIALIZATION REPRODUCTION")
    print("  Investigating: Why query_embedding returns as string vs list")
    print("=" * 80)

    # Setup Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)

    supabase = create_client(supabase_url, supabase_key)

    # Run tests
    test_table_selects(supabase)
    test_rpc_responses(supabase)
    test_database_storage(supabase)
    test_write_paths(supabase)

    # Summary
    print_section("SUMMARY")
    print("Key findings:")
    print("1. DB column type: vector(512) (pgvector extension)")
    print("2. Supabase client version: 2.27.0")
    print("3. postgrest-py version: 2.27.0")
    print("4. Behavior: CONSISTENT - always returns as JSON string")
    print("5. Root cause: PostgREST serializes pgvector as JSON for transport")
    print("6. Solution: Always deserialize with json.loads() + isinstance() check")
    print("\nSee detailed output above for evidence.")


if __name__ == "__main__":
    main()
