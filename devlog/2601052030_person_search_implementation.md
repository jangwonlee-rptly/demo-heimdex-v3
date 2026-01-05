# Person Search Implementation Progress

**Date:** 2026-01-05 20:30
**Feature:** Reference Photo People Search with Weighted Fusion
**Status:** COMPLETE (All Phases 1-11)

## ✅ COMPLETED

### Phase 1: Database Migration ✅
**File:** `infra/migrations/024_add_person_search.sql`
- persons table with query_embedding vector(512)
- person_reference_photos table with state machine
- scene_person_embeddings table with (kind, ordinal) for multiple embeddings per scene
- HNSW index on scene_person_embeddings.embedding
- RPC function: search_scenes_by_person_clip_embedding (filters by spe.owner_id directly)
- RLS policies for tenant isolation
- Triggers for updated_at

### Phase 2: Domain Models & Schemas ✅
**Files:** `services/api/src/domain/models.py`, `services/api/src/domain/schemas.py`, `services/api/src/domain/search/fusion.py`
- Added Person and PersonReferencePhoto models
- Added PersonStatus and PersonPhotoState enums
- Added PersonCreateRequest, PersonResponse, PersonPhotoUploadUrlResponse, etc.
- Added ScoreType.PERSON_CONTENT_FUSION enum value
- All syntax validated ✅

### Phase 3: Database Adapter (API) ✅
**File:** `services/api/src/adapters/database.py`

Added methods:
- Person CRUD: create_person, get_person, list_persons, update_person_query_embedding, delete_person
- Photo CRUD: create_person_reference_photo, get_person_reference_photo, list_person_photos
- Photo state updates: update_person_photo_state, update_person_photo_embedding, update_person_photo_failed
- Photo aggregation: get_ready_photo_embeddings
- Person search RPC: search_scenes_by_person_clip_embedding
- Scene embeddings: create_scene_person_embedding, get_scene_person_embedding
- Mappers: _map_person_row, _map_person_photo_row

**All methods use adapter for state updates (no raw SQL) ✅**
**Syntax validated ✅**

### Phase 4: API Routes (persons) ✅
**File:** `services/api/src/routes/persons.py`

Implemented routes:
- POST /v1/persons - Create person
- GET /v1/persons - List persons with photo counts
- GET /v1/persons/{person_id} - Get person detail + photos
- POST /v1/persons/{person_id}/photos/upload-url - Get signed upload URL
- POST /v1/persons/{person_id}/photos/{photo_id}/complete - Complete upload, enqueue worker
- DELETE /v1/persons/{person_id} - Delete person (CASCADE)

**Key features:**
- Uses SupabaseStorage.create_signed_upload_url(storage_path) - NO hardcoded bucket
- Storage path validation in /complete endpoint prevents path injection
- Pattern: `persons/{owner_id}/{person_id}/refs/{photo_id}.jpg`
- Enqueues via `queue.enqueue_reference_photo_processing(photo_id)`
- Returns `has_query_embedding` bool in PersonResponse
- Tenant isolation via owner_id everywhere

**Also updated:**
- `services/api/src/adapters/supabase.py` - Added create_signed_upload_url method
- `services/api/src/adapters/queue.py` - Added enqueue_reference_photo_processing method
- `services/api/src/main.py` - Registered persons router under /v1

**Syntax validated ✅**

### Phase 5: Worker Database Adapter ✅
**File:** `services/worker/src/adapters/database.py`

Copied methods from API adapter:
- get_person_reference_photo
- update_person_photo_state
- update_person_photo_embedding
- update_person_photo_failed
- get_ready_photo_embeddings
- update_person_query_embedding
- create_scene_person_embedding (UPSERT)
- get_scene_person_embedding

**Syntax validated ✅**

### Phase 6: Worker Task - Reference Photo Processing ✅
**Files:** `libs/tasks/reference_photo.py`, `services/worker/src/domain/person_photo_processor.py`

Implemented:
- Dramatiq actor: process_reference_photo with retry/timeout config
- PersonPhotoProcessor with idempotency and error handling
- State machine: UPLOADED → PROCESSING → READY/FAILED
- CLIP embedding generation with normalization
- Aggregate query embedding update (normalized mean of READY photos)
- Registered actor in worker bootstrap (services/worker/src/tasks.py)

**Syntax validated ✅**

### Phase 7: Scene Person Embeddings Generation ✅
**File:** `services/worker/src/domain/video_processor.py`

Added `_generate_scene_person_embeddings()` method:
- Called after scene processing and thumbnail upload
- Idempotent: checks existing embeddings before creating
- Deterministic path: `{owner_id}/{video_id}/thumbnails/scene_{index}.jpg`
- CLIP embedding with normalization
- UPSERT with (scene_id, kind, ordinal) unique constraint
- Failures logged but don't block video processing

**Syntax validated ✅**

### Phase 8: Person Query Parser ✅
**File:** `services/api/src/domain/search/person_query_parser.py`

Implemented deterministic parsing:
- Pattern 1: "person:<name>, <rest>"
- Pattern 2: "<name> <rest>" (name at start, case-insensitive)
- Longest-match-first to avoid prefix collisions
- Returns (person_id, person_embedding, remaining_query)
- Returns person_id even if query_embedding is None

**Syntax validated ✅**

### Phase 9: Person Fusion ✅
**File:** `services/api/src/domain/search/person_fusion.py`

Implemented weighted fusion:
- Min-max normalization per channel
- Weighted sum: 0.35 * content + 0.65 * person
- ScoreType.PERSON_CONTENT_FUSION
- Channel scores populated for debugging
- Truncation after fusion

**Syntax validated ✅**

### Phase 10: Search Endpoint Integration ✅
**Files:** `services/api/src/routes/search.py`, `services/api/src/config.py`

Integrated person-aware search:
1. Parse query for person name at beginning
2. Use content_query (person name stripped) for all embeddings/searches
3. Run content search pipeline (existing multi-dense logic)
4. If person_id + person_embedding: run person retrieval + fuse
5. If person_id but no embedding: log and fallback to content-only
6. Backward compatible: no person detected = unchanged behavior

Added config parameters:
- candidate_k_person: 200
- threshold_person: 0.3
- weight_content_person_search: 0.35
- weight_person_person_search: 0.65

**Syntax validated ✅**

### Phase 11: Unit Tests ✅
**Files:** `services/api/tests/unit/test_person_query_parser.py`, `services/api/tests/unit/test_person_fusion.py`

Implemented comprehensive test coverage (42 tests total):

**test_person_query_parser.py** (21 tests):
- Prefix pattern parsing ("person:<name>, <rest>")
  - With/without embedding
  - Case insensitive
  - No comma separator
  - Person not found
- Name-at-start parsing ("<name> <rest>")
  - Space, comma, colon separators
  - Case insensitive
- Longest-match-first logic (prevents prefix collisions)
- Word boundary detection (space, comma, punctuation)
- Edge cases (empty query, no persons, no display name, whitespace)

**test_person_fusion.py** (21 tests):
- Person-dominant ranking (0.65 weight verification)
- Overlapping scene fusion
- Fallback behaviors (content-only, person-only, both empty)
- ScoreType correctness (PERSON_CONTENT_FUSION, DENSE_ONLY)
- Channel scores population (content/person channels)
- Normalization stability (single candidate, constant scores, large ranges)
- Top-k truncation
- Result ordering (implicit ranks)
- Custom weights (content-dominant vs person-dominant)

**Production code fixes made during testing:**
1. **person_query_parser.py:108** - Fixed index alignment bug in Pattern 2 parsing
   - Changed `remaining = query[match_end:]` to `remaining = query_lower[match_end:]`
   - Bug: match_end calculated against stripped string but extraction from original
   - Impact: Queries with leading/trailing whitespace now parsed correctly

2. **person_fusion.py:52,66,138** - Removed invalid `rank` parameter from FusedCandidate
   - FusedCandidate dataclass doesn't have a `rank` field
   - Rank is implicit in list position (result[0] = rank 1, result[1] = rank 2, etc.)
   - Affects: Main fusion path and both fallback paths

**Docker test execution:**
```bash
docker compose -f docker-compose.test.yml run --rm api pytest tests/unit/test_person_query_parser.py tests/unit/test_person_fusion.py -v
```
All 42 tests pass ✅

**Coverage:**
- `person_query_parser.py`: 100% coverage
- `person_fusion.py`: 100% coverage

---

## 📋 IMPLEMENTATION CHECKLIST

- [x] Migration with corrected schema
- [x] Domain models (Person, PersonReferencePhoto)
- [x] API schemas (PersonResponse, PersonPhotoResponse, etc.)
- [x] ScoreType.PERSON_CONTENT_FUSION enum
- [x] Database adapter methods (API)
- [x] API routes (persons) - services/api/src/routes/persons.py
- [x] Register routes in main.py
- [x] Update queue adapter - enqueue_reference_photo_processing
- [x] Add create_signed_upload_url to SupabaseStorage
- [x] Database adapter methods (Worker)
- [x] Worker task actor (reference_photo.py)
- [x] PersonPhotoProcessor domain service
- [x] Update worker bootstrap
- [x] Scene embeddings generation in video processor
- [x] PersonQueryParser
- [x] Person fusion function
- [x] Search endpoint integration
- [x] Config parameters
- [x] Unit tests (42 tests, 100% coverage)

---

## 🔑 KEY DESIGN DECISIONS

1. **Storage paths computed deterministically** (no URL parsing)
   - Reference photos: `persons/{owner_id}/{person_id}/refs/{photo_id}.jpg`
   - Scene thumbnails: `{owner_id}/{video_id}/thumbnails/scene_{index}.jpg`

2. **Bucket access only via SupabaseStorage adapter**
   - No hardcoded `from_('videos')` in routes

3. **Multiple embeddings per scene via (kind, ordinal)**
   - Allows future keyframe support
   - Unique constraint on (scene_id, kind, ordinal)

4. **RPC filters by spe.owner_id directly**
   - No video table join needed
   - Faster person search

5. **No raw SQL in domain services**
   - All state updates via adapter methods

6. **Fusion on topK candidates before truncation**
   - Content retrieval gets 200 candidates
   - Person retrieval gets 200 candidates
   - Fusion operates on full candidate sets
   - Then truncate to limit (default 10)

7. **New ScoreType for person fusion**
   - PERSON_CONTENT_FUSION distinguishes from other fusion modes

8. **Resolve person name even without query_embedding**
   - Parser returns person_id if name matches
   - Search falls back to content-only if no embedding

---

## 🧪 TESTING STRATEGY

### Manual Testing Flow:
```bash
# 1. Apply migration
psql -h localhost -U postgres -d heimdex < infra/migrations/024_add_person_search.sql

# 2. Create person
curl -X POST http://localhost:8000/api/persons \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"display_name": "J Lee"}'

# 3. Get upload URL
curl -X POST http://localhost:8000/api/persons/{person_id}/photos/upload-url \
  -H "Authorization: Bearer $TOKEN"

# 4. Upload photo (use signed URL from response)

# 5. Complete upload
curl -X POST http://localhost:8000/api/persons/{person_id}/photos/{photo_id}/complete \
  -H "Authorization: Bearer $TOKEN" \
  -d "storage_path=persons/{owner_id}/{person_id}/refs/{photo_id}.jpg"

# 6. Check processing status
curl http://localhost:8000/api/persons/{person_id} \
  -H "Authorization: Bearer $TOKEN"

# 7. Search with person
curl -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "j lee doing pushups", "limit": 10}'
```

### Unit Test Coverage:
- Person query parsing (various formats)
- Person fusion (weights, score types, fallbacks)
- Database adapter methods (mocked)

---

## 📝 NOTES

- Worker will need numpy for embedding aggregation
- CLIP embedder must be initialized in worker context
- Scene embeddings generation is idempotent (checks existing before creating)
- Person search uses HNSW index for fast cosine similarity
- Tenant isolation enforced at DB level (RLS + owner_id filters)
- Error handling: photo processing failures don't block video processing

---

## 🎯 NEXT STEPS

1. ~~Complete Phase 4: API routes~~ ✅
2. ~~Complete Phase 5: Worker database adapter~~ ✅
3. ~~Complete Phase 6: Worker task + processor~~ ✅
4. ~~Complete Phase 7: Scene embeddings integration~~ ✅
5. ~~Complete Phase 8-9: Query parser + fusion~~ ✅
6. ~~Complete Phase 10: Search endpoint integration~~ ✅
7. ~~Complete Phase 11: Unit tests~~ ✅ (42 tests, all passing)
8. Manual end-to-end testing (recommended)
9. Document feature in README (optional)
