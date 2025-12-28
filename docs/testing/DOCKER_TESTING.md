# Docker Testing Guide

This guide explains how to run tests in Docker containers, matching your production deployment environment.

## Quick Start

### Option 1: Using Makefile (Recommended)
```bash
# Run API tests
make test

# Run with coverage report
make test-coverage

# Run only unit tests (fast)
make quick-test

# Open test container shell for debugging
make test-shell
```

### Option 2: Using Test Script
```bash
# Run API tests
./scripts/test.sh api

# Run with coverage
./scripts/test.sh --coverage api

# Run only unit tests
./scripts/test.sh --unit api

# Debug in container shell
./scripts/test.sh --shell api
```

### Option 3: Using Docker Compose Directly
```bash
# Build and run tests
docker compose -f docker-compose.test.yml build api-test
docker compose -f docker-compose.test.yml run --rm api-test
```

---

## Available Commands

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make test` | Run API tests |
| `make test-api` | Run API tests (explicit) |
| `make test-worker` | Run worker tests |
| `make test-all` | Run all service tests |
| `make test-coverage` | Run tests with HTML coverage report |
| `make test-unit` | Run only unit tests (fast) |
| `make test-integration` | Run only integration tests |
| `make test-shell` | Open shell in test container |
| `make test-verbose` | Run tests with verbose output |
| `make quick-test` | Quick unit tests (development) |
| `make ci` | Run full CI pipeline locally |

### Test Script Options

```bash
./scripts/test.sh [OPTIONS] [SERVICE]

OPTIONS:
    -h, --help              Show help message
    -v, --verbose           Verbose test output
    -c, --coverage          Generate HTML coverage report
    -u, --unit              Run only unit tests
    -i, --integration       Run only integration tests
    --no-cache              Build without Docker cache
    --shell                 Drop into container shell

SERVICE:
    api                     API tests (default)
    worker                  Worker tests
    all                     All tests
```

---

## Test Output

### Successful Test Run
```
ℹ Heimdex Test Runner

ℹ Running tests for api service...
ℹ Building test image...
ℹ Executing tests...

============================= test session starts ==============================
platform linux -- Python 3.11.x, pytest-7.4.0, pluggy-1.3.0
rootdir: /app
configfile: pytest.ini
plugins: asyncio-0.21.0, cov-4.1.0, mock-3.12.0
collected 29 items

tests/unit/test_exceptions.py ................. [59%]
tests/unit/test_health.py ...... [79%]
tests/integration/test_videos_api.py ...... [100%]

---------- coverage: platform linux, python 3.11.x -----------
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
src/__init__.py                            0      0   100%
src/exceptions.py                        120     15    88%   45-48, 89-92
src/routes/health.py                      65      5    92%   67-68
src/routes/videos.py                     180     95    47%   ...
---------------------------------------------------------------------
TOTAL                                    365     115    68%

============================== 29 passed in 2.53s ===============================

✓ api tests passed!
```

### Coverage Report Location
After running `make test-coverage`, open:
```
services/api/htmlcov/index.html
```

---

## Development Workflow

### 1. Run Tests During Development
```bash
# Quick unit tests (no coverage)
make quick-test

# Full test with coverage
make test-coverage
```

### 2. Debug Failing Tests
```bash
# Open shell in test container
make test-shell

# Then inside container:
pytest tests/unit/test_health.py::TestHealthEndpoints::test_basic_health_check -v
pytest --pdb  # Run with debugger
exit
```

### 3. Watch Mode (Manual)
```bash
# In one terminal
make test-shell

# Inside container
while true; do clear; pytest -v; sleep 2; done
```

### 4. Test Specific File or Function
```bash
# Specific file
docker compose -f docker-compose.test.yml run --rm api-test \
  pytest tests/unit/test_health.py -v

# Specific test
docker compose -f docker-compose.test.yml run --rm api-test \
  pytest tests/unit/test_health.py::TestHealthEndpoints::test_basic_health_check -v
```

---

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run tests
        run: |
          chmod +x scripts/test.sh
          ./scripts/test.sh --coverage all

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./services/api/htmlcov/coverage.xml
```

### Local CI Simulation
```bash
# Run exactly what CI will run
make ci
```

---

## Troubleshooting

### Issue: Tests Fail with Import Errors
**Solution:** Rebuild test image
```bash
./scripts/test.sh --no-cache api
```

### Issue: Coverage Report Not Generated
**Solution:** Ensure you're using the `--coverage` flag
```bash
make test-coverage
# Report will be at: services/api/htmlcov/index.html
```

### Issue: Docker Permission Errors
**Solution:** Ensure Docker daemon is running
```bash
docker info
# If error, start Docker Desktop
```

### Issue: Tests Pass Locally but Fail in Docker
**Solution:** Environment mismatch - check:
1. Python version matches (3.11)
2. All dependencies installed in Dockerfile.test
3. Environment variables set correctly

### Issue: Want to Add Prints for Debugging
**Solution:** Use `-s` flag to see print statements
```bash
docker compose -f docker-compose.test.yml run --rm api-test \
  pytest -v -s
```

### Issue: Test Container Keeps Running
**Solution:** Use `--rm` flag (automatically included in scripts)
```bash
# Cleanup any hanging containers
docker compose -f docker-compose.test.yml down
```

---

## File Structure

```
heimdex/
├── Makefile                           # Convenient shortcuts
├── docker-compose.test.yml            # Test orchestration
├── scripts/
│   └── test.sh                        # Test runner script
└── services/
    ├── api/
    │   ├── Dockerfile.test            # Test container image
    │   ├── pytest.ini                 # Pytest config
    │   ├── tests/                     # Test files
    │   │   ├── conftest.py            # Shared fixtures
    │   │   ├── unit/
    │   │   └── integration/
    │   └── htmlcov/                   # Coverage reports (generated)
    └── worker/
        └── Dockerfile.test            # (to be created)
```

---

## Best Practices

### 1. Run Tests Before Committing
```bash
make quick-test  # Fast check
```

### 2. Run Full Test Suite Before Pushing
```bash
make test-all --coverage
```

### 3. Check Coverage Regularly
```bash
make test-coverage
open services/api/htmlcov/index.html
```

### 4. Add Tests for New Features
- Add unit tests in `tests/unit/`
- Add integration tests in `tests/integration/`
- Mark tests with `@pytest.mark.unit` or `@pytest.mark.integration`

### 5. Keep Tests Fast
- Unit tests should be < 100ms each
- Use mocks for external services
- Integration tests can be slower but keep < 1s each

---

## Differences from Local Testing

### Docker Testing (Recommended)
✅ Matches production environment exactly
✅ Consistent across all developers
✅ Isolated from host machine
✅ Easy to run in CI/CD

### Local Testing
❌ Requires local Python 3.11
❌ Requires manual dependency management
❌ Environment may differ from production
✅ Slightly faster (no container overhead)

**Recommendation:** Use Docker testing as the source of truth, local testing for quick iteration during development.

---

## Next Steps

1. **Run your first test:**
   ```bash
   make test
   ```

2. **Check coverage:**
   ```bash
   make test-coverage
   open services/api/htmlcov/index.html
   ```

3. **Add more tests:**
   - See `services/api/tests/README.md` for test writing guide

4. **Integrate into CI/CD:**
   - Add `make ci` to your CI pipeline
