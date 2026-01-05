# Person Search Implementation Progress

**Date:** 2026-01-05 20:30
**Feature:** Reference Photo People Search with Weighted Fusion
**Status:** IN PROGRESS (Phase 1-3 Complete)

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

---

## 🚧 REMAINING WORK

### Phase 5: Worker Database Adapter 🔄
**File:** `services/worker/src/adapters/database.py`

Copy methods from API database adapter:
- update_person_photo_state
- update_person_photo_embedding
- update_person_photo_failed
- get_ready_photo_embeddings
- update_person_query_embedding
- create_scene_person_embedding
- get_scene_person_embedding

---

### Phase 6: Worker Task - Reference Photo Processing 🔄

**File:** `libs/tasks/reference_photo.py` (NEW)
```python
@dramatiq.actor(
    queue_name="reference_photo_processing",
    max_retries=1,
    min_backoff=15000,
    max_backoff=60000,
    time_limit=300000,  # 5 minutes
)
def process_reference_photo(photo_id: str) -> None:
    # Lazy import worker context
    # Call PersonPhotoProcessor.process_photo(photo_id)
```

**File:** `services/worker/src/domain/person_photo_processor.py` (NEW)
```python
class PersonPhotoProcessor:
    def process_photo(self, photo_id: UUID) -> None:
        # 1. db.update_person_photo_state(photo_id, "PROCESSING")
        # 2. storage.download_file(storage_path, local_path)
        # 3. embedding = clip_embedder.embed_image(local_path)
        # 4. quality_score = _compute_quality_score(embedding)
        # 5. db.update_person_photo_embedding(photo_id, embedding, quality_score)
        # 6. _update_person_query_embedding(person_id)

    def _update_person_query_embedding(self, person_id: UUID) -> None:
        # 1. embeddings = db.get_ready_photo_embeddings(person_id)
        # 2. mean_embedding = np.mean(embeddings, axis=0)
        # 3. mean_embedding = mean_embedding / np.linalg.norm(mean_embedding)
        # 4. db.update_person_query_embedding(person_id, mean_embedding.tolist())
```

**Update:** `libs/tasks/__init__.py`
```python
from .reference_photo import process_reference_photo
```

**Update:** `services/api/src/adapters/queue.py`
```python
def enqueue_reference_photo_processing(self, photo_id: UUID) -> None:
    self._ensure_broker()
    from libs.tasks import process_reference_photo
    process_reference_photo.send(str(photo_id))
```

**Update:** `services/worker/src/tasks.py` - Import in bootstrap
```python
from libs.tasks import process_reference_photo  # Register actor
```

---

### Phase 7: Scene Embeddings Generation 🔄

**File:** `services/worker/src/domain/video_processor.py`

Add method after scene processing:
```python
def _generate_scene_person_embeddings(self, video: Video, scenes: list[VideoScene]) -> None:
    """Generate person embeddings for scenes (idempotent)."""
    if not self.clip_embedder:
        return

    for scene in scenes:
        # Check idempotency
        existing = self.db.get_scene_person_embedding(scene.id)
        if existing:
            continue

        # Compute deterministic thumbnail path
        # Pattern: {owner_id}/{video_id}/thumbnails/scene_{scene.index}.jpg
        thumbnail_storage_path = f"{video.owner_id}/{video.id}/thumbnails/scene_{scene.index}.jpg"

        # Download thumbnail
        with TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / f"scene_{scene.id}.jpg"
            self.storage.download_file(thumbnail_storage_path, local_path)

            # Generate embedding
            embedding = self.clip_embedder.embed_image(str(local_path))

            if embedding and len(embedding) == 512:
                self.db.create_scene_person_embedding(
                    owner_id=video.owner_id,
                    video_id=video.id,
                    scene_id=scene.id,
                    embedding=embedding,
                    kind="thumbnail",
                    ordinal=0,
                )
```

**Call in process_video() after scene hydration:**
```python
# After: scenes = self.db.get_scenes(video_id)
self._generate_scene_person_embeddings(video, scenes)
```

---

### Phase 8: Query Parser 🔄

**File:** `services/api/src/domain/search/person_query_parser.py` (NEW)
```python
class PersonQueryParser:
    def __init__(self, db, owner_id: UUID):
        self.db = db
        self.owner_id = owner_id
        self._load_persons()

    def _load_persons(self) -> None:
        persons = self.db.list_persons(self.owner_id)
        # Build lookup: lowercase display_name -> (person_id, embedding)
        # Include persons even if query_embedding is None (return person_id but not embedding)

    def parse(self, query: str) -> tuple[Optional[UUID], Optional[list[float]], str]:
        """Parse query to extract person.

        Returns:
            (person_id, person_embedding, remaining_query)
            - person_id: UUID if person found, else None
            - person_embedding: embedding if exists, else None
            - remaining_query: query with person name removed
        """
        # Check for "person:" prefix: person:j lee, doing pushups
        # Check if query starts with known person name (case-insensitive)
        # Return person_id even if query_embedding is None
```

---

### Phase 9: Person Fusion 🔄

**File:** `services/api/src/domain/search/person_fusion.py` (NEW)
```python
def fuse_with_person(
    content_candidates: list[Candidate],  # topK from content (e.g., 200)
    person_candidates: list[Candidate],
    weight_content: float = 0.35,
    weight_person: float = 0.65,
    eps: float = 1e-9,
    top_k: int = 10,
) -> list[FusedCandidate]:
    """Fuse content and person candidates with person as strong signal.

    Uses ScoreType.PERSON_CONTENT_FUSION.
    """
    # Normalize both sets
    # Weighted mean: final = w_content * norm(content) + w_person * norm(person)
    # Return FusedCandidate with score_type=ScoreType.PERSON_CONTENT_FUSION
    # Populate channel_scores with "content" and "person" channels
```

---

### Phase 10: Search Endpoint Integration 🔄

**File:** `services/api/src/routes/search.py`

Modifications:
```python
# At top, add imports
from ..domain.search.person_query_parser import PersonQueryParser
from ..domain.search.person_fusion import fuse_with_person

# In search_scenes endpoint, after line ~1200:

# 1. Parse query for person name
parser = PersonQueryParser(db, user_id)
person_id, person_embedding, content_query = parser.parse(request.query)

# 2. Run content search with content_query (existing pipeline)
# ... existing multi-dense logic ...
# Get content_fused_results (topK, e.g., 200 candidates BEFORE final truncation)

# 3. If person detected AND has embedding, run person search
if person_id and person_embedding:
    logger.info(f"Person-aware search: person_id={person_id}, content_query='{content_query}'")

    # Run person retrieval
    person_results = db.search_scenes_by_person_clip_embedding(
        query_embedding=person_embedding,
        user_id=user_id,
        video_id=request.video_id,
        match_count=settings.candidate_k_person,
        threshold=settings.threshold_person,
    )

    person_candidates = [
        Candidate(scene_id=scene_id, rank=rank, score=similarity)
        for scene_id, rank, similarity in person_results
    ]

    # Convert content fused results to candidates
    content_candidates = [
        Candidate(scene_id=f.scene_id, rank=i+1, score=f.score)
        for i, f in enumerate(content_fused_results)
    ]

    # Fuse with person signal
    fused_results = fuse_with_person(
        content_candidates=content_candidates,
        person_candidates=person_candidates,
        weight_content=settings.weight_content_person_search,
        weight_person=settings.weight_person_person_search,
        top_k=request.limit,
    )
elif person_id:
    # Person detected but no query_embedding yet
    logger.info(f"Person '{person_id}' detected but no query embedding, using content-only")
    # fallback to content_fused_results

# 4. Hydrate and return
```

**Add config parameters in `services/api/src/config.py`:**
```python
# Person search configuration
candidate_k_person: int = 200
threshold_person: float = 0.3
weight_content_person_search: float = 0.35
weight_person_person_search: float = 0.65
```

---

### Phase 11: Unit Tests 🔄

**File:** `services/api/tests/unit/test_person_query_parser.py` (NEW)
- test_parse_person_prefix_with_embedding
- test_parse_person_prefix_without_embedding
- test_parse_name_at_start
- test_parse_no_person
- test_parse_case_insensitive

**File:** `services/api/tests/unit/test_person_fusion.py` (NEW)
- test_fuse_person_strong_signal
- test_fuse_fallback_content_only
- test_fuse_fallback_person_only
- test_fuse_weights_validation
- test_fuse_score_type

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
- [ ] Database adapter methods (Worker)
- [ ] Worker task actor (reference_photo.py)
- [ ] PersonPhotoProcessor domain service
- [ ] Update worker bootstrap
- [ ] Scene embeddings generation in video processor
- [ ] PersonQueryParser
- [ ] Person fusion function
- [ ] Search endpoint integration
- [ ] Config parameters
- [ ] Unit tests

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

1. Complete Phase 4: API routes
2. Complete Phase 5: Worker database adapter
3. Complete Phase 6: Worker task + processor
4. Complete Phase 7: Scene embeddings integration
5. Complete Phase 8-9: Query parser + fusion
6. Complete Phase 10: Search endpoint integration
7. Complete Phase 11: Unit tests
8. Manual end-to-end testing
9. Document feature in README
