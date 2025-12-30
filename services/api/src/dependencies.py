"""Dependency injection factories for FastAPI routes.

This module provides factory functions that can be used with FastAPI's Depends()
to inject dependencies into route handlers. All factories pull from the
AppContext stored in app.state.

Usage in routes:
    from .dependencies import get_db, get_storage, get_queue
    from fastapi import Depends

    @router.get("/videos")
    def list_videos(
        db: Database = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        videos = db.list_user_videos(current_user.id)
        return videos
"""
from typing import Optional

from fastapi import Request, Depends

from .context import AppContext
from .adapters.database import Database
from .adapters.supabase import SupabaseStorage
from .adapters.queue import TaskQueue
from .adapters.openai_client import OpenAIClient
from .adapters.opensearch_client import OpenSearchClient
from .adapters.clip_client import ClipClient
from .config import Settings


def get_ctx(request: Request) -> AppContext:
    """Get the application context from request state.

    This is the base dependency that all other dependencies use.

    Args:
        request: FastAPI request object

    Returns:
        AppContext from app.state

    Raises:
        RuntimeError: If context not initialized (should never happen in normal operation)
    """
    if not hasattr(request.app.state, "ctx"):
        raise RuntimeError(
            "Application context not initialized. "
            "This should never happen - check main.py lifespan."
        )
    return request.app.state.ctx


def get_settings(ctx: AppContext = Depends(get_ctx)) -> Settings:
    """Get application settings.

    Args:
        ctx: Application context (injected by FastAPI)

    Returns:
        Settings instance
    """
    return ctx.settings


def get_db(ctx: AppContext = Depends(get_ctx)) -> Database:
    """Get database adapter.

    Args:
        ctx: Application context (injected by FastAPI)

    Returns:
        Database instance
    """
    return ctx.db


def get_storage(ctx: AppContext = Depends(get_ctx)) -> SupabaseStorage:
    """Get storage adapter.

    Args:
        ctx: Application context (injected by FastAPI)

    Returns:
        SupabaseStorage instance
    """
    return ctx.storage


def get_queue(ctx: AppContext = Depends(get_ctx)) -> TaskQueue:
    """Get task queue adapter.

    Args:
        ctx: Application context (injected by FastAPI)

    Returns:
        TaskQueue instance
    """
    return ctx.queue


def get_openai(ctx: AppContext = Depends(get_ctx)) -> OpenAIClient:
    """Get OpenAI client.

    Args:
        ctx: Application context (injected by FastAPI)

    Returns:
        OpenAIClient instance
    """
    return ctx.openai


def get_opensearch(ctx: AppContext = Depends(get_ctx)) -> Optional[OpenSearchClient]:
    """Get OpenSearch client (optional).

    Args:
        ctx: Application context (injected by FastAPI)

    Returns:
        OpenSearchClient instance or None if not configured
    """
    return ctx.opensearch


def get_clip(ctx: AppContext = Depends(get_ctx)) -> Optional[ClipClient]:
    """Get CLIP client (optional).

    Args:
        ctx: Application context (injected by FastAPI)

    Returns:
        ClipClient instance or None if not configured
    """
    return ctx.clip
