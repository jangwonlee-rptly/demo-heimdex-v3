"""Import safety tests to ensure no side effects at import time.

These tests verify that Phase 1 refactoring goals are met:
- No network connections at import time
- No Redis client creation at import time
- No Supabase client creation at import time
- No model loading at import time
"""
import sys
from unittest.mock import patch, MagicMock
import pytest


def test_import_config_no_side_effects():
    """Test that importing config.py doesn't create Settings instance."""
    # Settings() reads from environment, which is OK
    # But we verify the global 'settings' is None
    from src import config

    assert config.settings is None, "Global settings should be None after Phase 1 refactor"


def test_import_database_adapter_no_client_creation():
    """Test that importing database.py doesn't create Supabase client."""
    # Mock create_client to fail if called at import time
    with patch('src.adapters.database.create_client') as mock_create:
        mock_create.side_effect = AssertionError("Supabase client created at import time!")

        # This should NOT trigger create_client
        from src.adapters import database

        # Verify global is None
        assert database.db is None, "Global db should be None after Phase 1 refactor"

        # Verify create_client was not called during import
        mock_create.assert_not_called()


def test_import_supabase_adapter_no_client_creation():
    """Test that importing supabase.py doesn't create Supabase client."""
    with patch('src.adapters.supabase.create_client') as mock_create:
        mock_create.side_effect = AssertionError("Supabase client created at import time!")

        from src.adapters import supabase

        assert supabase.storage is None, "Global storage should be None after Phase 1 refactor"
        mock_create.assert_not_called()


def test_import_queue_adapter_no_redis_connection():
    """Test that importing queue.py doesn't create Redis broker."""
    with patch('src.adapters.queue.RedisBroker') as mock_broker:
        mock_broker.side_effect = AssertionError("Redis broker created at import time!")

        from src.adapters import queue

        assert queue.task_queue is None, "Global task_queue should be None after Phase 1 refactor"
        mock_broker.assert_not_called()


def test_import_openai_adapter_no_client_creation():
    """Test that importing openai_client.py doesn't create OpenAI client."""
    with patch('src.adapters.openai_client.OpenAI') as mock_openai:
        mock_openai.side_effect = AssertionError("OpenAI client created at import time!")

        from src.adapters import openai_client

        assert openai_client.openai_client is None, "Global openai_client should be None after Phase 1 refactor"
        mock_openai.assert_not_called()


def test_import_opensearch_adapter_no_client_creation():
    """Test that importing opensearch_client.py doesn't create OpenSearch client."""
    with patch('src.adapters.opensearch_client.OpenSearch') as mock_opensearch:
        mock_opensearch.side_effect = AssertionError("OpenSearch client created at import time!")

        from src.adapters import opensearch_client

        assert opensearch_client.opensearch_client is None, "Global opensearch_client should be None after Phase 1 refactor"
        mock_opensearch.assert_not_called()


def test_import_main_no_app_start():
    """Test that importing main.py doesn't start the FastAPI app."""
    # main.py should be importable without side effects
    # The lifespan context manager should not execute until app.run()
    from src import main

    # App should be created but lifespan not yet executed
    assert main.app is not None
    assert hasattr(main.app.state, 'ctx') is False, "App context should not be initialized until lifespan starts"


def test_context_creation_with_mocked_adapters():
    """Test that create_app_context properly creates all adapters."""
    from src.context import create_app_context
    from src.config import Settings

    # Create settings
    settings = Settings()

    # Create context (this WILL create clients, but that's the point)
    # We just verify it works and creates the right structure
    ctx = create_app_context(settings)

    assert ctx.settings is settings
    assert ctx.db is not None
    assert ctx.storage is not None
    assert ctx.queue is not None
    assert ctx.openai is not None
    # opensearch and clip are optional
    assert hasattr(ctx, 'opensearch')
    assert hasattr(ctx, 'clip')


def test_dependency_factories_require_app_context():
    """Test that dependency factories fail gracefully without app context."""
    from src.dependencies import get_ctx
    from fastapi import Request

    # Create mock request without ctx
    mock_request = MagicMock(spec=Request)
    mock_request.app.state = MagicMock()
    del mock_request.app.state.ctx  # Ensure ctx doesn't exist

    with pytest.raises(RuntimeError, match="Application context not initialized"):
        get_ctx(mock_request)
