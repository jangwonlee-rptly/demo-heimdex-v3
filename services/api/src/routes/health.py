"""Health check endpoint."""
from datetime import datetime
from fastapi import APIRouter

from ..domain.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.

    Returns:
        HealthResponse: The current service status and timestamp.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
    )
