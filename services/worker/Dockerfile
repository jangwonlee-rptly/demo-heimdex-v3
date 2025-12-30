FROM python:3.11-slim

# Install system dependencies in one layer
# Minimal dependencies for headless opencv and ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY services/worker/pyproject.toml ./

# Install PyTorch CPU-only version FIRST (separate layer for caching)
# This is the slowest dependency, so we want it cached
RUN uv pip install --system \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.1.0

# Install other heavy dependencies (separate layer)
# Use opencv-python-headless (no GUI = smaller and faster)
RUN uv pip install --system \
    opencv-python-headless==4.8.1.78 \
    numpy==1.26.0 \
    scenedetect==0.6.2

# Install remaining dependencies (lighter, changes more often)
RUN uv pip install --system \
    dramatiq[redis]>=1.15.0 \
    redis>=5.0.0 \
    psycopg[binary]>=3.1.0 \
    supabase>=2.3.0 \
    openai>=1.10.0 \
    pillow>=10.0.0 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    opensearch-py>=2.4.0 \
    open-clip-torch>=2.20.0

# Copy shared libraries (required for Dramatiq actors)
COPY libs/ ./libs/

# Copy application code
COPY services/worker/src/ ./src/

# Create temp directories
RUN mkdir -p /tmp/heimdex /tmp/clip_cache

# Set Python path (includes both /app for src/ and libs/)
ENV PYTHONPATH=/app

# Run worker via __main__.py which bootstraps context before starting Dramatiq
CMD ["python", "-m", "src"]
