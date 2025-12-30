"""Worker context and dependency container.

This module defines the WorkerContext dataclass that holds all service dependencies
for the background worker. The context is created once at worker startup and passed
to task handlers via explicit injection.

This is the composition root for the Worker service - all dependencies are wired here.
"""
from dataclasses import dataclass
from typing import Optional

from .config import Settings


@dataclass
class WorkerContext:
    """Worker context holding all service dependencies.

    This is created once at worker startup and provides access to all adapters.
    Tasks should receive this context as a parameter, not import global singletons.

    Attributes:
        settings: Application settings from environment
        db: Database adapter for Supabase/PostgREST operations
        storage: Supabase storage adapter for file operations
        opensearch: OpenSearch client for indexing (optional)
        openai: OpenAI client for embeddings and AI operations
        clip_embedder: CLIP embedder for visual embeddings (optional)
        ffmpeg: FFmpeg adapter for video processing
    """

    settings: Settings
    db: 'Database'  # Forward reference to avoid circular import
    storage: 'SupabaseStorage'
    opensearch: Optional['OpenSearchClient']
    openai: 'OpenAIClient'
    clip_embedder: Optional['ClipEmbedder']
    ffmpeg: 'FFmpegAdapter'


def create_worker_context(settings: Settings) -> WorkerContext:
    """Create and initialize worker context with all dependencies.

    This is the composition root for the worker - all adapter creation happens here.
    No I/O or heavy initialization happens during import; it's all deferred
    to this function which is called at worker startup.

    Args:
        settings: Application settings

    Returns:
        WorkerContext with all initialized dependencies
    """
    # Import adapters here to avoid import-time side effects
    from .adapters.database import Database
    from .adapters.supabase import SupabaseStorage
    from .adapters.opensearch_client import OpenSearchClient
    from .adapters.openai_client import OpenAIClient
    from .adapters.clip_embedder import ClipEmbedder
    from .adapters.ffmpeg import FFmpegAdapter

    # Create database adapter
    db = Database(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
    )

    # Create storage adapter
    storage = SupabaseStorage(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
    )

    # Create OpenSearch client (optional)
    # Note: Worker's OpenSearchClient uses legacy pattern with no-arg constructor
    # TODO: Refactor to accept constructor parameters like API service
    opensearch: Optional[OpenSearchClient] = None
    if settings.opensearch_url:
        opensearch = OpenSearchClient()

    # Create OpenAI client
    # Note: Worker's OpenAIClient uses legacy pattern with no-arg constructor
    # TODO: Refactor to accept api_key parameter like API service
    openai = OpenAIClient()

    # Create CLIP embedder (optional, lazy-loads model on first use)
    clip_embedder: Optional[ClipEmbedder] = None
    if settings.clip_enabled:
        clip_embedder = ClipEmbedder()

    # Create FFmpeg adapter (stateless)
    ffmpeg = FFmpegAdapter()

    return WorkerContext(
        settings=settings,
        db=db,
        storage=storage,
        opensearch=opensearch,
        openai=openai,
        clip_embedder=clip_embedder,
        ffmpeg=ffmpeg,
    )
