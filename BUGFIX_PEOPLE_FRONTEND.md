# Bug Fix: People Frontend API Response Handling

## Issue
Browser console error after deploying:
```
TypeError: e.map is not a function
```

## Root Cause
The frontend was expecting the backend `/v1/persons` endpoint to return a direct array of persons, but the backend actually returns:
```json
{
  "persons": [...]
}
```

Additionally, there were several type mismatches between frontend and backend:

1. **List Persons Response**: Backend returns `{persons: Person[]}`, frontend expected `Person[]`
2. **Get Person Response**: Backend returns `{person: PersonResponse, photos: PersonPhotoResponse[]}`, frontend expected `Person` with photos included
3. **Person Status**: Backend returns `"active"` or `"archived"`, frontend expected `"NEEDS_PHOTOS"` | `"PROCESSING"` | `"READY"`
4. **Person owner_id**: Backend doesn't return `owner_id` (security), but frontend type included it

## Files Changed

### 1. `services/frontend/src/lib/people-api.ts`

**Added helper function:**
```typescript
export function getPersonDisplayStatus(person: Person): PersonDisplayStatus {
  if (person.total_photos_count === 0) {
    return 'NEEDS_PHOTOS';
  }
  if (person.has_query_embedding && person.ready_photos_count > 0) {
    return 'READY';
  }
  return 'PROCESSING';
}
```

**Fixed `listPersons()`:**
```typescript
// Before:
export async function listPersons(): Promise<Person[]> {
  return apiRequest<Person[]>('/persons', { method: 'GET' });
}

// After:
export async function listPersons(): Promise<Person[]> {
  const response = await apiRequest<{ persons: Person[] }>('/persons', {
    method: 'GET',
  });
  return response.persons;
}
```

**Fixed `getPerson()`:**
```typescript
// Before:
export async function getPerson(personId: string): Promise<Person> {
  return apiRequest<Person>(`/persons/${personId}`, { method: 'GET' });
}

// After:
export async function getPerson(personId: string): Promise<Person> {
  const response = await apiRequest<{
    person: Omit<Person, 'photos'>;
    photos: Person['photos'];
  }>(`/persons/${personId}`, {
    method: 'GET',
  });
  return {
    ...response.person,
    photos: response.photos,
  };
}
```

### 2. `services/frontend/src/types/index.ts`

**Updated Person type:**
```typescript
// Removed owner_id field (backend doesn't return it)
export interface Person {
  id: string;
  // owner_id: string; // REMOVED
  display_name: string;
  status: PersonStatus; // Now "active" | "archived"
  ready_photos_count: number;
  total_photos_count: number;
  has_query_embedding: boolean;
  photos?: PersonPhoto[];
  created_at: string;
  updated_at: string;
}

// Updated status type to match backend
export type PersonStatus = 'active' | 'archived';

// Added display status for UI
export type PersonDisplayStatus = 'NEEDS_PHOTOS' | 'PROCESSING' | 'READY';
```

### 3. `services/frontend/src/app/people/page.tsx`

**Imported helper:**
```typescript
import { getPersonDisplayStatus } from '@/lib/people-api';
```

**Updated PersonCard component:**
```typescript
function PersonCard({ person, onViewDetails, onDelete, t }) {
  const displayStatus = getPersonDisplayStatus(person); // Compute display status
  const statusConfig = {
    READY: { label: t.people.status.READY, color: 'bg-green-500/10 text-green-400' },
    PROCESSING: { label: t.people.status.PROCESSING, color: 'bg-yellow-500/10 text-yellow-400' },
    NEEDS_PHOTOS: { label: t.people.status.NEEDS_PHOTOS, color: 'bg-red-500/10 text-red-400' },
  };
  const status = statusConfig[displayStatus];
  // ...
}
```

**Updated PersonDetailsModal:**
```typescript
// Changed from: person.status
// To: getPersonDisplayStatus(person)
<span className={`status-badge ${
  getPersonDisplayStatus(person) === 'READY'
    ? 'bg-green-500/10 text-green-400'
    : getPersonDisplayStatus(person) === 'PROCESSING'
    ? 'bg-yellow-500/10 text-yellow-400'
    : 'bg-red-500/10 text-red-400'
}`}>
  {t.people.status[getPersonDisplayStatus(person)]}
</span>
```

## Backend API Contract (for reference)

### GET /v1/persons
**Returns:**
```json
{
  "persons": [
    {
      "id": "uuid",
      "display_name": "J Lee",
      "status": "active",
      "ready_photos_count": 3,
      "total_photos_count": 5,
      "has_query_embedding": true,
      "created_at": "2026-01-05T...",
      "updated_at": "2026-01-05T..."
    }
  ]
}
```

### GET /v1/persons/{person_id}
**Returns:**
```json
{
  "person": {
    "id": "uuid",
    "display_name": "J Lee",
    "status": "active",
    "ready_photos_count": 3,
    "total_photos_count": 5,
    "has_query_embedding": true,
    "created_at": "2026-01-05T...",
    "updated_at": "2026-01-05T..."
  },
  "photos": [
    {
      "id": "uuid",
      "person_id": "uuid",
      "storage_path": "persons/...",
      "state": "READY",
      "quality_score": 0.85,
      "error_message": null,
      "created_at": "2026-01-05T...",
      "updated_at": "2026-01-05T..."
    }
  ]
}
```

## Display Status Logic

The frontend computes display status from backend data:

- **NEEDS_PHOTOS**: `total_photos_count === 0`
- **PROCESSING**: Has photos but not ready (`!has_query_embedding || ready_photos_count === 0`)
- **READY**: `has_query_embedding && ready_photos_count > 0`

## Testing

After deploying these changes:

1. Navigate to `/people` - should load without errors
2. Create a person - should appear with "Needs Photos" status
3. Upload photos - should transition to "Processing" then "Ready"
4. Search page person detection - should work without errors

## Deployment

No backend changes required. Simply rebuild and redeploy frontend:

```bash
docker-compose build frontend
docker-compose up -d frontend
```

Or if using a build pipeline:
```bash
npm run build
npm run start
```
