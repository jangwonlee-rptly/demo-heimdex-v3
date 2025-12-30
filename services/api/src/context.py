"""Application context and dependency container for API service.

This module defines the AppContext dataclass that holds all service dependencies.
The context is created once at application startup and attached to app.state.

This is the composition root for the API service - all dependencies are wired here.
"""
from dataclasses import dataclass
from typing import Optional

from .adapters.database import Database
from .adapters.supabase import SupabaseStorage
from .adapters.queue import TaskQueue
from .adapters.openai_client import OpenAIClient
from .adapters.opensearch_client import OpenSearchClient
from .adapters.clip_client import ClipClient
from .config import Settings


@dataclass
class AppContext:
    """Application context holding all service dependencies.

    This is created once at startup and provides access to all adapters.
    Routes should access dependencies via FastAPI's Depends() mechanism,
    not by importing this directly.

    Attributes:
        settings: Application settings from environment
        db: Database adapter for Supabase/PostgREST operations
        storage: Supabase storage adapter for file operations
        queue: Task queue adapter for background job enqueueing
        openai: OpenAI client for embeddings
        opensearch: OpenSearch client for BM25 lexical search (optional)
        clip: CLIP client for visual similarity search (optional)
    """

    settings: Settings
    db: Database
    storage: SupabaseStorage
    queue: TaskQueue
    openai: OpenAIClient
    opensearch: Optional[OpenSearchClient]
    clip: Optional[ClipClient]


def create_app_context(settings: Settings) -> AppContext:
    """Create and initialize application context with all dependencies.

    This is the composition root - all adapter creation happens here.
    No I/O or heavy initialization happens during import; it's all deferred
    to this function which is called at app startup.

    Args:
        settings: Application settings

    Returns:
        AppContext with all initialized dependencies
    """
    # Create database adapter
    db = Database(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
        search_debug=settings.search_debug,
    )

    # Create storage adapter
    storage = SupabaseStorage(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
    )

    # Create task queue adapter
    queue = TaskQueue(redis_url=settings.redis_url)

    # Create OpenAI client
    openai = OpenAIClient(api_key=settings.openai_api_key)

    # Create OpenSearch client (optional)
    opensearch: Optional[OpenSearchClient] = None
    if settings.opensearch_url:
        opensearch = OpenSearchClient(
            url=settings.opensearch_url,
            timeout_s=settings.opensearch_timeout_s,
            index_name=settings.opensearch_index_scenes,
        )

    # Create CLIP client (optional)
    clip: Optional[ClipClient] = None
    if settings.clip_runpod_url and settings.clip_runpod_secret:
        clip = ClipClient(
            base_url=settings.clip_runpod_url,
            secret_key=settings.clip_runpod_secret,
            timeout_s=settings.clip_text_embedding_timeout_s,
            max_retries=settings.clip_text_embedding_max_retries,
        )

    return AppContext(
        settings=settings,
        db=db,
        storage=storage,
        queue=queue,
        openai=openai,
        opensearch=opensearch,
        clip=clip,
    )


def cleanup_app_context(ctx: AppContext) -> None:
    """Clean up application context and release resources.

    Called at application shutdown to close connections and release resources.

    Args:
        ctx: Application context to clean up
    """
    # Close CLIP client if it exists
    if ctx.clip:
        try:
            ctx.clip.close()
        except Exception:
            pass  # Best effort cleanup

    # Close task queue Redis connections
    if ctx.queue:
        try:
            ctx.queue.close()
        except Exception:
            pass  # Best effort cleanup

    # Note: Supabase clients don't need explicit cleanup
    # OpenSearch client also doesn't need explicit cleanup (httpx handled internally)
