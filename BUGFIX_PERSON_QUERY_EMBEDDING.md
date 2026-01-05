# Bug Fix: Person Query Embedding JSON Deserialization

## Issue

Person-based search was not working despite:
- Person profile created with 3 READY reference photos
- Query embedding generated (512-dimensional CLIP embedding)
- Video scenes having CLIP embeddings (84 out of 100 sampled)

The search would fail because the person's `query_embedding` was being returned as a JSON string instead of a numeric array.

## Root Cause

The API database adapter was returning the person's `query_embedding` as a JSON string (`"[0.123, 0.456, ...]"`) instead of deserializing it to a list of floats.

This is the **same serialization issue** we fixed for photo embeddings in Bug #6 (BUGFIX_EMBEDDING_DESERIALIZATION.md).

**Why this happened:**
1. Supabase client returns JSONB columns as JSON strings (not auto-parsed)
2. The `_map_person_row()` method had a comment claiming "Already a list from Supabase"
3. But empirically, the database was returning a 6390-character string (JSON serialized 512-float array)
4. When PersonQueryParser tried to use this embedding for search, it would fail or behave incorrectly

## Files Changed

### `services/api/src/adapters/database.py` (lines 1865-1888)

**Before:**
```python
def _map_person_row(self, row: dict) -> Person:
    """Map database row to Person model."""
    return Person(
        id=UUID(row["id"]),
        owner_id=UUID(row["owner_id"]),
        display_name=row.get("display_name"),
        query_embedding=row.get("query_embedding"),  # Already a list from Supabase
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
        updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
    )
```

**After:**
```python
def _map_person_row(self, row: dict) -> Person:
    """Map database row to Person model."""
    # Deserialize query_embedding if it's a JSON string
    query_embedding = row.get("query_embedding")
    if query_embedding and isinstance(query_embedding, str):
        import json
        query_embedding = json.loads(query_embedding)

    return Person(
        id=UUID(row["id"]),
        owner_id=UUID(row["owner_id"]),
        display_name=row.get("display_name"),
        query_embedding=query_embedding,
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
        updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
    )
```

## Solution

Added JSON deserialization for `query_embedding` before returning:
1. Check if `query_embedding` is a string
2. If so, deserialize with `json.loads()`
3. Return proper list[float] for search to use

This ensures the `PersonQueryParser` receives a proper numeric array for vector search.

## Deployment

Rebuild and restart API:
```bash
docker-compose build api
docker-compose up -d api
```

Verify startup:
```bash
docker-compose logs api --tail 20
```

## Testing

After deployment:

1. **Navigate to search page** (`/search`)
2. **Enter person name at start of query:**
   ```
   이장원 presentation
   ```
   Or:
   ```
   이장원 meeting
   ```

3. **Monitor API logs** for person detection:
   ```bash
   docker-compose logs api -f | grep -i person
   ```

4. **Expected log output:**
   ```
   Person detected: person_id=<uuid>, has_embedding=True, content_query='presentation'
   Running person-aware search for person_id=<uuid>
   Person retrieval: found N candidates (threshold=0.3, elapsed_ms=X)
   Person fusion: returned M results, weights=(content=0.35, person=0.65)
   ```

5. **Verify search results:**
   - Results should include scenes where the person appears
   - Results should be ranked by relevance (person match + content match)
   - Person detection banner should appear in frontend

## Diagnostic Tool

A diagnostic script was created to check person search prerequisites:

```bash
docker-compose exec -T api python3 << 'PYTHON_SCRIPT'
import os
import json
from supabase import create_client

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

# Check person profile
persons_resp = supabase.table("persons").select("*").execute()
for p in persons_resp.data:
    qe = p.get('query_embedding')
    if isinstance(qe, str):
        print(f"❌ {p['display_name']}: query_embedding is STRING (needs fix)")
    elif isinstance(qe, list):
        print(f"✅ {p['display_name']}: query_embedding is list[float] (dim={len(qe)})")

# Check video CLIP embeddings
scenes_resp = supabase.table("video_scenes").select("id,embedding_visual_clip").limit(100).execute()
with_clip = sum(1 for s in scenes_resp.data if s.get('embedding_visual_clip'))
print(f"Video scenes with CLIP: {with_clip}/{len(scenes_resp.data)}")
PYTHON_SCRIPT
```

## Impact

- **Severity**: Critical (person search completely broken)
- **Scope**: All person-based searches
- **User Impact**: Person search would fail silently or return no results
- **Time to Fix**: ~5 minutes (once root cause identified)
- **Blocking**: Person search feature unusable without this fix

## Root Cause Analysis

**Pattern Recognition:**
This is the **7th deployment bug** related to JSON serialization of JSONB columns:
1. Bug #6: Photo embeddings returned as JSON strings (worker/database.py)
2. Bug #7: Person query embeddings returned as JSON strings (api/database.py)

**Common Theme - JSONB Serialization:**
- Supabase Python client returns JSONB columns as JSON strings
- Developers assume they'll be auto-parsed to Python objects
- Type hints don't enforce runtime types
- Only discovered through testing with real data

**Why This Specific Issue:**
1. Same root cause as Bug #6 (photo embeddings)
2. Different code location (API vs Worker)
3. Same pattern: assumed "already a list" but was actually string
4. Comment in code was incorrect (misleading future developers)

**Prevention Needed:**
1. Search codebase for ALL JSONB column accesses
2. Add JSON deserialization everywhere JSONB is read
3. Add runtime type validation for embeddings
4. Remove misleading comments about "already parsed"
5. Document Supabase client serialization behavior

## Lessons Learned

1. **Don't trust comments about data types** - Verify with actual data
2. **JSONB columns always need explicit deserialization** with Supabase Python client
3. **Test with real database data** - Mocks won't catch serialization issues
4. **Systematic code review needed** - Find all JSONB accesses and fix proactively
5. **Type hints don't prevent runtime type mismatches** in Python
6. **Diagnostic tools are valuable** - Created reusable diagnostic script
7. **Pattern repetition indicates systematic gap** - 7th bug suggests need for better testing

## Prevention Strategy

### Immediate
1. ✅ Fixed person query_embedding deserialization
2. Test person search with actual queries
3. Monitor API logs for person detection working correctly

### Short-term
1. **Audit all JSONB column accesses:**
   ```bash
   grep -r "query_embedding\|embedding\|visual_clip" services/api/src/adapters/database.py
   ```
2. **Add JSON deserialization for ALL embedding fields**
3. **Remove misleading comments** about auto-parsing
4. **Add runtime type validation:**
   ```python
   def validate_embedding(embedding: Any) -> list[float]:
       if isinstance(embedding, str):
           embedding = json.loads(embedding)
       if not isinstance(embedding, list):
           raise TypeError(f"Expected list, got {type(embedding)}")
       return embedding
   ```

### Long-term
1. **Create embedding deserialization helper:**
   ```python
   def deserialize_embedding(value: Any) -> Optional[list[float]]:
       """Safely deserialize JSONB embedding from database."""
       if value is None:
           return None
       if isinstance(value, str):
           import json
           return json.loads(value)
       if isinstance(value, list):
           return value
       raise TypeError(f"Unexpected embedding type: {type(value)}")
   ```

2. **Add to all mapping methods:**
   - `_map_person_row()` ✅
   - `_map_person_photo_row()` - check if needed
   - `_map_scene_row()` - check if needed
   - Any other JSONB embedding fields

3. **Add integration tests with real database:**
   - Test person retrieval returns proper types
   - Test person search with real embeddings
   - Test end-to-end person search flow

4. **Document Supabase serialization behavior:**
   ```markdown
   ## Database Serialization Notes

   **IMPORTANT**: Supabase Python client returns JSONB columns as JSON strings.

   Always deserialize JSONB fields:
   - `query_embedding` (persons table)
   - `embedding` (person_reference_photos table)
   - `embedding_visual_clip` (video_scenes table)
   - Any other JSONB fields

   Use defensive isinstance() check to handle both formats.
   ```

## Related Issues

This is related to:
- **Bug #6**: BUGFIX_EMBEDDING_DESERIALIZATION.md (photo embeddings in worker)
- **Same root cause**: Supabase JSONB serialization behavior
- **Different location**: API adapter vs Worker adapter
- **Same solution**: JSON deserialization with isinstance() check

Both bugs indicate a systematic issue with JSONB handling across the codebase.

## Next Steps

1. ✅ Person query_embedding deserialization fixed
2. ⏳ Test person search with user's query: "이장원 presentation"
3. ⏳ Verify search logs show person detection and fusion
4. ⏳ Audit remaining JSONB column accesses
5. ⏳ Create reusable deserialization helper function
6. ⏳ Add integration tests for person search
