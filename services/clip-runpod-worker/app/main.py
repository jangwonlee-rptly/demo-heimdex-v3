"""
FastAPI application for CLIP embedding service.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import torch
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app import __version__
from app.download import download_image, download_images_batch, DownloadError
from app.model import get_clip_model, load_model_global
from app.schemas import (
    BatchEmbedImageItemError,
    BatchEmbedImageItemResult,
    BatchEmbedImageRequest,
    BatchEmbedImageResponse,
    BatchTimings,
    EmbedImageRequest,
    EmbedImageResponse,
    EmbedTextRequest,
    EmbedTextResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    Timings,
)
from app.security import AuthError, create_canonical_message, validate_auth
from app.settings import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Track service start time for uptime
SERVICE_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Loads CLIP model on startup and performs cleanup on shutdown.
    """
    logger.info("=" * 60)
    logger.info(f"Starting {settings.service_name} v{__version__}")
    logger.info("=" * 60)

    # Load model at startup
    try:
        load_model_global()
        logger.info("Application startup complete")
    except Exception as e:
        logger.exception(f"FATAL: Failed to load model during startup: {e}")
        raise

    yield

    # Cleanup on shutdown
    logger.info("Application shutting down")


app = FastAPI(
    title="CLIP RunPod Worker",
    description="Production-grade CLIP embedding service for image and text",
    version=__version__,
    lifespan=lifespan,
)


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    """Handle authentication errors."""
    logger.warning(f"Authentication failed: {exc}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorResponse(
            error=ErrorDetail(
                code="AUTH_FAILED",
                message=str(exc),
            )
        ).model_dump(),
    )


@app.exception_handler(DownloadError)
async def download_error_handler(request: Request, exc: DownloadError):
    """Handle download errors."""
    logger.warning(f"Download failed: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error=ErrorDetail(
                code="DOWNLOAD_ERROR",
                message=str(exc),
            )
        ).model_dump(),
    )


# ============================================================================
# Health Check
# ============================================================================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns model status and system information.
    """
    model = get_clip_model()
    metadata = model.get_metadata()

    return HealthResponse(
        status="ok",
        model_name=metadata["model_name"],
        pretrained=metadata["pretrained"],
        device=metadata["device"],
        torch_version=torch.__version__,
        cuda_version=torch.version.cuda if torch.cuda.is_available() else None,
        uptime_seconds=time.time() - SERVICE_START_TIME,
    )


# ============================================================================
# Single Image Embedding
# ============================================================================


@app.post("/v1/embed/image", response_model=EmbedImageResponse)
async def embed_image(request: EmbedImageRequest):
    """
    Generate CLIP embedding for a single image.

    Authenticates request, downloads image, and returns 512-dimensional embedding.
    """
    request_id = request.request_id or f"img-{uuid.uuid4().hex[:8]}"
    total_start = time.time()

    logger.info(f"Processing image embedding request: request_id={request_id}")

    # Validate authentication
    try:
        canonical = create_canonical_message(
            "POST", "/v1/embed/image", image_url=str(request.image_url)
        )
        validate_auth(canonical, request.auth, request_id)
    except AuthError as e:
        raise e

    # Download image
    download_start = time.time()
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            image = await download_image(session, str(request.image_url), request_id)
        download_ms = (time.time() - download_start) * 1000
    except DownloadError as e:
        raise e

    # Generate embedding
    inference_start = time.time()
    try:
        model = get_clip_model()
        embedding = model.encode_image(image, normalize=request.normalize)
        inference_ms = (time.time() - inference_start) * 1000
    except RuntimeError as e:
        logger.error(f"Inference failed for request_id={request_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorDetail(
                code="INFERENCE_ERROR",
                message=str(e),
                request_id=request_id,
            ).model_dump(),
        )

    total_ms = (time.time() - total_start) * 1000

    logger.info(
        f"Image embedding completed: request_id={request_id}, "
        f"total_ms={total_ms:.1f}, download_ms={download_ms:.1f}, inference_ms={inference_ms:.1f}"
    )

    metadata = model.get_metadata()

    return EmbedImageResponse(
        request_id=request_id,
        embedding=embedding,
        dim=len(embedding),
        model_name=metadata["model_name"],
        pretrained=metadata["pretrained"],
        device=metadata["device"],
        normalized=request.normalize,
        timings=Timings(
            download_ms=download_ms,
            inference_ms=inference_ms,
            total_ms=total_ms,
        ),
    )


# ============================================================================
# Batch Image Embedding
# ============================================================================


@app.post("/v1/embed/image-batch", response_model=BatchEmbedImageResponse)
async def embed_image_batch(request: BatchEmbedImageRequest):
    """
    Generate CLIP embeddings for a batch of images.

    Downloads images concurrently, then processes batch on GPU in single forward pass.
    Returns per-item results with errors for failed items.
    """
    total_start = time.time()
    batch_size = len(request.items)

    logger.info(f"Processing batch image embedding request: batch_size={batch_size}")

    # Validate batch size
    if batch_size > settings.max_batch_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetail(
                code="BATCH_TOO_LARGE",
                message=f"Batch size {batch_size} exceeds maximum {settings.max_batch_size}",
            ).model_dump(),
        )

    # Validate authentication for all items
    for item in request.items:
        try:
            canonical = create_canonical_message(
                "POST", "/v1/embed/image-batch", image_url=str(item.image_url)
            )
            validate_auth(canonical, item.auth, item.request_id)
        except AuthError as e:
            # Return early error for auth failures
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorDetail(
                    code="AUTH_FAILED",
                    message=f"Authentication failed for request_id={item.request_id}: {e}",
                    request_id=item.request_id,
                ).model_dump(),
            )

    # Phase 1: Download all images concurrently
    download_start = time.time()
    image_urls = [str(item.image_url) for item in request.items]
    request_ids = [item.request_id for item in request.items]

    download_results = await download_images_batch(image_urls, request_ids)
    download_ms = (time.time() - download_start) * 1000

    # Separate successful downloads from failures
    successful_images = []
    successful_indices = []
    successful_request_ids = []
    failed_results = {}

    for idx, (image, error) in enumerate(download_results):
        if image is not None:
            successful_images.append(image)
            successful_indices.append(idx)
            successful_request_ids.append(request_ids[idx])
        else:
            failed_results[idx] = error

    logger.info(
        f"Batch download completed: successful={len(successful_images)}, "
        f"failed={len(failed_results)}, download_ms={download_ms:.1f}"
    )

    # Phase 2: Batch inference on GPU
    inference_ms = 0.0
    if successful_images:
        inference_start = time.time()
        try:
            model = get_clip_model()
            # Single batched forward pass
            embeddings = model.encode_images_batch(
                successful_images, normalize=request.items[0].normalize
            )
            inference_ms = (time.time() - inference_start) * 1000

            logger.info(
                f"Batch inference completed: batch_size={len(successful_images)}, "
                f"inference_ms={inference_ms:.1f}"
            )
        except RuntimeError as e:
            logger.error(f"Batch inference failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ErrorDetail(
                    code="INFERENCE_ERROR",
                    message=str(e),
                ).model_dump(),
            )
    else:
        embeddings = []

    # Build results
    results = []
    metadata = get_clip_model().get_metadata()

    # Add successful results
    for idx, embedding_idx in enumerate(successful_indices):
        original_idx = embedding_idx
        embedding = embeddings[idx]

        results.append(
            BatchEmbedImageItemResult(
                request_id=request_ids[original_idx],
                embedding=embedding,
                dim=len(embedding),
                normalized=request.items[original_idx].normalize,
                timings=Timings(
                    download_ms=download_ms / batch_size,  # Amortized
                    inference_ms=inference_ms / len(successful_images) if successful_images else 0,
                    total_ms=(download_ms + inference_ms) / batch_size,
                ),
            )
        )

    # Add failed results (maintain order)
    for failed_idx in sorted(failed_results.keys()):
        error_msg = failed_results[failed_idx]
        results.insert(
            failed_idx,
            BatchEmbedImageItemError(
                request_id=request_ids[failed_idx],
                error=ErrorDetail(
                    code="DOWNLOAD_ERROR",
                    message=error_msg,
                    request_id=request_ids[failed_idx],
                ),
            ),
        )

    total_ms = (time.time() - total_start) * 1000

    logger.info(
        f"Batch request completed: batch_size={batch_size}, "
        f"successful={len(successful_images)}, failed={len(failed_results)}, "
        f"total_ms={total_ms:.1f}"
    )

    return BatchEmbedImageResponse(
        results=results,
        model_name=metadata["model_name"],
        pretrained=metadata["pretrained"],
        device=metadata["device"],
        batch_timings=BatchTimings(
            total_download_ms=download_ms,
            total_inference_ms=inference_ms,
            total_ms=total_ms,
        ),
    )


# ============================================================================
# Text Embedding
# ============================================================================


@app.post("/v1/embed/text", response_model=EmbedTextResponse)
async def embed_text(request: EmbedTextRequest):
    """
    Generate CLIP embedding for text.

    Returns 512-dimensional embedding from CLIP text encoder.
    """
    request_id = request.request_id or f"txt-{uuid.uuid4().hex[:8]}"
    total_start = time.time()

    logger.info(f"Processing text embedding request: request_id={request_id}")

    # Validate authentication
    try:
        canonical = create_canonical_message("POST", "/v1/embed/text", text=request.text)
        validate_auth(canonical, request.auth, request_id)
    except AuthError as e:
        raise e

    # Generate embedding
    inference_start = time.time()
    try:
        model = get_clip_model()
        embedding = model.encode_text(request.text, normalize=request.normalize)
        inference_ms = (time.time() - inference_start) * 1000
    except RuntimeError as e:
        logger.error(f"Text inference failed for request_id={request_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorDetail(
                code="INFERENCE_ERROR",
                message=str(e),
                request_id=request_id,
            ).model_dump(),
        )

    total_ms = (time.time() - total_start) * 1000

    logger.info(
        f"Text embedding completed: request_id={request_id}, "
        f"total_ms={total_ms:.1f}, inference_ms={inference_ms:.1f}"
    )

    metadata = model.get_metadata()

    return EmbedTextResponse(
        request_id=request_id,
        embedding=embedding,
        dim=len(embedding),
        model_name=metadata["model_name"],
        pretrained=metadata["pretrained"],
        device=metadata["device"],
        normalized=request.normalize,
        timings=Timings(
            download_ms=None,
            inference_ms=inference_ms,
            total_ms=total_ms,
        ),
    )


# ============================================================================
# Root
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.service_name,
        "version": __version__,
        "status": "ok",
        "endpoints": {
            "health": "/health",
            "embed_image": "/v1/embed/image",
            "embed_image_batch": "/v1/embed/image-batch",
            "embed_text": "/v1/embed/text",
        },
    }
