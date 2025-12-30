# Phase 1 Completion Checklist

This document provides step-by-step instructions to complete the remaining Phase 1 work.

## Status: 🟡 75% Complete

**✅ Completed:**
- API composition root and dependency injection infrastructure
- Worker context and bootstrap pattern
- All adapters refactored to remove module-level singletons
- Import safety tests created
- Comprehensive documentation

**🚧 Remaining:**
- Update all API route handlers to use dependency injection
- Update VideoProcessor constructor
- Run tests and fix regressions

---

## Step 1: Update API Route Handlers (2-4 hours)

All route handlers need to be updated to use dependency injection instead of global adapter imports.

### Pattern to Apply

**Before:**
```python
from ..adapters.database import db
from ..adapters.supabase import storage
from ..adapters.queue import task_queue

@router.get("/videos")
async def list_videos(current_user: User = Depends(get_current_user)):
    videos = db.list_user_videos(current_user.id)
    return videos
```

**After:**
```python
from ..dependencies import get_db, get_storage, get_queue
from ..adapters.database import Database
from fastapi import Depends

@router.get("/videos")
async def list_videos(
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    videos = db.list_user_videos(current_user.id)
    return videos
```

### Files to Update

1. **`services/api/src/routes/videos.py`** (~7 handlers) ⚠️ Partially done
   - ✅ Line 99: `create_upload_url` - Already updated as example
   - 🔲 Line 162: `mark_video_uploaded` - Add `db: Database = Depends(get_db), queue: TaskQueue = Depends(get_queue)`
   - 🔲 Line 227: `request_video_processing` - Add `db, queue`
   - 🔲 Line 288: `reprocess_video` - Add `db, queue`
   - 🔲 Line 380: `list_videos` - Add `db`
   - 🔲 Line 426: `get_video` - Add `db`
   - 🔲 Line 487: `get_video_details` - Add `db`

2. **`services/api/src/routes/search.py`** (~2 handlers)
   - Imports: Replace `from ..adapters.opensearch_client import opensearch_client, from ..adapters.openai_client import openai_client`
   - With: `from ..dependencies import get_db, get_opensearch, get_openai, get_clip`
   - Add dependencies to route handlers

3. **`services/api/src/routes/exports.py`** (~4 handlers)
   - Add `db: Database = Depends(get_db), queue: TaskQueue = Depends(get_queue)`

4. **`services/api/src/routes/highlights.py`** (~3 handlers)
   - Add `db, queue` dependencies

5. **`services/api/src/routes/admin.py`** (~5 handlers)
   - Add `db` dependency

6. **`services/api/src/routes/preferences.py`** (~2 handlers)
   - Add `db` dependency

7. **`services/api/src/routes/profile.py`** (~2 handlers)
   - Add `db, storage` dependencies

### Special Case: task_queue Methods

The `TaskQueue` class was refactored to accept `db` as an optional parameter:

**Old:**
```python
task_queue.enqueue_video_processing(video_id)
```

**New:**
```python
queue.enqueue_video_processing(video_id, db=db)
```

Update all calls to `enqueue_*` methods.

---

## Step 2: Update VideoProcessor Constructor (1-2 hours)

The `VideoProcessor` class needs to be refactored to accept dependencies via constructor.

### File: `services/worker/src/domain/video_processor.py`

**Current state (lines 13-26):**
```python
from ..adapters.database import db, VideoStatus
from ..adapters.supabase import storage
from ..adapters.ffmpeg import ffmpeg
from ..adapters.openai_client import openai_client
from ..config import settings

class VideoProcessor:
    _api_semaphore = Semaphore(settings.max_api_concurrency)
```

**Target state:**
```python
from ..adapters.database import VideoStatus

class VideoProcessor:
    def __init__(
        self,
        db,
        storage,
        opensearch,
        openai,
        clip_embedder,
        ffmpeg,
        settings,
    ):
        self.db = db
        self.storage = storage
        self.opensearch = opensearch
        self.openai = openai
        self.clip_embedder = clip_embedder
        self.ffmpeg = ffmpeg
        self.settings = settings
        self._api_semaphore = Semaphore(settings.max_api_concurrency)
```

Then replace all references to global `db` with `self.db`, `storage` with `self.storage`, etc., throughout the class.

**Note:** `libs/tasks/video_processing.py` already creates VideoProcessor with injected dependencies (line 55-63), so this will work once the constructor is updated.

---

## Step 3: Run Import Safety Tests

Run the import safety tests to verify Phase 1 goals are met.

```bash
# API import safety tests
docker-compose run --rm api pytest services/api/tests/test_import_safety.py -v

# Worker import safety tests
docker-compose run --rm worker pytest services/worker/tests/test_import_safety.py -v
```

**Expected results:**
- All tests should pass
- No network connections should be made during test execution
- If tests fail, check:
  - Are there remaining module-level singletons?
  - Are adapters being created during import?

---

## Step 4: Run Full Test Suite

Run the existing test suite to catch any regressions.

```bash
# Run API tests
docker-compose run --rm api pytest services/api/tests/ -v

# Run worker tests
docker-compose run --rm worker pytest services/worker/tests/ -v
```

**Common issues to fix:**
1. **Tests that imported global adapters:**
   - Replace `from src.adapters.database import db` with mocking `get_db` dependency

2. **Tests that expected module-level initialization:**
   - Update to use `app.dependency_overrides` pattern

3. **Worker tests that expected global video_processor:**
   - Update to create VideoProcessor with explicit dependencies

---

## Step 5: Manual Smoke Test

After tests pass, run a manual smoke test to verify the app works end-to-end.

```bash
# Start all services
docker-compose up

# In another terminal, run smoke tests:

# 1. Check API health
curl http://localhost:8000/health

# 2. Create a test upload URL (requires authentication)
# Use Postman/httpie with auth token

# 3. Check worker logs
docker-compose logs worker -f
# Should see: "Worker bootstrapped successfully"

# 4. Enqueue a test job and verify it processes
```

---

## Step 6: Update Remaining Worker Adapters (Optional)

For completeness, update worker adapter files to match the API pattern:

1. **`services/worker/src/config.py`**
   - Set `settings = None` (currently `settings = Settings()`)

2. **`services/worker/src/adapters/database.py`**
   - Remove `from ..config import settings` import
   - Set `db = None` at module level
   - Already has constructor that accepts parameters

3. **`services/worker/src/adapters/openai_client.py`**
   - Same pattern as API version

4. **`services/worker/src/adapters/opensearch_client.py`**
   - Same pattern as API version

**Note:** This is lower priority since worker adapters are created via WorkerContext, but it improves consistency.

---

## Step 7: Update Other Task Actors (Optional)

Update the other shared task actors to use dependency injection:

1. **`libs/tasks/scene_export.py`** - export_scene_as_short actor
2. **`libs/tasks/highlight_export.py`** - process_highlight_export actor

Follow the same pattern as `video_processing.py`:
```python
from src.tasks import get_worker_context

ctx = get_worker_context()
# Use ctx.db, ctx.storage, etc.
```

---

## Acceptance Criteria for Phase 1 Completion

- [ ] All API route handlers use `Depends()` for adapter injection
- [ ] VideoProcessor accepts dependencies via constructor
- [ ] Import safety tests pass (both API and Worker)
- [ ] Existing test suite passes with no regressions
- [ ] Manual smoke test confirms end-to-end functionality
- [ ] No module-level adapter instantiation remains
- [ ] Importing any module performs no I/O operations

---

## Troubleshooting

### Issue: "Application context not initialized"
**Cause:** Route handler trying to access `app.state.ctx` before lifespan runs.
**Fix:** Ensure FastAPI app is started with lifespan (should happen automatically).

### Issue: "Worker context not initialized"
**Cause:** Task trying to call `get_worker_context()` before `bootstrap()` runs.
**Fix:** Ensure task actor imports trigger bootstrap (auto-runs in tasks.py).

### Issue: Tests failing with "db is None"
**Cause:** Test importing module that references deprecated global `db`.
**Fix:** Update test to use dependency injection or mock the dependency.

### Issue: Circular import errors
**Cause:** Context trying to import adapters that import context.
**Fix:** Use forward references (strings) in type hints or restructure imports.

---

## Estimated Time to Complete

- Route handler updates: **2-4 hours**
- VideoProcessor refactor: **1-2 hours**
- Test fixes: **1-2 hours**
- Smoke testing: **30 minutes**

**Total: 4.5-8.5 hours**

---

## Success Criteria

✅ Phase 1 is complete when:
1. You can import any module without triggering network calls
2. All adapters are created in composition roots (lifespan/bootstrap)
3. All dependencies are injected, not imported as globals
4. Tests pass and use proper dependency mocking
5. The application runs correctly end-to-end

You will know you succeeded when:
- You can run `python -c "import src.adapters.database"` without Redis/Supabase connections
- Tests run fast because they don't need live services
- You can override any dependency in tests without monkey-patching
- The codebase is ready for Phase 2 refactoring (service extraction, domain isolation)
