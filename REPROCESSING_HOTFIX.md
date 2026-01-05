# Reprocessing Pipeline Hotfix - Import Errors

## Issues

### Issue 1: ModuleNotFoundError
```
ModuleNotFoundError: No module named 'src.domain.reprocess'
```
**Root Cause:** The API service was trying to import from worker's domain module.

### Issue 2: IndexError (after first fix)
```
IndexError: 4
```
**Root Cause:** Incorrect parent directory navigation - used `parents[4]` instead of `parents[2]` for API, and `parents[5]` instead of `parents[3]` for worker.

## Solution

Created a shared constants module in `libs/` that both services can access.

### Files Changed

1. **`libs/shared_constants.py`** (NEW)
   - Contains `LATEST_EMBEDDING_SPEC_VERSION = "2026-01-06"`
   - Shared between API and worker services

2. **`services/worker/src/domain/reprocess/latest_reprocess.py`** (MODIFIED)
   - Changed to import `LATEST_EMBEDDING_SPEC_VERSION` from `shared_constants`
   - Added path manipulation: `parents[3] / "libs"` (Docker path: `/app/src/domain/reprocess/latest_reprocess.py`)

3. **`services/worker/src/domain/reprocess/__init__.py`** (MODIFIED)
   - Imports and re-exports `LATEST_EMBEDDING_SPEC_VERSION` from `shared_constants`
   - Added path manipulation: `parents[3] / "libs"` (Docker path: `/app/src/domain/reprocess/__init__.py`)

4. **`services/api/src/routes/admin.py`** (MODIFIED)
   - Changed import from `src.domain.reprocess` to `shared_constants`
   - Added path manipulation: `parents[2] / "libs"` (Docker path: `/app/src/routes/admin.py`, lazy import inside endpoint)

### Why This Works

Both Dockerfiles already copy the `libs/` directory:
- `services/api/Dockerfile` line 29: `COPY libs/ ./libs/`
- `services/worker/Dockerfile` line 46: `COPY libs/ ./libs/`

Both set `PYTHONPATH=/app`, so the libs are accessible.

The path manipulation code adds `libs/` to `sys.path` dynamically, allowing imports from the shared constants module.

## Deployment Steps

1. **Rebuild Docker images:**
   ```bash
   docker compose build api worker
   ```

2. **Deploy to production** (your deployment process)

3. **Verify the fix:**
   - Navigate to admin panel
   - Click "Reprocess Embeddings (All)" button
   - Should see success message with spec version

## Testing Locally

```bash
# Build services
docker compose -f docker-compose.reprocess.yml build

# Start services
docker compose -f docker-compose.reprocess.yml up -d redis worker api

# Wait for services to start
sleep 5

# Test via API (replace with actual admin token)
curl -X POST http://localhost:8000/v1/admin/reprocess-embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -d '{"scope": "all", "force": false}'

# Expected response:
# {
#   "status": "queued",
#   "spec_version": "2026-01-06",
#   "scope": "all",
#   "video_count": 42,
#   "message": "Queued embedding reprocessing for 42 video(s) using spec version 2026-01-06"
# }

# Check logs
docker compose -f docker-compose.reprocess.yml logs api | grep "spec_version"
docker compose -f docker-compose.reprocess.yml logs worker | grep "spec_version"
```

## Future Updates

When updating the embedding spec version:

**Edit only one file:** `libs/shared_constants.py`

```python
LATEST_EMBEDDING_SPEC_VERSION = "2026-XX-XX"  # Update this
```

All services will automatically use the new version after rebuilding and deploying.

## Architecture Decision

**Why use path manipulation instead of package installation?**

1. **Simplicity:** No need to publish internal packages
2. **Monorepo-friendly:** Keeps shared code in `libs/` as intended
3. **No build step:** Direct import without package installation
4. **Consistency:** Both services already copy `libs/` in Dockerfiles

**Alternative considered:**
- Making `libs/` a proper Python package with setup.py and installing it
- Rejected due to added complexity and build overhead

## Verification

All syntax checks pass:
```bash
python3 -m py_compile libs/shared_constants.py
python3 -m py_compile services/worker/src/domain/reprocess/latest_reprocess.py
python3 -m py_compile services/api/src/routes/admin.py
```

---

**Status:** ✅ Fixed
**Date:** 2026-01-06
**Version:** 2026-01-06
