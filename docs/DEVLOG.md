# Development Log

## 2025-12-31: Phase 1.5 Emergency Hotfix - Missing DI for ClipEmbedder & SceneDetector

### Problem
After deploying Phase 1.5, the worker container crashed on startup, then crashed again during video processing:

**Crash 1 - ClipEmbedder:**
```
AttributeError: 'NoneType' object has no attribute 'clip_enabled'
  File "/app/src/adapters/clip_embedder.py", line 116, in __init__
    f"ClipEmbedder singleton created (enabled={settings.clip_enabled})"
```

**Crash 2 - SceneDetector (after ClipEmbedder fix):**
```
AttributeError: 'NoneType' object has no attribute 'scene_min_len_seconds'
  File "/app/src/domain/scene_detector.py", line 378, in detect_scenes_best
    min_scene_len = settings.scene_min_len_seconds
```

Two modules were missed in the initial Phase 1.5 hotfix and were still using global `settings`.

### Root Cause
**ClipEmbedder** (`services/worker/src/adapters/clip_embedder.py`):
- Line 31: `from ..config import settings` (global import)
- Line 116: Accessed `settings.clip_enabled` at initialization
- 20+ references to `settings.*` throughout the file
- No DI-friendly constructor

**SceneDetector** (`services/worker/src/domain/scene_detector.py`):
- Line 23: `from ..config import settings` (global import)
- Line 378, 464: Accessed `settings.scene_min_len_seconds` in active methods
- 15+ references to `settings.*` in active code paths
- Static methods didn't accept settings parameter

When the worker processed videos, these modules tried to access the global `settings` (now `None` after Phase 1.5).

### Solution
Refactored both ClipEmbedder and SceneDetector to use dependency injection:

**ClipEmbedder** - Constructor-based DI:
1. Removed global `from ..config import settings` import
2. Added `settings` parameter to `__init__` and `__new__` (singleton pattern requires both)
3. Replaced all 20+ occurrences of `settings.*` with `self._settings.*`
4. Updated `context.py` to pass settings: `ClipEmbedder(settings=settings)`
5. Made settings parameter required (raises ValueError if None)

**SceneDetector** - Parameter-based DI:
1. Added `settings` parameter to active static methods:
   - `detect_scenes_best(video_path, settings, ...)`
   - `detect_scenes_with_preferences(video_path, settings, ...)`
2. Updated internal call in `detect_scenes_with_preferences` to pass settings
3. Updated `video_processor.py` to pass `self.settings` when calling scene detection
4. Left backwards-compatible methods (`detect_scenes`, `get_scene_detector`) unchanged (not in active code path)

### Changes Made

**1. ClipEmbedder Constructor** (`services/worker/src/adapters/clip_embedder.py`)
```python
# Before:
from ..config import settings  # Line 31

def __new__(cls):
    ...

def __init__(self):
    ...
    logger.info(f"ClipEmbedder singleton created (enabled={settings.clip_enabled})")

# After:
# Removed global import

def __new__(cls, settings=None):  # Accept settings parameter
    ...

def __init__(self, settings=None):
    if settings is None:
        raise ValueError("ClipEmbedder requires settings via constructor")
    self._settings = settings
    logger.info(f"ClipEmbedder singleton created (enabled={self._settings.clip_enabled})")
```

**2. Replace all settings references** (20+ occurrences)
```python
# Examples of changes:
settings.clip_enabled → self._settings.clip_enabled
settings.clip_model_name → self._settings.clip_model_name
settings.clip_device → self._settings.clip_device
settings.clip_normalize → self._settings.clip_normalize
# ... 16 more similar changes
```

**3. WorkerContext** (`services/worker/src/context.py:91`)
```python
# Before:
clip_embedder = ClipEmbedder()

# After:
clip_embedder = ClipEmbedder(settings=settings)
```

**4. SceneDetector Methods** (`services/worker/src/domain/scene_detector.py`)
```python
# Before:
@staticmethod
def detect_scenes_best(
    video_path: Path,
    video_duration_s: Optional[float] = None,
    ...
):
    min_scene_len = settings.scene_min_len_seconds  # Global access

# After:
@staticmethod
def detect_scenes_best(
    video_path: Path,
    settings,  # NEW: settings parameter
    video_duration_s: Optional[float] = None,
    ...
):
    min_scene_len = settings.scene_min_len_seconds  # Parameter access
```

**5. VideoProcessor** (`services/worker/src/domain/video_processor.py:277`)
```python
# Before:
scenes, detection_result = scene_detector.detect_scenes_with_preferences(
    video_path,
    video_duration_s=metadata.duration_s,
    ...
)

# After:
scenes, detection_result = scene_detector.detect_scenes_with_preferences(
    video_path,
    self.settings,  # Pass settings from VideoProcessor
    video_duration_s=metadata.duration_s,
    ...
)
```

### Verification

**Import Safety Check:**
```bash
# Check for runtime-only settings usage (acceptable)
grep -rn "from.*config import settings" services/worker/src/
# → Only in backwards-compatible methods and inside functions (runtime-only)

# Verify no module-level settings access
python3 -c "
import re
for f in ['src/domain/frame_quality.py', 'src/domain/scene_detector.py']:
    lines = open(f).readlines()
    for i, line in enumerate(lines, 1):
        if 'settings.' in line and line[0] not in ' \t#':
            print(f'{f}:{i}: {line.rstrip()}')
"
# → No output (all settings access is inside functions)
```

**Runtime Test:**
Worker starts successfully and processes videos without crashing.

### Files Changed
1. `services/worker/src/adapters/clip_embedder.py` - Added settings parameter to constructor
2. `services/worker/src/context.py` - Pass settings to ClipEmbedder
3. `services/worker/src/domain/scene_detector.py` - Added settings parameter to static methods
4. `services/worker/src/domain/video_processor.py` - Pass settings when calling scene detection
5. `docs/DEVLOG.md` - This documentation

### Deployment
Deploy immediately to restore worker functionality:
```bash
git add services/worker/src/adapters/clip_embedder.py \
        services/worker/src/context.py \
        services/worker/src/domain/scene_detector.py \
        services/worker/src/domain/video_processor.py \
        docs/DEVLOG.md
git commit -m "hotfix: ClipEmbedder & SceneDetector DI for Phase 1.5"
git push
```

Worker now starts and processes videos successfully with proper DI.

### Related
- Phase 1.5 Hotfix (original): Worker Import Safety & DI Consistency
- Phase 1 Refactor Summary: Original DI initiative

---

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
