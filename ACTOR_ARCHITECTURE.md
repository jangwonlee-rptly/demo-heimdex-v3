# Dramatiq Actor Architecture

## Overview

This document describes the refactored Dramatiq actor architecture that eliminates the "actor already registered" error and follows best practices for a microservices monorepo.

## Architecture

### Shared Actor Definition

All Dramatiq actors are defined in a shared module at the project root:

```
libs/
└── tasks/
    ├── __init__.py
    └── video_processing.py  # Canonical process_video actor
```

**Key Principles:**
1. **Single Source of Truth**: Each actor is defined exactly once in `libs/tasks/`
2. **Both Services Import**: Both API and Worker services import the same actor
3. **No Dummy Actors**: No local actor stubs or dummy definitions
4. **No Manual Message Construction**: No manual `Message(...)` instantiation
5. **Lazy Implementation Loading**: Business logic is imported only when executed (in worker)

### Service Architecture

```
project-root/
├── libs/tasks/                    # Shared actor definitions
│   ├── __init__.py
│   └── video_processing.py        # process_video actor
│
├── services/
│   ├── api/                       # FastAPI web service
│   │   └── src/adapters/
│   │       └── queue.py           # Imports actor, calls .send()
│   │
│   └── worker/                    # Dramatiq worker service
│       └── src/
│           ├── tasks.py           # Imports actor, registers with Dramatiq
│           └── domain/
│               └── video_processor.py  # Business logic
```

## How It Works

### Shared Actor (`libs/tasks/video_processing.py`)

```python
@dramatiq.actor(
    queue_name="video_processing",
    max_retries=3,
    # ... other options
)
def process_video(video_id: str):
    """
    Canonical actor definition used by both services.

    - API: Only calls .send() - function body never executes
    - Worker: Executes the function - imports domain logic lazily
    """
    # Lazy import avoids requiring worker dependencies in API
    from services.worker.src.domain.video_processor import video_processor

    video_processor.process_video(UUID(video_id))
```

**Key Design:**
- The actor is defined **once** at module level
- Implementation uses **lazy imports** to avoid circular dependencies
- API service can import without needing worker dependencies
- Worker service executes with full access to domain logic

### API Service (`services/api/src/adapters/queue.py`)

```python
from libs.tasks import process_video

class TaskQueue:
    def enqueue_video_processing(self, video_id: UUID):
        # Simply call .send() on the shared actor
        process_video.send(str(video_id))
```

**What Happens:**
1. API imports the actor at startup (module load time)
2. When enqueueing, calls `process_video.send(video_id)`
3. The function body **never executes** in API context
4. Message is sent to Redis queue

### Worker Service (`services/worker/src/tasks.py`)

```python
# Initialize broker
redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)

# Import the shared actor - this registers it with the broker
from libs.tasks import process_video
```

**What Happens:**
1. Worker initializes Redis broker
2. Worker imports the actor (registers with broker)
3. Dramatiq workers process jobs from the queue
4. When a job runs, the function body **executes**:
   - Lazy import loads `video_processor`
   - Business logic runs
   - Job completes or retries on failure

## Benefits

### ✓ No "Actor Already Registered" Error

**Previous Problem:**
```python
# BAD: Registering actor inside function (called multiple times)
def enqueue_video_processing(video_id):
    process_video = dramatiq.actor(...)  # ← Error on second call!
    process_video.send(video_id)
```

**Solution:**
```python
# GOOD: Import once at module level
from libs.tasks import process_video

def enqueue_video_processing(video_id):
    process_video.send(video_id)  # ← No re-registration
```

### ✓ No Circular Imports

**Dependency Flow:**
```
libs/tasks/          (shared actors, no external deps)
    ↑
    ├── services/api/        (depends on libs/tasks)
    └── services/worker/     (depends on libs/tasks)
            ↓
        domain/              (business logic, no deps on actors)
```

**Why It Works:**
- `libs/tasks` defines actors with lazy implementation loading
- `services/api` imports actors for sending only
- `services/worker` imports actors for execution
- Domain logic is loaded lazily (only when worker executes jobs)

### ✓ Clean Separation of Concerns

| Component | Responsibility |
|-----------|---------------|
| `libs/tasks/` | Actor definitions (interface + routing) |
| `services/api/` | HTTP API + job enqueueing |
| `services/worker/` | Job execution + orchestration |
| `services/worker/src/domain/` | Business logic |

### ✓ Idiomatic Dramatiq Usage

- Uses `@dramatiq.actor` decorator (not manual `Message` construction)
- Uses `.send()` method (not `broker.enqueue()`)
- Follows Dramatiq's intended patterns
- Configuration lives with actor definition

## Testing

To test the architecture (requires Dramatiq installed):

```bash
python scripts/test_actor_import.py
```

This verifies:
- Shared actor can be imported
- Actor has correct configuration
- API can import and use the actor
- Worker can import and register the actor

## Deployment

Both services need access to the shared `libs/` module:

### Docker / Docker Compose

The `docker-compose.yml` uses the **project root** as the build context:

```yaml
# docker-compose.yml
services:
  api:
    build:
      context: .  # Project root
      dockerfile: ./services/api/Dockerfile

  worker:
    build:
      context: .  # Project root
      dockerfile: ./services/worker/Dockerfile
```

**Why project root?** Because `libs/` is at the project root, and Docker can only access files within the build context.

Each Dockerfile then copies the necessary files:

```dockerfile
# services/api/Dockerfile
WORKDIR /app

# Copy shared libraries first
COPY libs/ ./libs/

# Copy service-specific code
COPY services/api/src/ ./src/

# Set Python path so libs/ is importable
ENV PYTHONPATH=/app
```

The same pattern applies to the Worker Dockerfile.

**Result:** Both containers have this structure:
```
/app/
├── libs/
│   └── tasks/
│       └── video_processing.py
└── src/
    └── (service code)
```

With `PYTHONPATH=/app`, importing `from libs.tasks import process_video` works automatically.

### Railway / Production

For Railway deployment, ensure the build context is set to the repository root:

**Option 1: Railway.json**
```json
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "services/api/Dockerfile"
  }
}
```

**Option 2: Railway Dashboard**
- Settings → Build → Root Directory: `/` (root)
- Dockerfile Path: `services/api/Dockerfile` (or `services/worker/Dockerfile`)

This ensures Railway builds from the root, giving the Dockerfile access to `libs/`.

### Local Development (without Docker)

For local development without Docker, you need to add the project root to `PYTHONPATH`:

```bash
# From project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use a .env file
echo "PYTHONPATH=$(pwd)" >> .env
```

Alternatively, install the project in editable mode:

```bash
# From project root
pip install -e .
```

## Migration Summary

### What Changed

1. **Created** `libs/tasks/video_processing.py` with canonical actor
2. **Updated** `services/worker/src/tasks.py` to import shared actor
3. **Updated** `services/api/src/adapters/queue.py` to import shared actor
4. **Removed** dummy actor definitions
5. **Removed** manual `Message` construction

### What Stayed The Same

- Queue name: `video_processing`
- Actor name: `process_video`
- Message format: `(video_id: str,)`
- Broker: Redis
- Business logic: `VideoProcessor.process_video()`

## Troubleshooting

### Error: "No module named 'libs'"

**Cause:** `sys.path` not configured correctly

**Fix:** Verify project root is added to `sys.path` in both services

### Error: "Actor already registered"

**Cause:** Actor being registered multiple times (shouldn't happen with this architecture)

**Fix:** Verify `from libs.tasks import process_video` is at module level, not inside functions

### Error: "Worker dependencies not available"

**Cause:** API trying to execute actor body (shouldn't happen)

**Fix:** Verify API only calls `.send()`, never calls actor directly like `process_video(video_id)`

## Summary

This refactored architecture:
- ✓ Defines each actor exactly once in a shared module
- ✓ Both services import the same actor definition
- ✓ No dummy actors or manual Message construction
- ✓ No circular imports (via lazy loading)
- ✓ Follows Dramatiq best practices
- ✓ Clean, maintainable, and scalable

The "actor already registered" error is **impossible** with this architecture because the actor is defined once at module load time and imported by both services, never re-registered.
