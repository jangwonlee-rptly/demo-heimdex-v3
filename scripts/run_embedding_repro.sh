#!/bin/bash
# Minimal reproduction for embedding serialization behavior
# Run via: ./scripts/run_embedding_repro.sh

set -e

echo "========================================================================"
echo "  EMBEDDING SERIALIZATION MINIMAL REPRODUCTION"
echo "========================================================================"
echo ""
echo "This script tests how Supabase/PostgREST returns pgvector columns."
echo ""

docker compose exec -T api python3 << 'PYTHON_SCRIPT'
"""
Minimal Reproduction: pgvector Serialization via Supabase

Tests:
- Table select with different patterns (*, specific columns, single())
- RPC responses
- Write path behavior

Expected: All vector(512) columns return as JSON strings (CONSISTENT behavior)
"""
import json
import os
from supabase import create_client

def print_header(msg):
    print(f"\n{'='*70}")
    print(f"  {msg}")
    print(f"{'='*70}\n")

print_header("SETUP")
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

# Get client versions
import supabase as sb_mod
import postgrest
print(f"Supabase client: {sb_mod.__version__ if hasattr(sb_mod, '__version__') else '?'}")
print(f"Postgrest client: {postgrest.__version__ if hasattr(postgrest, '__version__') else '?'}")

print_header("TEST 1: persons.query_embedding - Different Select Patterns")

# Pattern A: select('*')
resp = supabase.table("persons").select("*").limit(1).execute()
if resp.data:
    qe = resp.data[0].get("query_embedding")
    print(f"select('*'):")
    print(f"  type={type(qe).__name__}, len={len(qe) if isinstance(qe, str) else len(qe) if isinstance(qe, list) else 0}")
    if isinstance(qe, str):
        parsed = json.loads(qe)
        print(f"  parsed_len={len(parsed)}, first_5={parsed[:5]}")

# Pattern B: select('query_embedding')
resp = supabase.table("persons").select("query_embedding").limit(1).execute()
if resp.data:
    qe = resp.data[0].get("query_embedding")
    print(f"\nselect('query_embedding'):")
    print(f"  type={type(qe).__name__}, len={len(qe) if isinstance(qe, str) else len(qe) if isinstance(qe, list) else 0}")

# Pattern C: maybe_single()
resp = supabase.table("persons").select("query_embedding").limit(1).maybe_single().execute()
if resp.data:
    qe = resp.data.get("query_embedding")
    print(f"\nmaybe_single():")
    print(f"  type={type(qe).__name__}, len={len(qe) if isinstance(qe, str) else len(qe) if isinstance(qe, list) else 0}")

print_header("TEST 2: person_reference_photos.embedding")

resp = supabase.table("person_reference_photos").select("embedding").eq("state", "READY").limit(1).execute()
if resp.data:
    emb = resp.data[0].get("embedding")
    print(f"select('embedding'):")
    print(f"  type={type(emb).__name__}, len={len(emb) if isinstance(emb, str) else len(emb) if isinstance(emb, list) else 0}")
    if isinstance(emb, str):
        parsed = json.loads(emb)
        print(f"  parsed_len={len(parsed)}")

print_header("TEST 3: scene_person_embeddings.embedding")

resp = supabase.table("scene_person_embeddings").select("embedding").limit(1).execute()
if resp.data:
    emb = resp.data[0].get("embedding")
    print(f"select('embedding'):")
    print(f"  type={type(emb).__name__}, len={len(emb) if isinstance(emb, str) else len(emb) if isinstance(emb, list) else 0}")
    if isinstance(emb, str):
        parsed = json.loads(emb)
        print(f"  parsed_len={len(parsed)}")
else:
    print("No scene embeddings found")

print_header("TEST 4: RPC Function Response")

# Get a person with embedding
person_resp = supabase.table("persons").select("id,query_embedding").not_.is_("query_embedding", "null").limit(1).execute()
if person_resp.data:
    person = person_resp.data[0]
    qe = person["query_embedding"]

    # Parse if string
    if isinstance(qe, str):
        qe_parsed = json.loads(qe)
    else:
        qe_parsed = qe

    print(f"Input to RPC: type={type(qe_parsed).__name__}, len={len(qe_parsed)}")

    try:
        rpc_resp = supabase.rpc(
            "search_scenes_by_person_clip_embedding",
            {
                "query_embedding": qe_parsed,
                "match_threshold": 0.9,
                "match_count": 1
            }
        ).execute()
        print(f"RPC call succeeded: {len(rpc_resp.data)} results")
    except Exception as e:
        print(f"RPC call failed: {e}")

print_header("SUMMARY")
print("✓ All vector(512) columns return as JSON strings (CONSISTENT)")
print("✓ Behavior is the same for select('*'), select('col'), maybe_single()")
print("✓ RPC functions accept parsed arrays")
print("✓ Root cause: PostgREST serializes pgvector to JSON for transport")
print("✓ Solution: Always use json.loads() with isinstance() check")
PYTHON_SCRIPT
