# Bug Fix: Delete Person JSON Parse Error

## Issue
When deleting a person from the People page, the browser console showed:
```
Failed to delete person: SyntaxError: Failed to execute 'json' on 'Response':
Unexpected end of JSON input
```

## Root Cause
The DELETE endpoint returns an empty response body (FastAPI converts `return None` to empty response), but the frontend's `apiRequest()` helper always calls `response.json()`, which fails when there's no JSON content to parse.

### Backend Behavior
```python
# services/api/src/routes/persons.py
@router.delete("/persons/{person_id}")
async def delete_person(...):
    # ... delete logic ...
    return None  # FastAPI sends empty response
```

### Frontend Issue
```typescript
// services/frontend/src/lib/supabase.ts
export async function apiRequest<T>(...) {
  // ...
  if (!response.ok) {
    // handle error
  }

  return response.json();  // ❌ Fails on empty response
}
```

## Files Changed

### `services/frontend/src/lib/supabase.ts` (lines 58-76)

**Before:**
```typescript
if (!response.ok) {
  const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
  throw new Error(error.detail || `API request failed: ${response.statusText}`);
}

return response.json();
```

**After:**
```typescript
if (!response.ok) {
  const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
  throw new Error(error.detail || `API request failed: ${response.statusText}`);
}

// Handle empty responses (e.g., 204 No Content, or DELETE with no body)
const contentLength = response.headers.get('content-length');
if (contentLength === '0' || response.status === 204) {
  return undefined as T;
}

// Check if response has content before parsing
const text = await response.text();
if (!text) {
  return undefined as T;
}

return JSON.parse(text);
```

## Solution Approach

The fix handles empty responses in three ways:

1. **Check Content-Length header**: If `0`, return undefined immediately
2. **Check HTTP status**: If `204 No Content`, return undefined
3. **Read as text first**: Convert to text, check if empty, then parse JSON

This approach:
- ✅ Handles DELETE endpoints that return no body
- ✅ Handles 204 No Content responses
- ✅ Still works for normal JSON responses
- ✅ Maintains backward compatibility with existing code
- ✅ TypeScript-safe (returns `undefined as T` for void types)

## Why This Pattern Works

For `deletePerson()`:
```typescript
export async function deletePerson(personId: string): Promise<void> {
  await apiRequest<void>(`/persons/${personId}`, { method: 'DELETE' });
}
```

- Return type is `Promise<void>`
- `apiRequest<void>` returns `undefined as void`
- Calling code doesn't use the return value
- No JSON parsing error occurs

## Deployment

Rebuild and restart frontend:
```bash
docker-compose build frontend
docker-compose up -d frontend
```

## Testing

1. Navigate to `/people`
2. Create a person (if needed)
3. Click "Delete" button on a person card
4. Confirm deletion in modal
5. Person should be removed from list
6. No console errors should appear

Expected behavior:
- ✅ Person deleted successfully
- ✅ UI updates immediately
- ✅ No JavaScript errors in console
- ✅ Success notification shown

## Impact
- **Severity**: High (delete functionality broken)
- **Scope**: Person deletion only
- **User Impact**: Could not delete person profiles
- **Time to Fix**: ~5 minutes
- **Workaround**: None (feature completely broken)

## Other Endpoints Affected

This fix also improves handling for any future endpoints that return empty responses:
- DELETE operations (typically return no body)
- 204 No Content responses
- Any endpoint that returns `None` or `null` from backend

Previously affected (now fixed):
- ✅ `DELETE /persons/{id}` - Delete person

## Related Issues

This is the **fourth deployment bug** in People feature:
1. devlog/2601051844.txt - Frontend response wrapper mismatches
2. devlog/2601051853.txt - Query parameter vs body issue
3. devlog/2601051907.txt - Worker import error
4. BUGFIX_DELETE_PERSON.md - JSON parse error (current)

## Lessons Learned

1. **API client should handle empty responses gracefully**
   - Not all endpoints return JSON
   - DELETE/PUT operations often return no body
   - HTTP 204 specifically means "No Content"

2. **Always read response as text first when body might be empty**
   - Calling `response.json()` on empty body throws error
   - Reading as text first allows checking for empty content
   - Then parse text as JSON if present

3. **Backend consistency matters**
   - Some frameworks return 204, others return 200 with empty body
   - Frontend should handle both cases
   - Document which endpoints return empty responses

4. **Type safety helps**
   - `Promise<void>` clearly indicates no return value expected
   - TypeScript doesn't prevent runtime parsing errors
   - Runtime checks still necessary

## Prevention

1. **Test all CRUD operations thoroughly**
   - Create, Read, Update, Delete
   - Don't assume success from just Create/Read
   - Delete operations often have different response patterns

2. **Add response handling tests**
   - Unit test `apiRequest()` with empty responses
   - Test with different status codes (200, 204)
   - Test with/without Content-Length headers

3. **Document API response formats**
   - Which endpoints return JSON
   - Which return empty responses
   - Expected status codes for each operation

4. **Consider backend consistency**
   - Use 204 No Content for DELETE operations
   - Or return success JSON: `{"success": true}`
   - Be consistent across all endpoints
