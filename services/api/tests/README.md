# Heimdex API Tests

This directory contains the test suite for the Heimdex API service.

## Structure

```
tests/
├── conftest.py              # Shared fixtures and pytest configuration
├── unit/                    # Unit tests (fast, no external dependencies)
│   ├── test_exceptions.py   # Test custom exception hierarchy
│   └── test_health.py       # Test health check endpoints
└── integration/             # Integration tests (may use mocked services)
    └── test_videos_api.py   # Test video API endpoints
```

## Running Tests

### Run all tests
```bash
cd services/api
pytest
```

### Run only unit tests
```bash
pytest -m unit
```

### Run only integration tests
```bash
pytest -m integration
```

### Run with coverage report
```bash
pytest --cov=src --cov-report=html
# Open htmlcov/index.html in browser to view detailed coverage
```

### Run specific test file
```bash
pytest tests/unit/test_health.py
```

### Run specific test function
```bash
pytest tests/unit/test_health.py::TestHealthEndpoints::test_basic_health_check
```

### Verbose output
```bash
pytest -v
```

### Stop on first failure
```bash
pytest -x
```

## Writing Tests

### Unit Tests

Unit tests should:
- Be fast (< 100ms each)
- Not require external services
- Use mocked dependencies
- Test a single unit of code

Example:
```python
@pytest.mark.unit
def test_video_not_found_exception():
    """Test VideoNotFoundException creation."""
    video_id = "12345678-1234-5678-1234-567812345678"
    exc = VideoNotFoundException(video_id)

    assert exc.status_code == 404
    assert exc.error_code == "VIDEO_NOT_FOUND"
```

### Integration Tests

Integration tests should:
- Test multiple components working together
- Use mocked external services (database, storage, queue)
- Verify API contract (request/response format)
- Test error handling

Example:
```python
@pytest.mark.integration
@patch("src.routes.videos.db")
def test_get_video(mock_db, client, video_factory):
    """Test GET /v1/videos/{id} endpoint."""
    test_video = video_factory()
    mock_db.get_video.return_value = test_video

    response = client.get(f"/v1/videos/{test_video.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_video.id)
```

## Available Fixtures

See `conftest.py` for all available fixtures:

- `client` - FastAPI TestClient
- `mock_user_id` - Fixed test user UUID
- `auth_headers` - HTTP headers with authentication
- `mock_db` - Mocked database adapter
- `mock_storage` - Mocked storage adapter
- `mock_queue` - Mocked task queue
- `mock_openai` - Mocked OpenAI client
- `video_factory` - Factory for creating test videos
- `user_profile_factory` - Factory for creating test user profiles

## Test Markers

Tests can be marked with custom markers:

- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests

## Coverage Goals

Target coverage levels:
- Critical paths (video processing, search): 80%+
- API endpoints: 70%+
- Utilities and helpers: 60%+
- Overall: 70%+

## CI/CD Integration

Tests run automatically in CI/CD pipeline:
- All tests must pass before merge
- Coverage must meet minimum thresholds
- Linting must pass (if configured)

## Troubleshooting

### Tests fail with import errors
```bash
# Make sure you're in the API service directory
cd services/api

# Install dependencies
uv sync
```

### Mock not working as expected
```python
# Use patch.object for class methods
from unittest.mock import patch

@patch.object(db, 'get_video')
def test_something(mock_get_video):
    mock_get_video.return_value = test_video
```

### Async test issues
```python
# Use pytest.mark.asyncio for async tests
import pytest

@pytest.mark.asyncio
async def test_async_endpoint():
    result = await some_async_function()
    assert result is not None
```
