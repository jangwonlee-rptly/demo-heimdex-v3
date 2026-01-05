"""Dramatiq task for reference photo processing."""
import logging
from uuid import UUID

import dramatiq

logger = logging.getLogger(__name__)


@dramatiq.actor(
    queue_name="reference_photo_processing",
    max_retries=1,
    min_backoff=15000,
    max_backoff=60000,
    time_limit=300000,  # 5 minutes
)
def process_reference_photo(photo_id: str) -> None:
    """
    Process a person reference photo: download, embed, aggregate.

    This task:
    1. Fetches photo record from database
    2. Updates state to PROCESSING
    3. Downloads photo from storage
    4. Generates CLIP embedding (512d)
    5. Normalizes embedding
    6. Computes quality score
    7. Updates photo record with embedding (state=READY)
    8. Aggregates all READY photos to update persons.query_embedding

    Idempotency:
    - If photo is already READY, exits early
    - If photo is PROCESSING, proceeds (simple rule for v1)

    Args:
        photo_id: UUID of the photo to process (as string)

    Raises:
        Exception: Any processing error (logged and saved to photo record)
    """
    # Lazy import to avoid import-time side effects
    from services.worker.src.tasks import get_worker_context
    from services.worker.src.domain.person_photo_processor import PersonPhotoProcessor

    ctx = get_worker_context()
    db = ctx.db
    storage = ctx.storage
    clip_embedder = ctx.clip_embedder

    logger.info(f"Starting reference photo processing for photo_id={photo_id}")

    photo_uuid = UUID(photo_id)

    # Create processor
    processor = PersonPhotoProcessor(
        db=db,
        storage=storage,
        clip_embedder=clip_embedder,
    )

    # Process photo (raises on error)
    processor.process_photo(photo_uuid)

    logger.info(f"Completed reference photo processing for photo_id={photo_id}")
