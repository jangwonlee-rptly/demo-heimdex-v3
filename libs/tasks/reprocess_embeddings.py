"""
Reprocess embeddings Dramatiq actor.

This actor executes the latest embedding reprocessing pipeline.
All reprocessing operations (admin button, CLI, etc.) should enqueue this actor.
"""

import dramatiq
from typing import Optional
from uuid import UUID


@dramatiq.actor(
    queue_name="reprocessing",
    max_retries=3,
    min_backoff=30000,  # 30 seconds
    max_backoff=600000,  # 10 minutes
    time_limit=7200000,  # 2 hour timeout for large reprocessing jobs
)
def reprocess_embeddings(
    scope: str,
    video_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    force: bool = False,
    since: Optional[str] = None,  # ISO format datetime string
) -> dict:
    """
    Reprocess embeddings using the latest embedding methods.

    This is the single entry point for all reprocessing operations.
    It guarantees that the latest embedding pipeline is used.

    Args:
        scope: "video", "owner", or "all"
        video_id: Optional video UUID (required for scope="video")
        owner_id: Optional owner UUID (required for scope="owner")
        force: Force regeneration even if embeddings exist
        since: Optional ISO datetime string (only reprocess videos updated after this)

    Returns:
        dict with reprocessing results
    """
    # Lazy import to avoid import-time side effects
    from src.tasks import get_worker_context
    from src.domain.reprocess import (
        ReprocessRunner,
        ReprocessRequest,
        ReprocessScope,
        LATEST_EMBEDDING_SPEC_VERSION,
    )
    from datetime import datetime

    # Get worker context (DI container)
    ctx = get_worker_context()

    # Create reprocess runner with injected dependencies
    runner = ReprocessRunner(
        db=ctx.db,
        storage=ctx.storage,
        opensearch=ctx.opensearch,
        openai=ctx.openai,
        clip_embedder=ctx.clip_embedder,
        settings=ctx.settings,
    )

    # Parse parameters
    reprocess_scope = ReprocessScope(scope)
    video_uuid = UUID(video_id) if video_id else None
    owner_uuid = UUID(owner_id) if owner_id else None
    since_dt = datetime.fromisoformat(since) if since else None

    # Create request
    request = ReprocessRequest(
        scope=reprocess_scope,
        video_id=video_uuid,
        owner_id=owner_uuid,
        force=force,
        since=since_dt,
        spec_version=LATEST_EMBEDDING_SPEC_VERSION,
    )

    # Execute reprocessing
    progress = runner.run_reprocess(request)

    # Return results
    return progress.to_dict()
