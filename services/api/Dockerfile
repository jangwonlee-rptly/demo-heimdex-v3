FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY services/api/pyproject.toml ./

# Install dependencies only (not the package itself)
RUN uv pip install --system \
    fastapi>=0.109.0 \
    uvicorn[standard]>=0.27.0 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    python-jose[cryptography]>=3.3.0 \
    python-multipart>=0.0.6 \
    httpx>=0.26.0 \
    psycopg[binary]>=3.1.0 \
    supabase>=2.3.0 \
    dramatiq[redis]>=1.15.0 \
    redis>=5.0.0 \
    openai>=1.10.0

# Copy shared libraries (required for Dramatiq actors)
COPY libs/ ./libs/

# Copy application code
COPY services/api/src/ ./src/

# Expose port
EXPOSE 8000

# Set Python path (includes both /app and /app for libs/)
ENV PYTHONPATH=/app

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
