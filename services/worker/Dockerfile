FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY services/worker/pyproject.toml ./

# Install dependencies only (not the package itself)
RUN uv pip install --system \
    dramatiq[redis]>=1.15.0 \
    redis>=5.0.0 \
    psycopg[binary]>=3.1.0 \
    supabase>=2.3.0 \
    openai>=1.10.0 \
    scenedetect[opencv]>=0.6.2 \
    opencv-python>=4.8.0 \
    numpy>=1.24.0 \
    pillow>=10.0.0 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    opensearch-py>=2.4.0

# Copy shared libraries (required for Dramatiq actors)
COPY libs/ ./libs/

# Copy application code
COPY services/worker/src/ ./src/

# Create temp directory
RUN mkdir -p /tmp/heimdex

# Set Python path (includes both /app for src/ and libs/)
ENV PYTHONPATH=/app

# Run Dramatiq worker
CMD ["dramatiq", "src.tasks", "-p", "1", "-t", "1"]
