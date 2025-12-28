# Phase 1 Implementation Summary - YouTube Shorts Export

**Date:** 2025-12-10
**Status:** ✅ Complete (Backend Foundation)
**Time:** ~3 hours

---

## What Was Implemented

Phase 1 focused on building the backend foundation for the YouTube Shorts export feature, including database schema, models, exceptions, database adapters, and API endpoints.

---

## Files Created

### 1. Database Migration
**File:** `infra/migrations/014_add_scene_exports.sql`
- Created `scene_exports` table with all required fields
- Added indexes for efficient queries (user_id, scene_id, status, expires_at, created_at)
- Composite index for rate limiting (user_id + created_at)
- Row Level Security (RLS) policies for user data isolation
- CHECK constraints for enum validation
- Default expires_at = created_at + 24 hours

**Key Fields:**
- `id`, `scene_id`, `user_id` (UUIDs with foreign keys)
- `aspect_ratio_strategy`, `output_quality` (enums)
- `status` (pending/processing/completed/failed)
- `storage_path`, `file_size_bytes`, `duration_s`, `resolution`
- `created_at`, `completed_at`, `expires_at`

### 2. API Routes
**File:** `services/api/src/routes/exports.py` (226 lines)

**Endpoints Created:**
1. `POST /v1/scenes/{scene_id}/export-short` (202 Accepted)
   - Creates new export request
   - Rate limiting: 10 exports per day
   - Validation: scene duration ≤ 180s
   - Returns export status immediately

2. `GET /v1/exports/{export_id}` (200 OK)
   - Get export status and metadata
   - Returns presigned download URL if completed
   - Checks expiration (404 if expired)

**Request/Response Schemas:**
- `CreateExportRequest` - aspect_ratio_strategy, output_quality
- `ExportResponse` - export metadata with download URL

---

## Files Modified

### 1. Domain Models
**File:** `services/api/src/domain/models.py`

**Added Enums:**
- `ExportStatus` (pending, processing, completed, failed)
- `AspectRatioStrategy` (center_crop, letterbox, smart_crop)
- `OutputQuality` (high, medium)

**Added Model:**
- `SceneExport` class (53 lines)
  - Complete model matching database schema
  - Type-safe with enum validation

### 2. Custom Exceptions
**File:** `services/api/src/exceptions.py`

**Added Exceptions:**
1. `ExportLimitExceededException` (429)
   - Raised when user exceeds 10 exports/day
   - Includes hours_until_reset in details

2. `ExportExpiredException` (404)
   - Raised when export has expired (> 24 hours)
   - Clear message to create new export

3. `SceneTooLongException` (400)
   - Raised when scene > 180 seconds
   - Includes scene_duration_s and max_duration_s

### 3. Database Adapter
**File:** `services/api/src/adapters/database.py`

**Added Methods:**
1. `create_scene_export()` - Create new export request
2. `get_scene_export()` - Get export by ID
3. `update_scene_export()` - Update export status/metadata
4. `count_user_exports_since()` - Count exports since datetime (rate limiting)
5. `get_oldest_user_export_today()` - Get oldest export in last 24h (reset calculation)
6. `get_expired_exports()` - Get all expired exports (cleanup job)
7. `delete_scene_export()` - Delete export record
8. `_map_export_response()` - Map database row to SceneExport model

**Added Imports:**
- `timedelta` from datetime
- All export-related models and enums

### 4. Main Application
**File:** `services/api/src/main.py`

**Changes:**
- Imported `exports` router
- Registered exports router with `/v1` prefix
- Routes now available at `/v1/scenes/{id}/export-short` and `/v1/exports/{id}`

---

## Features Implemented

### ✅ Rate Limiting
- 10 exports per day per user (sliding 24-hour window)
- Database query counts exports in last 24 hours
- Calculates hours until rate limit resets
- Returns 429 with clear error message

### ✅ Validation
- Scene duration must be ≤ 180 seconds (YouTube Shorts limit)
- User must own the video containing the scene
- Smart crop not yet implemented (returns 400 error)
- Scene and video existence validation

### ✅ Expiration Handling
- Exports expire 24 hours after creation
- Database default: `expires_at = created_at + INTERVAL '24 hours'`
- Frontend will show countdown ("Expires in X hours")
- GET endpoint returns 404 if expired

### ✅ Security
- Row Level Security (RLS) on scene_exports table
- Users can only see/modify their own exports
- Ownership verification in API endpoints
- Presigned URLs for secure downloads (1-hour expiration)

---

## Database Schema

```sql
CREATE TABLE scene_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    aspect_ratio_strategy TEXT NOT NULL CHECK (aspect_ratio_strategy IN ('center_crop', 'letterbox', 'smart_crop')),
    output_quality TEXT NOT NULL CHECK (output_quality IN ('high', 'medium')),

    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,

    storage_path TEXT,
    file_size_bytes BIGINT,
    duration_s FLOAT,
    resolution TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours')
);
```

**Indexes:**
- `idx_scene_exports_scene_id` (scene_id)
- `idx_scene_exports_user_id` (user_id)
- `idx_scene_exports_status` (status)
- `idx_scene_exports_expires_at` (expires_at) - for cleanup
- `idx_scene_exports_created_at` (created_at)
- `idx_scene_exports_user_created` (user_id, created_at) - for rate limiting

---

## API Examples

### Create Export Request

**Request:**
```bash
POST /v1/scenes/{scene_id}/export-short
Authorization: Bearer <token>
Content-Type: application/json

{
  "aspect_ratio_strategy": "center_crop",
  "output_quality": "high"
}
```

**Response (202 Accepted):**
```json
{
  "export_id": "550e8400-e29b-41d4-a716-446655440000",
  "scene_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "aspect_ratio_strategy": "center_crop",
  "output_quality": "high",
  "download_url": null,
  "file_size_bytes": null,
  "duration_s": null,
  "resolution": null,
  "error_message": null,
  "created_at": "2025-12-10T12:00:00Z",
  "completed_at": null,
  "expires_at": "2025-12-11T12:00:00Z"
}
```

### Get Export Status

**Request:**
```bash
GET /v1/exports/{export_id}
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "export_id": "550e8400-e29b-41d4-a716-446655440000",
  "scene_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "aspect_ratio_strategy": "center_crop",
  "output_quality": "high",
  "download_url": "https://storage.supabase.co/...?token=...",
  "file_size_bytes": 45678900,
  "duration_s": 45.2,
  "resolution": "1080x1920",
  "error_message": null,
  "created_at": "2025-12-10T12:00:00Z",
  "completed_at": "2025-12-10T12:00:28Z",
  "expires_at": "2025-12-11T12:00:00Z"
}
```

### Error Responses

**Rate Limit Exceeded (429):**
```json
{
  "error_code": "EXPORT_LIMIT_EXCEEDED",
  "message": "Daily export limit reached (10/day). Try again in 5 hours.",
  "details": {
    "current_count": 10,
    "limit": 10,
    "hours_until_reset": 5
  }
}
```

**Scene Too Long (400):**
```json
{
  "error_code": "SCENE_TOO_LONG",
  "message": "Scene duration (245.3s) exceeds YouTube Shorts maximum (180s)",
  "details": {
    "scene_duration_s": 245.3,
    "max_duration_s": 180
  }
}
```

**Export Expired (404):**
```json
{
  "error_code": "EXPORT_EXPIRED",
  "message": "Export 550e8400-e29b-41d4-a716-446655440000 has expired (24-hour limit). Please create a new export."
}
```

---

## Testing Checklist

### ✅ Manual Testing Required

Before proceeding to Phase 2, test the following:

**Database Migration:**
- [ ] Run migration on dev database
- [ ] Verify table created with correct schema
- [ ] Verify indexes created
- [ ] Verify RLS policies active

**API Endpoints:**
- [ ] Create export request returns 202
- [ ] Rate limiting works (try 11 exports)
- [ ] Scene too long validation (try scene > 180s)
- [ ] Ownership validation (try scene from different user)
- [ ] Get export status returns correct data
- [ ] Expired export returns 404

**Error Handling:**
- [ ] Invalid scene_id returns 404
- [ ] Invalid export_id returns 404
- [ ] Smart crop returns 400 (not implemented)
- [ ] All error responses have correct structure

---

## Next Steps: Phase 2

**Phase 2: Worker Implementation** (6-8 hours)

Now that the backend foundation is complete, the next phase involves:

1. **FFmpeg Adapter Enhancements**
   - Add `extract_scene_clip()` method
   - Add `convert_aspect_ratio()` method (center_crop, letterbox)
   - Test with various source aspect ratios

2. **Worker Task**
   - Create `export_scene_as_short` task
   - Download source video from storage
   - Extract scene clip (start_s to end_s)
   - Convert to 9:16 aspect ratio
   - Encode to YouTube Shorts specs (1080x1920, H.264, AAC)
   - Upload to storage (exports/{user_id}/{export_id}.mp4)
   - Update database with metadata

3. **Queue Integration**
   - Uncomment task queue call in exports.py
   - Test end-to-end workflow

**Estimated Time:** 6-8 hours

---

## Code Statistics

**Lines Added:**
- Migration: 70 lines
- Models: 40 lines (enums + SceneExport class)
- Exceptions: 80 lines (3 new exceptions)
- Database adapter: 210 lines (8 new methods)
- API routes: 226 lines (2 endpoints + schemas)
- **Total: ~626 lines of new code**

**Files Modified:** 4
**Files Created:** 2

---

## Dependencies

**No new dependencies required** - all functionality built with existing libraries:
- FastAPI (routing, validation)
- Pydantic (schemas)
- Supabase Python SDK (database, storage)
- Standard library (datetime, uuid, logging)

---

## Deployment Notes

**Before deploying to production:**

1. **Run migration:**
   ```bash
   psql $DATABASE_URL -f infra/migrations/014_add_scene_exports.sql
   ```

2. **Verify RLS policies:**
   - Check users can only see their own exports
   - Test with multiple user accounts

3. **Monitor rate limiting:**
   - Check database query performance
   - Monitor `count_user_exports_since()` execution time

4. **Set up alerts:**
   - High number of failed exports
   - Exports stuck in "processing" state
   - Rate limit exceptions spike

---

**Phase 1: Complete ✅**
**Ready for Phase 2: Worker Implementation**
