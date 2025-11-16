"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import health, profile, videos, search

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Heimdex API service")
    logger.info(f"CORS origins: {settings.cors_origins_list}")
    yield
    # Shutdown
    logger.info("Shutting down Heimdex API service")


# Create FastAPI application
app = FastAPI(
    title="Heimdex API",
    description="Vector-native video archive API",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(profile.router, tags=["Profile"])
app.include_router(videos.router, tags=["Videos"])
app.include_router(search.router, tags=["Search"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Heimdex API",
        "version": "0.1.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
