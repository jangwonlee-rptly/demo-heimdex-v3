"""Health check endpoints."""
import logging
import time
from datetime import datetime
from fastapi import APIRouter, status, Depends
from fastapi.responses import JSONResponse

from ..domain.schemas import HealthResponse, DetailedHealthResponse, DependencyHealth
from ..dependencies import get_db, get_queue, get_storage
from ..adapters.database import Database
from ..adapters.queue import TaskQueue
from ..adapters.supabase import SupabaseStorage

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint (liveness probe).

    Returns 200 if the service is running, regardless of dependency status.
    Use this for Kubernetes liveness probes.

    Returns:
        HealthResponse: The current service status and timestamp.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
    )


@router.get("/health/ready", response_model=DetailedHealthResponse)
async def readiness_check(
    db: Database = Depends(get_db),
    task_queue: TaskQueue = Depends(get_queue),
    storage: SupabaseStorage = Depends(get_storage),
):
    """
    Detailed readiness check with dependency validation.

    Checks the health of all critical dependencies:
    - Database (Supabase/PostgreSQL)
    - Redis (message queue)
    - Storage (Supabase Storage)

    Returns 200 if all dependencies are healthy.
    Returns 503 if any critical dependency is unhealthy.
    Use this for Kubernetes readiness probes.

    Returns:
        DetailedHealthResponse: Detailed health status of all dependencies.
    """
    dependencies = {}
    overall_healthy = True

    # Check Database
    db_start = time.time()
    try:
        # Simple query to verify database connectivity
        db.client.table("videos").select("id").limit(1).execute()
        db_latency = int((time.time() - db_start) * 1000)
        dependencies["database"] = DependencyHealth(
            status="healthy",
            latency_ms=db_latency,
        )
        logger.debug(f"Database health check passed ({db_latency}ms)")
    except Exception as e:
        db_latency = int((time.time() - db_start) * 1000)
        dependencies["database"] = DependencyHealth(
            status="unhealthy",
            latency_ms=db_latency,
            error=str(e)[:200],  # Truncate long errors
        )
        overall_healthy = False
        logger.error(f"Database health check failed: {e}")

    # Check Redis (Message Queue)
    redis_start = time.time()
    try:
        # Ping Redis to verify connectivity
        task_queue.broker.client.ping()
        redis_latency = int((time.time() - redis_start) * 1000)
        dependencies["redis"] = DependencyHealth(
            status="healthy",
            latency_ms=redis_latency,
        )
        logger.debug(f"Redis health check passed ({redis_latency}ms)")
    except Exception as e:
        redis_latency = int((time.time() - redis_start) * 1000)
        dependencies["redis"] = DependencyHealth(
            status="unhealthy",
            latency_ms=redis_latency,
            error=str(e)[:200],
        )
        overall_healthy = False
        logger.error(f"Redis health check failed: {e}")

    # Check Storage (Supabase Storage)
    storage_start = time.time()
    try:
        # List buckets to verify storage connectivity
        # This is a lightweight operation
        storage.client.storage.list_buckets()
        storage_latency = int((time.time() - storage_start) * 1000)
        dependencies["storage"] = DependencyHealth(
            status="healthy",
            latency_ms=storage_latency,
        )
        logger.debug(f"Storage health check passed ({storage_latency}ms)")
    except Exception as e:
        storage_latency = int((time.time() - storage_start) * 1000)
        dependencies["storage"] = DependencyHealth(
            status="unhealthy",
            latency_ms=storage_latency,
            error=str(e)[:200],
        )
        overall_healthy = False
        logger.error(f"Storage health check failed: {e}")

    # Build response
    response = DetailedHealthResponse(
        status="healthy" if overall_healthy else "unhealthy",
        timestamp=datetime.utcnow(),
        dependencies=dependencies,
    )

    # Return 503 if any dependency is unhealthy
    if not overall_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(mode='json'),
        )

    return response
