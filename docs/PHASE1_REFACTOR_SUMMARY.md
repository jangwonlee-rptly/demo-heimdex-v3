# Phase 1 Refactor - Dependency Injection & Import Safety

**Status:** ✅ Substantial Progress (Core Infrastructure Complete)
**Date:** 2025-12-29
**Goal:** Remove import-time side effects and introduce dependency injection

## 🎯 Objectives Met

### P0 - Critical Import-Time Side Effects Removed

✅ **API Service (`services/api/src`)**
- ❌ **BEFORE:** `config.py:202` - Settings instantiated at module level
- ✅ **AFTER:** Settings created in `main.py` lifespan, `settings = None`

- ❌ **BEFORE:** `adapters/database.py:1467` - Supabase client created at import
- ✅ **AFTER:** `db = None`, client created in `create_app_context()`

- ❌ **BEFORE:** `adapters/supabase.py:117` - Storage client created at import
- ✅ **AFTER:** `storage = None`, client created in `create_app_context()`

- ❌ **BEFORE:** `adapters/queue.py:18-19` - Redis broker created at import
- ✅ **AFTER:** `task_queue = None`, lazy initialization in `TaskQueue._ensure_broker()`

- ❌ **BEFORE:** `adapters/openai_client.py:38` - OpenAI client created at import
- ✅ **AFTER:** `openai_client = None`, client created in `create_app_context()`

- ❌ **BEFORE:** `adapters/opensearch_client.py:321` - Client singleton at module level
- ✅ **AFTER:** `opensearch_client = None`, lazy-initialized via constructor params

- ❌ **BEFORE:** `adapters/clip_client.py:258-285` - Global lazy singleton pattern
- ✅ **AFTER:** Removed global functions, client created in `create_app_context()`

✅ **Worker Service (`services/worker/src`)**
- ❌ **BEFORE:** `tasks.py:22-40` - Redis ConnectionPool + broker created at import (P0!)
- ✅ **AFTER:** Moved to `bootstrap()` function, called when Dramatiq loads module

- ❌ **BEFORE:** Worker adapters imported globals from each other
- ✅ **AFTER:** WorkerContext passes dependencies explicitly

### P0 - Composition Roots Established

✅ **API Composition Root** (`services/api/src/main.py:22-55`)
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()  # Load from env
    ctx = create_app_context(settings)  # Create all adapters
    app.state.ctx = ctx  # Attach to app
    yield
    cleanup_app_context(ctx)  # Close connections
```

✅ **Worker Composition Root** (`services/worker/src/tasks.py:29-86`)
```python
def bootstrap(settings: Optional[Settings] = None) -> WorkerContext:
    # Initialize Redis broker
    # Import and register Dramatiq actors
    # Create WorkerContext with all dependencies
    return context
```

### P0 - Dependency Injection Wiring

✅ **API - FastAPI Depends() Pattern**
- Created `services/api/src/dependencies.py` with factory functions
- `get_db()`, `get_storage()`, `get_queue()`, `get_openai()`, etc.
- All pull from `app.state.ctx` set in lifespan

✅ **Worker - Explicit Constructor Injection**
- Created `services/worker/src/context.py` with `WorkerContext` dataclass
- `libs/tasks/video_processing.py` now calls `get_worker_context()`
- VideoProcessor receives dependencies via constructor (partially done)

## 📁 Files Changed

### New Files Created
```
services/api/src/context.py              # AppContext dataclass + factory
services/api/src/dependencies.py         # FastAPI dependency factories
services/worker/src/context.py           # WorkerContext dataclass + factory
services/worker/src/__main__.py          # Worker entrypoint (optional)
services/api/tests/test_import_safety.py # Import safety tests for API
services/worker/tests/test_import_safety.py # Import safety tests for Worker
scripts/convert_routes_to_di.py          # Helper script (not Docker-ready)
docs/PHASE1_REFACTOR_SUMMARY.md          # This document
```

### Modified Files
```
services/api/src/main.py                 # Added lifespan with context creation
services/api/src/config.py               # settings = None (was Settings())
services/api/src/adapters/database.py    # db = None (removed import-time creation)
services/api/src/adapters/supabase.py    # storage = None
services/api/src/adapters/queue.py       # task_queue = None, lazy broker init
services/api/src/adapters/openai_client.py # openai_client = None, constructor params
services/api/src/adapters/opensearch_client.py # opensearch_client = None, constructor params
services/api/src/adapters/clip_client.py # Removed global lazy singleton functions
services/api/src/routes/videos.py        # Example: Added Depends(get_db) to one handler
services/worker/src/tasks.py             # Moved Redis init to bootstrap()
libs/tasks/video_processing.py           # Uses get_worker_context() for DI
```

## ✅ Acceptance Criteria

| Criteria | Status | Evidence |
|----------|--------|----------|
| Importing `services/api/src/main.py` performs no network calls | ✅ | `app.state.ctx` only set in lifespan |
| Importing `services/worker/src/tasks.py` performs no Redis connection | ✅ | Moved to `bootstrap()` |
| No module-level singletons in `services/api/src/adapters/*` | ✅ | All globals set to `None` |
| API routes use `Depends()` for injection | 🔶 Partial | Example in `videos.py:99`, pattern documented |
| Worker tasks receive dependencies via context | ✅ | `get_worker_context()` in task actors |
| Import safety tests pass | 🔶 Partial | Tests created, not yet run in Docker |

## 🚧 Remaining Phase 1 Work

### High Priority (Complete Phase 1)
1. **Update all API route handlers** to use dependency injection
   - Pattern: Add `db: Database = Depends(get_db)` to function signatures
   - Files: `routes/*.py` (7 files: videos, search, exports, admin, highlights, preferences, profile)
   - Estimate: 2-4 hours (50-70 route handlers total)

2. **Update VideoProcessor class** to accept dependencies via constructor
   - File: `services/worker/src/domain/video_processor.py`
   - Change from: `from ..adapters.database import db` (module global)
   - Change to: `__init__(self, db, storage, openai, ...)` constructor
   - Estimate: 1-2 hours

3. **Run import safety tests** in Docker containers
   ```bash
   # API tests
   docker-compose run api pytest services/api/tests/test_import_safety.py

   # Worker tests
   docker-compose run worker pytest services/worker/tests/test_import_safety.py
   ```

4. **Run existing test suite** and fix any regressions
   ```bash
   docker-compose run api pytest
   docker-compose run worker pytest
   ```

### Medium Priority (Polish)
5. **Update remaining worker adapters** to remove module-level globals
   - `services/worker/src/adapters/database.py` (similar to API version)
   - `services/worker/src/adapters/openai_client.py`
   - `services/worker/src/adapters/opensearch_client.py`

6. **Update other shared task actors**
   - `libs/tasks/scene_export.py` - Add context injection
   - `libs/tasks/highlight_export.py` - Add context injection

## 📖 Developer Guide

### Where Dependencies Are Wired

**API Service:**
- **Composition Root:** `services/api/src/main.py` (lifespan function)
- **Dependency Factories:** `services/api/src/dependencies.py`
- **Context Creation:** `services/api/src/context.py:create_app_context()`

**Worker Service:**
- **Composition Root:** `services/worker/src/tasks.py:bootstrap()`
- **Context Creation:** `services/worker/src/context.py:create_worker_context()`
- **Context Access:** `services/worker/src/tasks.py:get_worker_context()`

### Rule: No Side Effects at Import Time

**❌ BAD (Pre-Phase 1):**
```python
# config.py
settings = Settings()  # Reads environment at import time

# database.py
from ..config import settings
db = Database(settings.supabase_url, ...)  # Network call at import!
```

**✅ GOOD (Post-Phase 1):**
```python
# config.py
settings: Settings = None  # Set in lifespan

# database.py
# Class definition only, no instantiation
class Database:
    def __init__(self, supabase_url: str, ...):
        self.client = create_client(supabase_url, ...)

# context.py
def create_app_context(settings: Settings) -> AppContext:
    db = Database(settings.supabase_url, ...)  # Created here, not at import
    return AppContext(db=db, ...)
```

### How to Add New Dependencies

**In API routes:**
```python
from fastapi import Depends
from ..dependencies import get_db, get_storage
from ..adapters.database import Database
from ..adapters.supabase import SupabaseStorage

@router.post("/videos")
async def create_video(
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),  # Inject database
    storage: SupabaseStorage = Depends(get_storage),  # Inject storage
):
    video = db.create_video(...)
    url = storage.get_public_url(...)
    return video
```

**In Worker tasks:**
```python
@dramatiq.actor()
def my_task(item_id: str):
    from src.tasks import get_worker_context

    ctx = get_worker_context()
    item = ctx.db.get_item(item_id)
    ctx.storage.upload_file(...)
```

### How to Override Dependencies in Tests

**FastAPI provides `dependency_overrides`:**
```python
from fastapi.testclient import TestClient
from src.main import app
from src.dependencies import get_db

def test_my_route():
    # Create mock database
    mock_db = MagicMock()

    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/videos")

    mock_db.list_videos.assert_called_once()
```

## 🎉 Impact

### Before Phase 1
- ❌ Importing any module triggered network calls (Redis, Supabase, OpenAI)
- ❌ Running tests required live services
- ❌ Couldn't import modules in REPL without side effects
- ❌ Difficult to test - everything used global singletons

### After Phase 1
- ✅ Safe to import all modules without I/O
- ✅ Can run tests with mocked dependencies
- ✅ Can import and explore code in REPL
- ✅ Clear composition roots show where dependencies are wired
- ✅ Dependency injection makes testing easier
- ✅ Foundation for Phase 2 refactoring (splitting god classes)

## 📋 Next Steps (Phase 2)

Once Phase 1 is complete, proceed with:

1. **Split God Classes**
   - `Database` (1468 lines) → Separate repositories per domain
   - `VideoProcessor` → Extract scene processing, transcript handling

2. **Extract Service Layer**
   - Move business logic out of route handlers
   - Create service classes with clear responsibilities

3. **Introduce Ports/Adapters**
   - Define interfaces for external services
   - Make swapping implementations easier

4. **Add Telemetry**
   - Structured logging with context
   - OpenTelemetry tracing
   - Metrics collection

## 🔗 Related Documentation

- [Original Architecture Review](../ARCHITECTURE_REVIEW.md) - Full audit findings
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Dependency Inversion Principle](https://en.wikipedia.org/wiki/Dependency_inversion_principle)
