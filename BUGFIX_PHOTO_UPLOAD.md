# Bug Fix: Photo Upload Complete Endpoint - 422 Error

## Issue
When uploading reference photos to a person profile, the complete upload step fails with:
```
422 Unprocessable Entity
POST /v1/persons/{person_id}/photos/{photo_id}/complete
```

## Root Cause
The frontend was sending `storage_path` in the **request body**, but the backend expects it as a **query parameter**.

### Backend API Contract
```python
@router.post("/persons/{person_id}/photos/{photo_id}/complete")
async def complete_photo_upload(
    person_id: UUID,           # Path parameter
    photo_id: UUID,            # Path parameter
    storage_path: str,         # Query parameter (not body!)
    current_user: User = Depends(get_current_user),
    ...
):
```

In FastAPI, when a parameter doesn't have a type annotation like `Body(...)`, `Path(...)`, or `Query(...)`, and it's not in the route path, it defaults to being a **query parameter**.

### Frontend (Incorrect)
```typescript
// WRONG: Sending storage_path in body
const body: CompletePhotoUploadRequest = { storage_path: storagePath };
await apiRequest<void>(
  `/persons/${personId}/photos/${photoId}/complete`,
  {
    method: 'POST',
    body: JSON.stringify(body),
  }
);
```

### Expected Backend Request
```
POST /v1/persons/{person_id}/photos/{photo_id}/complete?storage_path=persons%2F...%2Frefs%2F....jpg
Content-Type: application/json

(empty body)
```

## Files Changed

### 1. `services/frontend/src/lib/people-api.ts`

**Fixed `completePersonPhotoUpload()`:**
```typescript
// Before:
export async function completePersonPhotoUpload(
  personId: string,
  photoId: string,
  storagePath: string
): Promise<void> {
  const body: CompletePhotoUploadRequest = { storage_path: storagePath };
  await apiRequest<void>(
    `/persons/${personId}/photos/${photoId}/complete`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    }
  );
}

// After:
export async function completePersonPhotoUpload(
  personId: string,
  photoId: string,
  storagePath: string
): Promise<void> {
  // Backend expects storage_path as a query parameter, not in the body
  const url = `/persons/${personId}/photos/${photoId}/complete?storage_path=${encodeURIComponent(storagePath)}`;
  await apiRequest<void>(url, {
    method: 'POST',
  });
}
```

**Key changes:**
- Removed request body
- Added `storage_path` as URL query parameter
- Used `encodeURIComponent()` to properly encode the path (it contains slashes)
- Removed `CompletePhotoUploadRequest` import (no longer needed)

### 2. `services/frontend/src/types/index.ts`

**Removed unused type:**
```typescript
// REMOVED - No longer needed
export interface CompletePhotoUploadRequest {
  storage_path: string;
}
```

## Testing

After deploying this fix:

1. Navigate to `/people`
2. Create a person
3. Click "View Details" → "Add Photos"
4. Select one or more face photos
5. Upload should complete successfully
6. Photos should transition: UPLOADED → PROCESSING → READY
7. No 422 errors in browser console or backend logs

## Deployment

Rebuild and redeploy frontend only (no backend changes):

```bash
docker-compose build frontend
docker-compose up -d frontend
```

## Related Issues

This is the second API contract mismatch after the initial deployment:
1. **First issue**: Response wrappers (`{persons: [...]}` vs `[...]`)
2. **This issue**: Query parameters vs request body

## Prevention

To prevent similar issues in the future:

1. **Use OpenAPI/Swagger**: Generate frontend types from backend OpenAPI spec
2. **Integration tests**: Test actual API calls against running backend
3. **Contract testing**: Use tools like Pact to verify API contracts
4. **Runtime validation**: Use libraries like `zod` to validate API responses
5. **Backend documentation**: Explicitly annotate FastAPI parameters:
   ```python
   storage_path: str = Query(...)  # Makes it clear it's a query param
   ```

## Backend API Reference

### Complete Photo Upload
**Endpoint:** `POST /v1/persons/{person_id}/photos/{photo_id}/complete`

**Parameters:**
- `person_id` (path): UUID of the person
- `photo_id` (path): UUID of the photo (from upload-url response)
- `storage_path` (query): Storage path (from upload-url response)

**Example:**
```bash
curl -X POST \
  'https://api.example.com/v1/persons/c4d3b3a8-727c-41b7-8eb6-9e674d879491/photos/1e8b61f9-9440-467d-a714-eb40d74441b9/complete?storage_path=persons%2F799f1283-a2d7-4f8a-96e6-faf71a749b64%2Fc4d3b3a8-727c-41b7-8eb6-9e674d879491%2Frefs%2F1e8b61f9-9440-467d-a714-eb40d74441b9.jpg' \
  -H 'Authorization: Bearer {token}'
```

**Response:**
```json
{
  "status": "accepted",
  "message": "Photo processing queued"
}
```
