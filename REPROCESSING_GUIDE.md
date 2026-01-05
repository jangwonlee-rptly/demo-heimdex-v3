# Embedding Reprocessing Pipeline Guide

## Overview

The Heimdex reprocessing pipeline provides a unified, idempotent way to regenerate all embeddings using the latest embedding methods. This ensures that after updating embedding logic (e.g., new CLIP models, updated normalization, new embedding channels), all videos can be updated to use the new pipeline.

**Key Features:**
- ✅ **Single Source of Truth**: All reprocessing uses `ReprocessSpec` which defines the latest embedding methods
- ✅ **Idempotent & Safe**: Can be re-run without duplicating data or causing corruption
- ✅ **Versioned**: `LATEST_EMBEDDING_SPEC_VERSION` tracks which pipeline version is being used
- ✅ **Multi-Channel**: Admin UI, CLI, and programmatic access
- ✅ **Docker-First**: All operations work via docker/docker-compose
- ✅ **Tenant-Isolated**: Respects owner_id scoping throughout

## Embedding Spec Version

**Current Version:** `2026-01-06`

This version includes:
1. **Scene Text Embeddings** (OpenAI text-embedding-3-small, 1536d)
   - `embedding_transcript`: Pure ASR transcript
   - `embedding_visual`: Visual description + tags
   - `embedding_summary`: Optional summary (currently disabled)

2. **Scene CLIP Embeddings** (OpenAI ViT-B-32, 512d)
   - `embedding_visual_clip`: Visual embedding from scene thumbnail
   - Backend: local CPU or RunPod GPU (configurable)

3. **Scene Person Embeddings** (CLIP, 512d)
   - Thumbnail-based person detection embeddings
   - Stored in `scene_person_embeddings` table

4. **Person Reference Photo Embeddings** (CLIP, 512d)
   - Individual photo embeddings
   - Stored in `person_reference_photos.embedding`

5. **Person Query Embeddings** (CLIP, 512d)
   - Aggregated mean of all READY photo embeddings
   - Stored in `persons.query_embedding`

6. **OpenSearch Reindexing**
   - Reindex scenes for BM25 lexical search

## Usage Methods

### 1. Admin Panel (Recommended for Production)

The Admin panel has a "Reprocess Embeddings (All)" button that triggers reprocessing for all videos.

**Steps:**
1. Navigate to `/admin` in the frontend
2. Click "Reprocess Embeddings (All)" button
3. Confirm the operation
4. The job is queued and processed asynchronously
5. You'll see a success message with the spec version

**What it does:**
- Calls `/v1/admin/reprocess-embeddings` API endpoint
- Enqueues a background job to the `reprocessing` queue
- Processes all videos using the latest embedding spec
- Shows confirmation with spec version (e.g., "2026-01-06")

### 2. CLI (Recommended for Development/Testing)

The CLI provides fine-grained control over reprocessing scope.

#### Run via Docker (Production-like)

```bash
# Build services first
docker compose -f docker-compose.reprocess.yml build

# Start Redis and Worker
docker compose -f docker-compose.reprocess.yml up -d redis worker

# Reprocess a single video
docker compose -f docker-compose.reprocess.yml run --rm cli-reprocess \
  python -m src.scripts.reprocess_embeddings_cli \
  --scope video \
  --video-id <VIDEO_UUID>

# Reprocess all videos for an owner
docker compose -f docker-compose.reprocess.yml run --rm cli-reprocess \
  python -m src.scripts.reprocess_embeddings_cli \
  --scope owner \
  --owner-id <OWNER_UUID>

# Reprocess ALL videos (admin only)
docker compose -f docker-compose.reprocess.yml run --rm cli-reprocess \
  python -m src.scripts.reprocess_embeddings_cli \
  --scope all

# Force regeneration (overwrite existing embeddings)
docker compose -f docker-compose.reprocess.yml run --rm cli-reprocess \
  python -m src.scripts.reprocess_embeddings_cli \
  --scope all \
  --force

# Reprocess videos updated after a specific date
docker compose -f docker-compose.reprocess.yml run --rm cli-reprocess \
  python -m src.scripts.reprocess_embeddings_cli \
  --scope all \
  --since "2026-01-01T00:00:00"

# View help
docker compose -f docker-compose.reprocess.yml run --rm cli-reprocess \
  python -m src.scripts.reprocess_embeddings_cli --help
```

#### Run via Host Python (Development)

```bash
cd services/worker

# Ensure dependencies are installed
pip install -r requirements.txt

# Run reprocessing
python -m src.scripts.reprocess_embeddings_cli --scope video --video-id <UUID>
```

### 3. API Endpoint (Programmatic Access)

The API provides a REST endpoint for programmatic reprocessing.

**Endpoint:** `POST /v1/admin/reprocess-embeddings`

**Request Body:**
```json
{
  "scope": "all",           // "video", "owner", or "all"
  "video_id": "uuid",       // Required if scope="video"
  "owner_id": "uuid",       // Required if scope="owner"
  "force": false            // Force regeneration even if embeddings exist
}
```

**Response:**
```json
{
  "status": "queued",
  "spec_version": "2026-01-06",
  "scope": "all",
  "video_count": 42,
  "message": "Queued embedding reprocessing for 42 video(s) using spec version 2026-01-06"
}
```

**Example with curl:**
```bash
# Get admin token first
TOKEN="<your-admin-jwt-token>"

# Reprocess all videos
curl -X POST http://localhost:8000/v1/admin/reprocess-embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"scope": "all", "force": false}'

# Reprocess single video
curl -X POST http://localhost:8000/v1/admin/reprocess-embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"scope": "video", "video_id": "<VIDEO_UUID>", "force": false}'
```

## Docker Commands Reference

### Build

```bash
# Build worker service
docker compose build worker

# Build for reprocessing testing
docker compose -f docker-compose.reprocess.yml build
```

### Run Unit Tests

```bash
# Run worker unit tests
docker compose -f docker-compose.test.yml run --rm worker pytest

# Run API unit tests
docker compose -f docker-compose.test.yml run --rm api pytest
```

### Smoke Test (Single Video Reprocess)

```bash
# 1. Start services
docker compose -f docker-compose.reprocess.yml up -d redis worker

# 2. Find a video ID from your database
# (Replace <VIDEO_UUID> below with an actual video ID)

# 3. Run reprocessing for that video
docker compose -f docker-compose.reprocess.yml run --rm cli-reprocess \
  python -m src.scripts.reprocess_embeddings_cli \
  --scope video \
  --video-id <VIDEO_UUID>

# 4. Check logs to verify it used the latest spec
docker compose -f docker-compose.reprocess.yml logs worker

# Look for log lines like:
#   "Using embedding spec version: 2026-01-06"
#   "Started reprocessing"
#   "Reprocessing completed"
```

### Full Integration Test

```bash
# 1. Start all services (redis, worker, api)
docker compose -f docker-compose.reprocess.yml up -d

# 2. Wait for services to be ready
docker compose -f docker-compose.reprocess.yml ps

# 3. Test via API endpoint
curl -X POST http://localhost:8000/v1/admin/reprocess-embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -d '{"scope": "all", "force": false}'

# 4. Monitor worker logs
docker compose -f docker-compose.reprocess.yml logs -f worker

# 5. Cleanup
docker compose -f docker-compose.reprocess.yml down
```

## Architecture

### File Structure

```
services/worker/src/
├── domain/
│   └── reprocess/
│       ├── __init__.py
│       └── latest_reprocess.py          # ReprocessSpec, ReprocessRunner
├── scripts/
│   └── reprocess_embeddings_cli.py      # CLI entrypoint
└── adapters/
    └── database.py                      # Reprocessing DB methods

libs/tasks/
├── __init__.py
└── reprocess_embeddings.py              # Dramatiq actor

services/api/src/
├── routes/
│   └── admin.py                         # /admin/reprocess-embeddings endpoint
├── adapters/
│   ├── queue.py                         # enqueue_reprocess_embeddings()
│   └── database.py                      # get_videos_for_owner_reprocess()
└── domain/
    └── admin_schemas.py                 # Request/Response schemas

services/frontend/src/
└── app/admin/page.tsx                   # Admin panel button
```

### Key Components

1. **ReprocessSpec** (`latest_reprocess.py`)
   - Defines what "latest embedding methods" means
   - Single source of truth for embedding generation steps
   - Includes version constant and step definitions

2. **ReprocessRunner** (`latest_reprocess.py`)
   - Orchestrates the reprocessing pipeline
   - Handles scoping (video/owner/all)
   - Tracks progress and errors
   - Uses existing domain services (SidecarBuilder, PersonPhotoProcessor)

3. **Dramatiq Actor** (`reprocess_embeddings.py`)
   - Background job that executes reprocessing
   - Registered with the `reprocessing` queue
   - Called by both API and CLI

4. **Admin Endpoint** (`admin.py`)
   - REST API for triggering reprocessing
   - Admin-only access
   - Enqueues background job

5. **CLI Tool** (`reprocess_embeddings_cli.py`)
   - Direct execution for testing/maintenance
   - Supports all scopes and options
   - Runs synchronously and shows progress

## Updating the Embedding Pipeline

When you update embedding generation logic (e.g., new CLIP model, updated normalization):

### 1. Update the Spec Version

Edit `services/worker/src/domain/reprocess/latest_reprocess.py`:

```python
# Update this constant
LATEST_EMBEDDING_SPEC_VERSION = "2026-01-XX"  # New date
```

### 2. Update the Spec Steps (if needed)

If you're adding/removing/modifying embedding types, update `ReprocessSpec.get_latest_spec()`:

```python
@classmethod
def get_latest_spec(cls) -> "ReprocessSpec":
    return cls(
        version=LATEST_EMBEDDING_SPEC_VERSION,
        steps=[
            # Add new step
            EmbeddingStep(
                step_type=EmbeddingStepType.NEW_EMBEDDING_TYPE,
                enabled=True,
                description="Description of new embedding type",
                idempotent=True,
            ),
            # ... existing steps
        ]
    )
```

### 3. Implement the Step Handler

Add the handler method to `ReprocessRunner`:

```python
def _regenerate_new_embedding_type(
    self,
    video_id: UUID,
    request: ReprocessRequest,
    progress: ReprocessProgress,
) -> None:
    """Regenerate new embedding type"""
    # Implementation here
    pass
```

### 4. Wire it up

Add the step to `_execute_video_steps()`:

```python
elif step.step_type == EmbeddingStepType.NEW_EMBEDDING_TYPE:
    self._regenerate_new_embedding_type(video_id, request, progress)
```

### 5. Deploy and Run

```bash
# Build new docker images
docker compose build worker api

# Deploy to production
# ...

# Trigger reprocessing via Admin panel or CLI
docker compose -f docker-compose.reprocess.yml run --rm cli-reprocess \
  python -m src.scripts.reprocess_embeddings_cli --scope all
```

## Troubleshooting

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'src.domain.reprocess'`

**Solution:** The reprocess module is in the worker service. Make sure you're running from the worker context:

```bash
# Correct
docker compose run worker python -m src.scripts.reprocess_embeddings_cli --scope all

# Incorrect
docker compose run api python -m src.scripts.reprocess_embeddings_cli --scope all
```

### Lazy Import Warning in API

**Problem:** `ImportError` when importing `LATEST_EMBEDDING_SPEC_VERSION` in API routes

**Solution:** This is intentional! The import is inside the endpoint function to avoid import-time dependencies:

```python
@router.post("/reprocess-embeddings")
async def reprocess_embeddings(...):
    # Import inside function (lazy import)
    from src.domain.reprocess import LATEST_EMBEDDING_SPEC_VERSION
    ...
```

### Job Not Processing

**Problem:** Reprocessing job is queued but not executing

**Solution:** Ensure worker is running and connected to Redis:

```bash
# Check worker status
docker compose ps worker

# Check worker logs
docker compose logs worker

# Verify Redis connection
docker compose exec redis redis-cli ping
```

### Database Methods Missing

**Problem:** `AttributeError: 'Database' object has no attribute 'get_videos_for_reprocess'`

**Solution:** Make sure you're using the updated database adapters. The methods were added in this implementation:
- Worker: `services/worker/src/adapters/database.py`
- API: `services/api/src/adapters/database.py`

## FAQ

**Q: Is reprocessing safe to run on production?**

A: Yes! The reprocessing is idempotent and uses upsert operations. It won't duplicate data or corrupt existing records. However, it will generate OpenAI API calls, so be mindful of costs.

**Q: Can I run reprocessing while videos are being uploaded?**

A: Yes, but videos currently in PROCESSING status will be skipped to avoid conflicts.

**Q: What happens if reprocessing fails midway?**

A: The pipeline tracks progress per video. If a video fails, it's logged and the pipeline continues with the next video. You can re-run reprocessing to retry failed videos.

**Q: Do I need to use `--force` to update embeddings?**

A: No! By default, the pipeline checks if embeddings exist and regenerates them anyway (it's idempotent). Use `--force` only if you want to ensure regeneration regardless of any cached state.

**Q: How do I know which spec version is currently deployed?**

A: Check the admin panel - when you trigger reprocessing, it shows the spec version. You can also check the source code in `latest_reprocess.py`.

**Q: Can I reprocess just one owner's videos?**

A: Yes! Use `--scope owner --owner-id <UUID>` in the CLI or pass `{"scope": "owner", "owner_id": "<UUID>"}` to the API.

## Monitoring

### Logs to Watch

The reprocessing pipeline emits structured logs:

```
2026-01-06 12:00:00 - INFO - Starting reprocessing (spec_version=2026-01-06, scope=all)
2026-01-06 12:00:01 - INFO - Found 42 total videos
2026-01-06 12:00:02 - INFO - Processing video <uuid>
2026-01-06 12:00:10 - INFO - Reprocessing completed (videos_processed=42, errors=0)
```

### Metrics to Track

- `videos_processed`: Number of videos successfully reprocessed
- `videos_failed`: Number of videos that failed
- `scenes_processed`: Number of scenes updated
- `person_photos_processed`: Number of person photos updated
- `error_count`: Total errors encountered

## Support

For issues or questions:
1. Check the logs: `docker compose logs worker`
2. Review this guide
3. Consult the source code in `services/worker/src/domain/reprocess/`
4. Contact the development team

---

**Last Updated:** 2026-01-06
**Spec Version:** 2026-01-06
