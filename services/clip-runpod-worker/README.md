# CLIP RunPod Worker - Always-On HTTP Service (v2.0)

Production-grade CLIP embedding service for RunPod Pods. Exposes HTTP endpoints for image and text embedding generation.

## Overview

This service has been **rewritten from RunPod Serverless to Always-On HTTP** to:
- Support batch processing with controlled GPU batching
- Enable text embedding for visual search
- Provide predictable performance and better observability
- Reduce cold-start latency with always-on deployment

## Architecture

- **Framework**: FastAPI + uvicorn
- **Model**: OpenAI CLIP ViT-B-32 (512 dimensions)
- **Deployment**: RunPod Pod (always-on HTTP)
- **Security**: HMAC-based request authentication
- **Batching**: Two-phase pipeline (concurrent download → single GPU batch)

## Files

```
services/clip-runpod-worker/
├── app/
│   ├── __init__.py         # Package metadata
│   ├── main.py             # FastAPI application + routes
│   ├── model.py            # CLIP model loading + inference
│   ├── schemas.py          # Pydantic request/response models
│   ├── security.py         # HMAC authentication
│   ├── download.py         # Image download with concurrency control
│   └── settings.py         # Environment configuration
├── tests/
│   ├── test_auth.py        # Authentication tests
│   └── test_schemas.py     # Schema validation tests
├── Dockerfile.pod          # Production Dockerfile (CUDA 12.4)
├── requirements.txt        # Pinned Python dependencies
├── Makefile                # Development tasks
└── README.pod.md           # This file
```

## API Endpoints

### Health Check

**GET** `/health`

Returns service status and model metadata.

**Response:**
```json
{
  "status": "ok",
  "model_name": "ViT-B-32",
  "pretrained": "openai",
  "device": "cuda",
  "torch_version": "2.5.1",
  "cuda_version": "12.4",
  "uptime_seconds": 3600.5
}
```

### Single Image Embedding

**POST** `/v1/embed/image`

**Request:**
```json
{
  "image_url": "https://storage.example.com/image.jpg",
  "request_id": "scene-123",
  "normalize": true,
  "auth": {
    "ts": 1703001234,
    "sig": "abc123..."
  }
}
```

**Response:**
```json
{
  "request_id": "scene-123",
  "embedding": [0.123, -0.456, ...],
  "dim": 512,
  "model_name": "ViT-B-32",
  "pretrained": "openai",
  "device": "cuda",
  "normalized": true,
  "timings": {
    "download_ms": 150.5,
    "inference_ms": 45.2,
    "total_ms": 195.7
  }
}
```

### Batch Image Embedding

**POST** `/v1/embed/image-batch`

**Request:**
```json
{
  "items": [
    {
      "image_url": "https://storage.example.com/img1.jpg",
      "request_id": "scene-1",
      "normalize": true,
      "auth": {"ts": 1703001234, "sig": "abc123..."}
    },
    {
      "image_url": "https://storage.example.com/img2.jpg",
      "request_id": "scene-2",
      "normalize": true,
      "auth": {"ts": 1703001234, "sig": "def456..."}
    }
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "request_id": "scene-1",
      "embedding": [...],
      "dim": 512,
      "normalized": true,
      "timings": {"download_ms": 75.0, "inference_ms": 22.5, "total_ms": 97.5}
    },
    {
      "request_id": "scene-2",
      "error": {
        "code": "DOWNLOAD_ERROR",
        "message": "Image download timeout after 30s",
        "request_id": "scene-2"
      }
    }
  ],
  "model_name": "ViT-B-32",
  "pretrained": "openai",
  "device": "cuda",
  "batch_timings": {
    "total_download_ms": 150.0,
    "total_inference_ms": 45.0,
    "total_ms": 195.0
  }
}
```

### Text Embedding

**POST** `/v1/embed/text`

**Request:**
```json
{
  "text": "a person walking in the rain",
  "request_id": "query-1",
  "normalize": true,
  "auth": {
    "ts": 1703001234,
    "sig": "xyz789..."
  }
}
```

**Response:**
```json
{
  "request_id": "query-1",
  "embedding": [...],
  "dim": 512,
  "model_name": "ViT-B-32",
  "pretrained": "openai",
  "device": "cuda",
  "normalized": true,
  "timings": {
    "download_ms": null,
    "inference_ms": 12.3,
    "total_ms": 12.3
  }
}
```

## Environment Variables

### Required

- `EMBEDDING_HMAC_SECRET` - HMAC secret for authentication (must match worker client)

### Optional

**Server:**
- `HOST` - Server host (default: `0.0.0.0`)
- `PORT` - Server port (default: `8000`)
- `WORKERS` - Uvicorn workers (default: `1`, keep at 1 for GPU)
- `LOG_LEVEL` - Logging level (default: `INFO`)

**Security:**
- `ALLOW_INSECURE_AUTH` - Allow requests without auth (dev only, default: `false`)
- `AUTH_TIME_WINDOW_SECONDS` - HMAC timestamp tolerance (default: `120`)

**Model:**
- `CLIP_MODEL_NAME` - Model architecture (default: `ViT-B-32`)
- `CLIP_PRETRAINED` - Pretrained weights (default: `openai`)

**Limits:**
- `MAX_IMAGE_SIZE_BYTES` - Max image size (default: `10485760` = 10MB)
- `IMAGE_DOWNLOAD_TIMEOUT_S` - Download timeout (default: `30`)
- `DOWNLOAD_CONCURRENCY` - Max concurrent downloads (default: `8`)
- `MAX_BATCH_SIZE` - Max batch size (default: `16`)
- `TOTAL_REQUEST_TIMEOUT_S` - Total request timeout (default: `300`)

## Authentication

### HMAC Signature Generation

**For image embedding:**
```python
import hashlib
import hmac
import time

secret = "your-hmac-secret"
image_url = "https://storage.example.com/image.jpg"
ts = int(time.time())

# Canonical message: method|path|image_url
canonical = f"POST|/v1/embed/image|{image_url}"
message = f"{canonical}|{ts}"

sig = hmac.new(
    secret.encode("utf-8"),
    message.encode("utf-8"),
    hashlib.sha256
).hexdigest()

# Include in request:
# {"image_url": "...", "auth": {"ts": ts, "sig": sig}}
```

**For text embedding:**
```python
import hashlib
import hmac
import time

secret = "your-hmac-secret"
text = "a person walking in the rain"
ts = int(time.time())

# Canonical message: method|path|text_hash
text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
canonical = f"POST|/v1/embed/text|{text_hash}"
message = f"{canonical}|{ts}"

sig = hmac.new(
    secret.encode("utf-8"),
    message.encode("utf-8"),
    hashlib.sha256
).hexdigest()
```

**For batch requests:**
- Each item has its own `auth` field
- Each signature includes that specific item's image URL
- Canonical message: `POST|/v1/embed/image-batch|{item.image_url}`

### Security Features

- **Replay protection**: Timestamp must be within 120 seconds (configurable)
- **HMAC-SHA256**: Prevents tampering and unauthorized access
- **Dev mode**: Set `ALLOW_INSECURE_AUTH=1` for local testing (never in production)

## Deployment

### 1. Build Docker Image

```bash
cd services/clip-runpod-worker

# Build image
docker build -f Dockerfile.pod -t your-dockerhub-username/clip-pod-worker:2.0 .

# Test locally (CPU mode)
docker run --rm -p 8000:8000 \
  -e EMBEDDING_HMAC_SECRET="test-secret" \
  -e ALLOW_INSECURE_AUTH=1 \
  your-dockerhub-username/clip-pod-worker:2.0
```

**Verify local startup:**
```bash
# In another terminal
curl http://localhost:8000/health
```

### 2. Push to Registry

```bash
docker login
docker push your-dockerhub-username/clip-pod-worker:2.0
```

### 3. Create RunPod Pod

1. Go to https://www.runpod.io/console/pods
2. Click **Deploy**
3. **GPU Configuration**:
   - GPU Type: RTX 4090 (recommended for dev) or A100 (production)
   - GPU Count: 1
   - Container Disk: 20GB
4. **Container Image**:
   - `your-dockerhub-username/clip-pod-worker:2.0`
5. **Expose HTTP Ports**:
   - HTTP Port: `8000`
   - ✅ Enable **HTTP Service** (this generates a proxy URL)
6. **Environment Variables**:
   ```
   EMBEDDING_HMAC_SECRET=<generate-strong-random-secret>
   LOG_LEVEL=INFO
   ```
7. Click **Deploy**

### 4. Get Pod Proxy URL

After deployment:
1. Go to **Pods** → Select your pod
2. Copy the **Proxy URL** (format: `https://<pod-id>-8000.proxy.runpod.net`)
3. Test it:
   ```bash
   curl https://<pod-id>-8000.proxy.runpod.net/health
   ```

**Expected response:**
```json
{
  "status": "ok",
  "model_name": "ViT-B-32",
  "pretrained": "openai",
  "device": "cuda",
  ...
}
```

### 5. Configure Heimdex Worker

Update `services/worker/.env` (or Railway environment):

```bash
# Switch to RunPod Pod backend
CLIP_INFERENCE_BACKEND=runpod_pod

# RunPod Pod configuration
CLIP_POD_BASE_URL=https://<pod-id>-8000.proxy.runpod.net

# Security (MUST match Pod secret)
EMBEDDING_HMAC_SECRET=<same-secret-as-pod>

# Model metadata
CLIP_MODEL_NAME=ViT-B-32
```

## Local Development

### Setup

```bash
cd services/clip-runpod-worker

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu  # CPU for local dev
```

### Run Locally

```bash
# Set environment
export EMBEDDING_HMAC_SECRET="test-secret"
export ALLOW_INSECURE_AUTH=1  # Dev mode only
export LOG_LEVEL=DEBUG

# Run server
make run
# OR
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Test Endpoints

**Health check:**
```bash
curl http://localhost:8000/health
```

**Single image embedding (with auth):**
```bash
python3 << 'EOF'
import hashlib
import hmac
import time
import requests

secret = "test-secret"
image_url = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=512"
ts = int(time.time())

canonical = f"POST|/v1/embed/image|{image_url}"
message = f"{canonical}|{ts}"
sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

response = requests.post(
    "http://localhost:8000/v1/embed/image",
    json={
        "image_url": image_url,
        "request_id": "test-001",
        "normalize": True,
        "auth": {"ts": ts, "sig": sig}
    }
)

print(f"Status: {response.status_code}")
print(f"Dim: {response.json()['dim']}")
print(f"First 5 values: {response.json()['embedding'][:5]}")
EOF
```

**Text embedding:**
```bash
python3 << 'EOF'
import hashlib
import hmac
import time
import requests

secret = "test-secret"
text = "a person walking in the rain"
ts = int(time.time())

text_hash = hashlib.sha256(text.encode()).hexdigest()
canonical = f"POST|/v1/embed/text|{text_hash}"
message = f"{canonical}|{ts}"
sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

response = requests.post(
    "http://localhost:8000/v1/embed/text",
    json={
        "text": text,
        "request_id": "query-001",
        "normalize": True,
        "auth": {"ts": ts, "sig": sig}
    }
)

print(f"Status: {response.status_code}")
print(f"Dim: {response.json()['dim']}")
print(f"First 5 values: {response.json()['embedding'][:5]}")
EOF
```

### Run Tests

```bash
make test
# OR
pytest tests/ -v
```

## Makefile Targets

```bash
make install        # Install dependencies
make run            # Run server locally
make test           # Run tests
make smoke          # Run smoke test (health + 1 image + 1 text)
make docker-build   # Build Docker image
make docker-run     # Run Docker container locally
make lint           # Run linting (ruff)
make format         # Format code (black)
```

## Performance

**Typical Latency (GPU - RTX 4090):**
- Startup time: ~10-15 seconds (model loading)
- Single image: 50-150ms total (30-80ms inference)
- Batch (16 images): 200-400ms total (~100-200ms for batch inference)
- Text: 10-30ms

**Batching Benefits:**
- Single forward pass for batch → ~10x faster than sequential
- Downloads run concurrently → no I/O bottleneck
- Controlled concurrency prevents OOM

**Recommended GPU:**
- **Development**: RTX 4090 (~$0.50/hr on RunPod)
- **Production**: A100 (~$1.50/hr) or L40S (~$1.00/hr)

## Error Handling

All errors return structured JSON:

```json
{
  "error": {
    "code": "AUTH_FAILED",
    "message": "HMAC signature mismatch",
    "request_id": "scene-123"
  }
}
```

**Error Codes:**
- `AUTH_FAILED` - Authentication failure (401)
- `DOWNLOAD_ERROR` - Image download failure (400)
- `INFERENCE_ERROR` - Model inference failure (500)
- `BATCH_TOO_LARGE` - Batch exceeds max size (400)

**Batch error handling:**
- Each item can succeed or fail independently
- Successful items return embeddings
- Failed items return error details
- HTTP 200 with mixed results (check per-item status)

## Monitoring

### Logs

Structured JSON logs with request tracing:
```
2025-12-23 10:15:23 [INFO] app.main - Processing image embedding request: request_id=scene-123
2025-12-23 10:15:23 [INFO] app.download - Image downloaded successfully: size=(1920, 1080), bytes=234567, request_id=scene-123
2025-12-23 10:15:23 [INFO] app.main - Image embedding completed: request_id=scene-123, total_ms=195.7, download_ms=150.5, inference_ms=45.2
```

### Health Checks

RunPod automatically monitors `/health` endpoint:
- Interval: 30 seconds
- Timeout: 10 seconds
- Unhealthy after 3 failures

### Metrics to Monitor

- Request rate (requests/second)
- Latency (p50, p95, p99)
- Error rate
- GPU utilization
- Memory usage
- Batch size distribution

## Troubleshooting

### Pod not starting

**Check logs:**
```bash
# In RunPod console → Pods → Logs
```

**Common issues:**
- Model download failed → Check HF_HOME cache
- OOM during startup → Reduce container size or use larger GPU
- Port not exposed → Verify HTTP port 8000 is enabled

### Authentication failures

```json
{"error": {"code": "AUTH_FAILED", "message": "HMAC signature mismatch"}}
```

**Fixes:**
- Verify `EMBEDDING_HMAC_SECRET` matches on both sides
- Check timestamp is current (within 120 seconds)
- Verify canonical message format matches exactly

### Download timeouts

```json
{"error": {"code": "DOWNLOAD_ERROR", "message": "Image download timeout after 30s"}}
```

**Fixes:**
- Increase `IMAGE_DOWNLOAD_TIMEOUT_S`
- Verify image URL is publicly accessible
- Check Supabase signed URL expiration

### Batch inference OOM

**Reduce batch size:**
```bash
MAX_BATCH_SIZE=8  # Default is 16
```

Or use larger GPU tier.

## Migration from Serverless

**Old (Serverless):**
- RunPod Serverless endpoint (`/runsync`)
- Single image only
- Cold starts (0→1 workers)
- No text embedding

**New (Pod HTTP):**
- Always-on HTTP service (proxy URL)
- Batch + single image + text
- Always warm (no cold starts)
- Better observability

**Client code changes:**
- See `services/worker/src/adapters/clip_inference.py`
- Backend: `runpod_serverless` → `runpod_pod`
- URL: RunPod API → Pod proxy URL
- Batch support via `/v1/embed/image-batch`

## Next Steps

1. ✅ Deploy Pod and verify `/health`
2. ✅ Test single image embedding
3. ✅ Test batch embedding (2-4 images)
4. ✅ Test text embedding
5. Update worker client to use new backend
6. Run end-to-end video processing test
7. Monitor performance and adjust settings
8. Consider auto-scaling based on load

## Support

- **RunPod Docs**: https://docs.runpod.io/
- **OpenCLIP**: https://github.com/mlfoundations/open_clip
- **FastAPI**: https://fastapi.tiangolo.com/
