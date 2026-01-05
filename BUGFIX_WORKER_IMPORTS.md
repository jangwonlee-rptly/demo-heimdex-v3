# Bug Fix: Worker Import Error for Reference Photo Processing

## Issue
When uploading reference photos for person profiles, the worker failed with:
```
ModuleNotFoundError: No module named 'services'
File "/app/libs/tasks/reference_photo.py", line 42, in process_reference_photo
  from services.worker.src.tasks import get_worker_context
```

## Root Cause
The task handler in `libs/tasks/reference_photo.py` was using an incorrect absolute import path:
```python
from services.worker.src.tasks import get_worker_context
from services.worker.src.domain.person_photo_processor import PersonPhotoProcessor
```

**Why this failed:**
1. Worker runs with `/app` as working directory (inside Docker container)
2. Python path includes `/app` but not the monorepo root
3. The path `services.worker.src.*` doesn't exist from worker's perspective
4. Other task files correctly use `from src.*` imports

## Files Changed

### `libs/tasks/reference_photo.py` (lines 42-43)

**Before:**
```python
# Lazy import to avoid import-time side effects
from services.worker.src.tasks import get_worker_context
from services.worker.src.domain.person_photo_processor import PersonPhotoProcessor
```

**After:**
```python
# Lazy import to avoid import-time side effects
from src.tasks import get_worker_context
from src.domain.person_photo_processor import PersonPhotoProcessor
```

## Why This Pattern is Correct

When the worker runs inside its Docker container:
- Working directory: `/app`
- Python path includes: `/app`
- Source layout:
  ```
  /app/
    src/              # Worker source code
      tasks.py
      domain/
        person_photo_processor.py
    libs/             # Shared task definitions
      tasks/
        reference_photo.py
  ```

From `libs/tasks/reference_photo.py`, the correct import is `from src.*` because:
1. Python resolves relative to `/app` (in sys.path)
2. `/app/src/` contains the modules we need
3. This matches the pattern used by all other task files

## Verification

All other task files already use the correct pattern:
```python
# libs/tasks/video_processing.py
from src.tasks import get_worker_context
from src.domain.video_processor import VideoProcessor

# libs/tasks/scene_export.py
from src.tasks import get_worker_context

# libs/tasks/highlight_export.py
from src.tasks import get_worker_context
```

## Deployment

Rebuild and restart worker:
```bash
docker-compose build worker
docker-compose up -d worker
```

Verify startup:
```bash
docker-compose logs worker --tail 20
```

Should see:
```
worker-1  | 2026-01-05 10:07:04,659 - src.tasks - INFO - Worker bootstrapped successfully
worker-1  | 2026-01-05 10:07:04,673 - dramatiq.MainProcess - INFO - Dramatiq '2.0.0' is booting up.
```

## Testing

After deployment:
1. Navigate to `/people`
2. Create a person
3. Click "View Details" → "Add Photos"
4. Select and upload face photos
5. Photos should process successfully
6. Check worker logs for successful processing:
   ```bash
   docker-compose logs worker -f
   ```
7. Should see:
   ```
   Starting reference photo processing for photo_id={uuid}
   Completed reference photo processing for photo_id={uuid}
   ```

## Impact
- **Severity**: Critical (feature completely broken)
- **Scope**: All reference photo uploads
- **User Impact**: Users could not add photos to person profiles
- **Time to Fix**: ~5 minutes (straightforward import path fix)

## Root Cause Analysis

**Why did this happen?**
- This task was the last one implemented (for People feature)
- Import pattern was likely copied from somewhere else and adapted incorrectly
- All other task files use the correct pattern, suggesting this was an isolated mistake
- No integration tests verify worker can import and run tasks

**Prevention:**
1. Use consistent import patterns across all task files
2. Add smoke tests that verify each task can be imported
3. Run worker build/test in CI before deployment
4. Document the correct import pattern in `libs/tasks/README.md`

## Lessons Learned
1. Always match import patterns with existing code in the same directory
2. Absolute imports like `services.worker.*` don't work inside worker container
3. Worker Python environment is isolated from monorepo structure
4. Import errors fail at runtime (task execution), not at worker startup
5. Check logs carefully for `ModuleNotFoundError` vs other import issues
