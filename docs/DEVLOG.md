# Development Log

## 2025-12-31: Phase 1.5 Hotfix - Worker Import Safety & DI Consistency

### Problem
Phase 1 DI refactor was incomplete for the worker service. The audit revealed critical violations:
- `services/worker/src/config.py:146` had module-level `settings = Settings()` instantiation
- `services/worker/src/adapters/opensearch_client.py:353` created global `opensearch_client` instance
- Worker adapters used legacy no-arg constructors instead of dependency injection
- Database adapter imported global `opensearch_client` at runtime instead of using DI
- OpenAI client imported global `settings` at runtime

These violations meant importing worker modules would trigger environment variable reads and potentially create clients at import time, breaking Phase 1's import-safety guarantees.

### Solution
Implemented minimal DI hotfix to restore Phase 1 compliance:
1. Removed all module-level adapter instantiations
2. Refactored adapters to accept configuration via constructor parameters
3. Updated `WorkerContext` to be the single composition root
4. Added comprehensive import-safety tests

### Changes Made

**1. Config Module** (`services/worker/src/config.py`)
```python
# Before:
settings = Settings()

# After:
settings: Optional[Settings] = None  # Only created in bootstrap()
```

**2. OpenSearch Client** (`services/worker/src/adapters/opensearch_client.py`)
- Added DI-friendly constructor:
  ```python
  def __init__(self, opensearch_url: str, timeout_s: float,
               index_scenes: str, indexing_enabled: bool = True)
  ```
- Replaced all `settings.opensearch_*` with `self.*` attributes
- Removed global singleton: `opensearch_client = None`

**3. Database Adapter** (`services/worker/src/adapters/database.py`)
- Added `opensearch: Optional[OpenSearchClient]` parameter to constructor
- Removed runtime import of global `opensearch_client`
- Updated methods to use `self.opensearch` instead
- Removed global singleton: `db = None`

**4. OpenAI Client** (`services/worker/src/adapters/openai_client.py`)
- Added DI-friendly constructor:
  ```python
  def __init__(self, api_key: str, settings=None)
  ```
- Replaced 26 occurrences of `settings.*` with `self.settings.*`
- Backward compatible: lazy-loads settings if not provided (for tests)
- Removed global singleton: `openai_client = None`

**5. Worker Context** (`services/worker/src/context.py`)
```python
# Create OpenSearch with explicit config
opensearch = OpenSearchClient(
    opensearch_url=settings.opensearch_url,
    timeout_s=settings.opensearch_timeout_s,
    index_scenes=settings.opensearch_index_scenes,
    indexing_enabled=settings.opensearch_indexing_enabled,
)

# Pass OpenSearch to Database
db = Database(
    supabase_url=settings.supabase_url,
    supabase_key=settings.supabase_service_role_key,
    opensearch=opensearch,  # DI instead of global import
)

# Create OpenAI with explicit config
openai = OpenAIClient(
    api_key=settings.openai_api_key,
    settings=settings,  # For transcription config
)
```

**6. Import Safety Tests** (`services/worker/tests/test_import_safety.py`)
Added 4 new tests:
- `test_import_config_no_settings_instance`: Verifies `config.settings is None`
- `test_import_database_no_global_db`: Verifies `database.db is None`
- `test_import_opensearch_no_global_client`: Verifies `opensearch_client.opensearch_client is None`
- `test_import_openai_no_global_client`: Verifies `openai_client.openai_client is None`

**7. Test Fixtures** (`services/worker/tests/test_transcription_quality.py`)
Updated to use new DI pattern:
```python
mock_settings = Settings()
client = OpenAIClient(api_key="test-key", settings=mock_settings)
```

### Verification

**Grep Searches (All Clean):**
```bash
# No module-level Settings() instantiation
rg "\bsettings\b\s*=\s*Settings\(" services/worker/src
# → Only in bootstrap() function (line 49 of tasks.py)

# No module-level OpenSearch instantiation
rg "opensearch_client\s*=\s*OpenSearchClient\(" services/worker/src
# → No matches

# No module-level Database instantiation
rg "^\s*db\s*=\s*Database\(" services/worker/src
# → Only in context.py (inside function) and scripts

# No module-level OpenAI instantiation
rg "openai_client\s*=\s*OpenAIClient\(" services/worker/src
# → No matches
```

**Test Results:**
```
Import Safety Tests: 8 passed, 2 skipped (torch-related)
Overall Worker Tests: 51 passed, 2 failed, 2 skipped
```
- All import safety tests passing
- 2 pre-existing test failures unrelated to DI changes

### Architecture

**Before (Violated Phase 1):**
```
module import → settings = Settings() → env vars read at import time ❌
module import → opensearch_client = OpenSearchClient() → client created at import ❌
database.py → from .opensearch_client import opensearch_client → global coupling ❌
```

**After (Phase 1 Compliant):**
```
bootstrap() → settings = Settings() → env vars read at runtime ✅
create_worker_context(settings) → all adapters created with explicit params ✅
Database(opensearch=...) → dependency injected via constructor ✅
```

### Benefits

1. **Import Safety**: Importing worker modules no longer reads environment variables or creates clients
2. **Testability**: Adapters can be tested with mock configuration without global state
3. **Consistency**: Worker now matches API service's DI patterns
4. **Composition Root**: `WorkerContext` is the single place where dependencies are wired
5. **Regression Prevention**: New tests catch future violations

### Acceptance Criteria Met

| Criterion | Status | Evidence |
|-----------|--------|----------|
| No Settings() at import time | ✅ | `config.py:147` now `= None` |
| No module-level adapter singletons | ✅ | All adapters now `= None` placeholders |
| Dependencies created only in bootstrap/context | ✅ | Verified via composition root |
| Database doesn't import globals | ✅ | Uses injected `self.opensearch` |
| Worker adapters use constructor DI | ✅ | Explicit parameters match API patterns |
| Tests validate regressions | ✅ | 4 new import safety tests |

### Runtime Behavior

**No Functional Changes**: This refactor only changes how dependencies are created, not what they do:
- OpenSearch indexing remains "best effort" and non-blocking
- Settings loaded once at worker startup
- All feature behavior unchanged
- Performance unchanged

### Future Work

Consider Phase 2 improvements:
- Remove backward-compatible `settings=None` fallback in OpenAIClient after all callsites updated
- Audit `libs/tasks/scene_export.py` and `highlight_export.py` for DI compliance
- Consider extracting transcription config into separate settings class

### Related Documentation

- Phase 1 Audit Report: Full findings and recommendations
- `docs/PHASE1_REFACTOR_SUMMARY.md`: Original Phase 1 goals
- `docs/PHASE1_COMPLETION_CHECKLIST.md`: Acceptance criteria

---

## 2025-11-24: Real-time Dashboard Updates

### Problem
Users had no visibility into video processing status without manually refreshing the dashboard. After uploading a video, they would need to keep refreshing the page to see when processing completed (PENDING → PROCESSING → READY).

### Solution
Implemented real-time updates using Supabase Realtime to automatically refresh the dashboard when video status changes.

### Changes Made

**1. Database Migration** (`infra/migrations/008_enable_realtime.sql`)
```sql
ALTER PUBLICATION supabase_realtime ADD TABLE videos;
```
- Enabled Postgres LISTEN/NOTIFY on the `videos` table
- Allows Supabase Realtime to broadcast changes to connected clients

**2. Frontend Updates** (`services/frontend/src/app/dashboard/page.tsx`)
- Added Supabase Realtime subscription in `useEffect` hook
- Listens for `UPDATE` events on the `videos` table
- Updates video list in-place when changes are received
- Shows toast notifications when status changes
- Properly cleans up subscription on unmount

**3. UI Enhancements** (`services/frontend/src/app/globals.css`)
- Added slide-in animation for toast notifications
- Toast appears top-right with color-coded status:
  - Green: Processing complete (READY)
  - Blue: Processing started (PROCESSING)
  - Red: Processing failed (FAILED)
- Auto-dismisses after 5 seconds

**4. Documentation** (`README.md`)
- Added real-time updates to features list
- Included new migration in setup instructions

### Technical Details

**Architecture:**
```
Worker → PostgreSQL → Supabase Realtime → WebSocket → Dashboard
```

**Flow:**
1. Worker updates video status in Postgres
2. Postgres triggers NOTIFY event
3. Supabase Realtime broadcasts to subscribed clients
4. Dashboard receives payload and updates React state
5. UI re-renders with new status + shows notification

**Key Code:**
```typescript
useEffect(() => {
  const channel = supabase
    .channel('videos-changes')
    .on('postgres_changes', {
      event: 'UPDATE',
      schema: 'public',
      table: 'videos',
    }, (payload) => {
      // Update video list
      setVideos((current) =>
        current.map((v) => v.id === payload.new.id ? payload.new : v)
      );
      // Show notification
      if (payload.old.status !== payload.new.status) {
        setNotification({ message: '...', type: 'success' });
      }
    })
    .subscribe();

  return () => supabase.removeChannel(channel);
}, []);
```

### Benefits

- **No polling**: Efficient, event-driven updates
- **Instant feedback**: Users see status changes immediately
- **Better UX**: Toast notifications provide clear feedback
- **Multi-tab support**: Updates work across all open tabs
- **Scalable**: Supabase handles connection management

### Testing

1. Upload a video from `/upload`
2. Navigate to `/dashboard`
3. Watch the status badge update automatically:
   - PENDING (yellow) → PROCESSING (blue) → READY (green)
4. Toast notification appears when processing completes
5. No manual refresh needed

### Future Improvements

Potential enhancements:
- Add progress percentage updates during processing
- Show estimated time remaining
- Add sound/browser notification for completed videos
- Extend to other real-time features (new search results, etc.)

### Migration Instructions

Run in Supabase SQL Editor:
```bash
# Copy migration file content
cat infra/migrations/008_enable_realtime.sql

# Execute in Supabase Dashboard → SQL Editor
ALTER PUBLICATION supabase_realtime ADD TABLE videos;
```

### Deployment Notes

- No backend changes required
- Migration must be applied before frontend deployment
- Works with existing Supabase free tier
- No additional costs for Realtime (included in Supabase plans)
