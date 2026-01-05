# Bug Fix: Embedding Deserialization from Database

## Issue
When aggregating multiple photo embeddings to create a person's query embedding, the worker failed with:
```
numpy.core._exceptions._UFuncNoLoopError: ufunc 'add' did not contain a loop with signature
matching types (dtype('<U6390'), dtype('<U6390')) -> None
```

## Root Cause
The database adapter was returning embeddings as **JSON strings** instead of numeric arrays. When numpy tried to compute the mean of these strings, it failed because you can't perform arithmetic operations on strings.

### The Error Explained
- `dtype('<U6390')` means numpy detected a Unicode string array with 6390 characters per element
- This is exactly what a JSON-serialized 512-dimensional float array looks like: `"[0.123, 0.456, ...]"`
- Numpy's `np.mean()` requires numeric arrays, not strings

### Database Storage Format
PostgreSQL stores embeddings in a JSONB column, which the Supabase client returns as a string when queried.

### Incorrect Code
```python
# services/worker/src/adapters/database.py (BEFORE)
def get_ready_photo_embeddings(self, person_id: UUID) -> list[list[float]]:
    response = (
        self.client.table("person_reference_photos")
        .select("embedding")
        .eq("person_id", str(person_id))
        .eq("state", "READY")
        .not_.is_("embedding", "null")
        .execute()
    )

    embeddings = []
    for row in response.data:
        if row.get("embedding"):
            embeddings.append(row["embedding"])  # ❌ Returns string!

    return embeddings
```

### Usage Site
```python
# services/worker/src/domain/person_photo_processor.py
embeddings = self.db.get_ready_photo_embeddings(person_id)
embeddings_array = np.array(embeddings)  # Creates array of strings!
mean_embedding = np.mean(embeddings_array, axis=0)  # ❌ Fails - can't average strings
```

## Files Changed

### `services/worker/src/adapters/database.py` (lines 910-920)

**Before:**
```python
embeddings = []
for row in response.data:
    if row.get("embedding"):
        embeddings.append(row["embedding"])

return embeddings
```

**After:**
```python
embeddings = []
for row in response.data:
    embedding = row.get("embedding")
    if embedding:
        # Handle both string (JSON) and list formats
        if isinstance(embedding, str):
            import json
            embedding = json.loads(embedding)
        embeddings.append(embedding)

return embeddings
```

## Solution

Parse JSON strings into actual lists before returning:
1. Check if embedding is a string
2. If so, deserialize with `json.loads()`
3. Return proper numeric list

This ensures numpy receives `list[list[float]]` not `list[str]`.

### Why the Defensive Check?
The code checks `isinstance(embedding, str)` because the database client behavior might vary:
- Some configurations return JSONB as strings
- Others might return as already-parsed lists
- This handles both cases safely

## Deployment

Rebuild and restart worker:
```bash
docker-compose build worker
docker-compose up -d worker
```

Verify startup:
```bash
docker-compose logs worker --tail 15
```

## Testing

After deployment:
1. Upload multiple reference photos to a person
2. Monitor worker logs:
   ```bash
   docker-compose logs worker -f
   ```
3. Should see successful processing:
   ```
   Starting reference photo processing for photo_id={uuid}
   Downloading photo from persons/.../refs/{photo_id}.jpg
   Downloaded {size} bytes
   Generating CLIP embedding for {local_path}
   Embedding generated: dim=512, quality_score=0.XXX
   Photo {photo_id} marked as READY
   Updating query embedding for person {person_id}
   Aggregating {N} embeddings for person {person_id}
   Person {person_id} query embedding updated
   Completed reference photo processing for photo_id={uuid}
   ```
4. Verify person status becomes READY
5. Test person detection in search

## Impact
- **Severity**: Critical (embedding aggregation completely broken)
- **Scope**: All persons with multiple photos
- **User Impact**: Photos processed but person never becomes READY
- **Time to Fix**: ~5 minutes

## Root Cause Analysis

**Why did this happen?**

1. **Database client behavior assumption**
   - Assumed Supabase client returns JSONB as parsed lists
   - Actually returns as JSON strings
   - No runtime type checking

2. **Type hints insufficient**
   - Method signature says `-> list[list[float]]`
   - But actually returned `list[str]`
   - Python doesn't enforce return types at runtime
   - mypy would catch this if run with strict mode

3. **No validation at boundaries**
   - Database adapter didn't validate return type
   - Processor trusted the type hint
   - Error occurred deep in numpy, not at boundary

**Similar issues in codebase?**

Other database methods likely have the same issue:
- `get_person()` might return embeddings as strings
- `update_person_query_embedding()` might need to serialize
- Any JSONB column retrieval needs deserialization

## Lessons Learned

1. **Don't trust database client serialization**
   - JSONB columns often returned as strings
   - Always explicitly deserialize
   - Document serialization format

2. **Type hints are documentation, not enforcement**
   - `-> list[list[float]]` doesn't guarantee the type
   - Need runtime validation
   - Or use mypy/pydantic for validation

3. **Validate at service boundaries**
   - Database adapter is a boundary
   - Should validate/coerce types before returning
   - Fail fast with clear error messages

4. **Test with real data**
   - Mock tests might not catch serialization issues
   - Need integration tests with real database
   - Test complete flows, not just happy path

5. **Numpy errors can be cryptic**
   - `_UFuncNoLoopError` doesn't immediately suggest "wrong type"
   - Need to decode `dtype('<U6390')` to understand issue
   - Earlier type validation would give clearer errors

## Prevention

### Immediate

1. **Review all JSONB column accesses**
   ```bash
   grep -r "\.select.*embedding" services/worker/src/adapters/
   ```
2. **Add similar fixes for other embeddings**
3. **Test with multiple photos per person**

### Short-term

1. **Add runtime type validation**
   ```python
   def get_ready_photo_embeddings(self, person_id: UUID) -> list[list[float]]:
       # ... fetch from db ...

       # Validate before returning
       for embedding in embeddings:
           if not isinstance(embedding, list):
               raise TypeError(f"Expected list, got {type(embedding)}")
           if not all(isinstance(x, (int, float)) for x in embedding):
               raise TypeError("Embedding must contain only numbers")

       return embeddings
   ```

2. **Add integration tests**
   - Insert photo with embedding
   - Retrieve and verify type
   - Test aggregation with real data

3. **Use Pydantic models for database responses**
   ```python
   class PhotoEmbedding(BaseModel):
       embedding: list[float]

   # Pydantic will validate/coerce types
   ```

### Long-term

1. **Run mypy in CI**
   ```bash
   mypy services/worker/src --strict
   ```

2. **Add runtime type checking library**
   - Use `typeguard` or `beartype`
   - Validates types at runtime
   - Catches mismatches immediately

3. **Document serialization contracts**
   - Document which fields are JSON
   - Document expected Python types
   - Add examples to docstrings

4. **Consider using proper array types**
   - PostgreSQL has native array types
   - Or use `pgvector` extension
   - Avoids JSON serialization entirely

## Related Issues

This is the **sixth deployment bug** in People feature:
1. devlog/2601051844.txt - Response wrapper mismatches
2. devlog/2601051853.txt - Query parameter issue
3. devlog/2601051907.txt - Worker import error
4. devlog/2601051917.txt - JSON parse error on delete
5. devlog/2601051938.txt - Storage method signature
6. BUGFIX_EMBEDDING_DESERIALIZATION.md - Embedding deserialization (current)

All found through manual testing. Strong indication that:
- Integration tests are insufficient
- Type validation at boundaries is missing
- Runtime type checking would help significantly
