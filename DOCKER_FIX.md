# Docker Fix for Shared Actor Architecture

## Problem

After refactoring to use a shared actor in `libs/tasks/`, the containers failed to start with:

```
ModuleNotFoundError: No module named 'libs'
```

## Root Cause

The Docker build context was set to individual service directories (`./services/api`, `./services/worker`), but the `libs/` directory is at the **project root**. Docker can only access files within the build context.

## Solution

### 1. Updated docker-compose.yml

Changed build context from service directories to project root:

**Before:**
```yaml
api:
  build:
    context: ./services/api
    dockerfile: Dockerfile
```

**After:**
```yaml
api:
  build:
    context: .  # Project root
    dockerfile: ./services/api/Dockerfile
```

### 2. Updated Dockerfiles

Updated COPY paths to account for the new context:

**API Dockerfile** (`services/api/Dockerfile`):
```dockerfile
WORKDIR /app

# Copy dependency files (updated path)
COPY services/api/pyproject.toml ./

# Install dependencies...

# Copy shared libraries (NEW)
COPY libs/ ./libs/

# Copy application code (updated path)
COPY services/api/src/ ./src/

# PYTHONPATH includes /app (where libs/ lives)
ENV PYTHONPATH=/app
```

**Worker Dockerfile** (`services/worker/Dockerfile`):
```dockerfile
WORKDIR /app

# Copy dependency files (updated path)
COPY services/worker/pyproject.toml ./

# Install dependencies...

# Copy shared libraries (NEW)
COPY libs/ ./libs/

# Copy application code (updated path)
COPY services/worker/src/ ./src/

# PYTHONPATH includes /app
ENV PYTHONPATH=/app
```

### 3. Simplified Python imports

Removed `sys.path` manipulation since `PYTHONPATH=/app` handles it:

**Before:**
```python
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from libs.tasks import process_video  # noqa: E402
```

**After:**
```python
from libs.tasks import process_video
```

## Container Structure

With these changes, both containers have this structure:

```
/app/
├── libs/
│   └── tasks/
│       ├── __init__.py
│       └── video_processing.py  (shared actor)
└── src/
    ├── (API or Worker code)
    └── ...
```

## Building and Running

```bash
# Rebuild containers with new Dockerfiles
docker-compose build

# Start services
docker-compose up

# Or do both
docker-compose up --build
```

## Verification

Check that both services start successfully:

```bash
# API should start without errors
docker-compose logs api

# Worker should show:
# "Worker initialized with process_video actor from libs.tasks"
docker-compose logs worker
```

## Railway Deployment

For Railway, ensure the build uses the repository root:

1. Go to Railway Dashboard → Service Settings
2. Build → Root Directory: **/** (root)
3. Build → Dockerfile Path: `services/api/Dockerfile` (or `services/worker/Dockerfile`)

Or create `railway.json` in project root:

```json
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "services/api/Dockerfile"
  }
}
```

## Files Changed

- ✏️ `docker-compose.yml` - Build context changed to `.`
- ✏️ `services/api/Dockerfile` - Updated paths, added `COPY libs/`
- ✏️ `services/worker/Dockerfile` - Updated paths, added `COPY libs/`
- ✏️ `services/api/src/adapters/queue.py` - Removed sys.path manipulation
- ✏️ `services/worker/src/tasks.py` - Removed sys.path manipulation

## Summary

✅ Build context is now project root
✅ Both Dockerfiles copy `libs/` directory
✅ Both Dockerfiles update paths to `services/{service}/...`
✅ PYTHONPATH=/app makes `libs/` importable
✅ No sys.path manipulation needed

The containers now have access to the shared actor module! 🚀
