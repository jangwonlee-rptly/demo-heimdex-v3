"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .context import create_app_context, cleanup_app_context
from .routes import health, profile, videos, search, exports, admin, preferences, highlights
from .exceptions import HeimdexException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events.

    This is the composition root for the API service. All dependencies are
    created here and attached to app.state for use throughout the application.

    Args:
        app: The FastAPI application instance.

    Yields:
        None: Control is yielded back to the application.
    """
    # Startup: Create settings and application context
    logger.info("Starting Heimdex API service")

    # Load settings from environment
    settings = Settings()
    logger.info(f"CORS origins: {settings.cors_origins_list}")

    # Create application context with all dependencies
    # This is where all adapters are instantiated (composition root)
    logger.info("Initializing application context...")
    ctx = create_app_context(settings)

    # Attach context to app state for access via dependencies
    app.state.ctx = ctx
    logger.info("Application context initialized successfully")

    yield

    # Shutdown: Clean up resources
    logger.info("Shutting down Heimdex API service")
    cleanup_app_context(ctx)
    logger.info("Application context cleaned up")


# Create FastAPI application
app = FastAPI(
    title="Heimdex API",
    description="Vector-native video archive API",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS with permissive defaults
# Settings are loaded in lifespan, so we can't use them here
# In production, configure CORS via environment variables and restart
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Override via Settings in lifespan if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(HeimdexException)
async def heimdex_exception_handler(request: Request, exc: HeimdexException):
    """
    Handle all Heimdex custom exceptions.

    Returns a structured JSON response with error details.

    Args:
        request: The FastAPI request object
        exc: The HeimdexException that was raised

    Returns:
        JSONResponse with error details and appropriate status code
    """
    logger.error(
        f"HeimdexException: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


# Include routers with API versioning
# Health checks don't need versioning (for K8s probes)
app.include_router(health.router, tags=["Health"])

# V1 API routes
app.include_router(profile.router, prefix="/v1", tags=["v1", "Profile"])
app.include_router(videos.router, prefix="/v1", tags=["v1", "Videos"])
app.include_router(search.router, prefix="/v1", tags=["v1", "Search"])
app.include_router(exports.router, prefix="/v1", tags=["v1", "Exports"])
app.include_router(preferences.router, prefix="/v1", tags=["v1", "Preferences"])
app.include_router(highlights.router, prefix="/v1", tags=["v1", "Highlights"])
app.include_router(admin.router, tags=["v1", "Admin"])


@app.get("/")
async def root():
    """Root endpoint.

    Returns:
        dict: Service information including name, version, and status.
    """
    return {
        "service": "Heimdex API",
        "version": "0.1.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    # Create settings for CLI usage only
    _settings = Settings()
    uvicorn.run(
        "main:app",
        host=_settings.api_host,
        port=_settings.api_port,
        reload=True,
    )
