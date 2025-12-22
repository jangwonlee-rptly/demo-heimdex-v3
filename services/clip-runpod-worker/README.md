# RunPod CLIP Worker

GPU-accelerated CLIP embedding generation service for Heimdex, deployed on RunPod Serverless.

## Overview

This service handles CLIP image embedding generation on GPU infrastructure, offloading CPU-intensive inference from the main Railway deployment. It receives image URLs, downloads the images, generates embeddings using CLIP ViT-B-32, and returns normalized 512-dimensional vectors.

## Architecture

- **Model**: OpenAI CLIP ViT-B-32 (512 dimensions)
- **Framework**: OpenCLIP + PyTorch
- **Deployment**: RunPod Serverless (GPU)
- **Security**: HMAC-based request authentication
- **Cold Start Optimization**: Model pre-downloaded in Docker image

## Files

- `handler.py` - Main RunPod serverless handler
- `Dockerfile` - GPU-optimized container image
- `requirements.txt` - Python dependencies
- `test_input.json` - Example input for testing
- `.dockerignore` - Docker build exclusions

## Input/Output Contract

### Input Schema

```json
{
  "input": {
    "image_url": "https://signed-url-to-thumbnail",
    "request_id": "scene-uuid-or-identifier",
    "normalize": true,
    "model": "ViT-B-32",
    "auth": {
      "ts": 1730000000,
      "sig": "hmac_sha256_signature"
    }
  }
}
```

**Fields:**
- `image_url` (required): Publicly accessible URL to image (typically signed URL from Supabase Storage)
- `request_id` (optional): Identifier for request tracing (e.g., scene ID)
- `normalize` (optional): Whether to L2-normalize embedding (default: true)
- `model` (optional): Model name (informational; only ViT-B-32 supported currently)
- `auth` (required): Authentication object
  - `ts`: Unix timestamp when request was created
  - `sig`: HMAC-SHA256 signature of `image_url|ts` using shared secret

### Output Schema

**Success:**
```json
{
  "request_id": "scene-uuid",
  "embedding": [0.123, -0.456, ...],
  "dim": 512,
  "model": "ViT-B-32",
  "pretrained": "openai",
  "normalized": true,
  "timings": {
    "download_ms": 234.56,
    "inference_ms": 89.12,
    "total_ms": 323.68
  }
}
```

**Error:**
```json
{
  "error": "Error message description",
  "request_id": "scene-uuid"
}
```

## Environment Variables

### Required (RunPod Endpoint)

- `EMBEDDING_HMAC_SECRET` - Shared secret for HMAC authentication (must match Heimdex worker)

### Optional (RunPod Endpoint)

- `CLIP_MODEL_NAME` - Model architecture (default: `ViT-B-32`)
- `CLIP_PRETRAINED` - Pretrained weights (default: `openai`)
- `MAX_IMAGE_SIZE_BYTES` - Max image download size (default: `10485760` = 10MB)
- `IMAGE_DOWNLOAD_TIMEOUT` - Image download timeout in seconds (default: `30`)
- `AUTH_TIME_WINDOW_SECONDS` - HMAC timestamp tolerance (default: `120`)

## Deployment Instructions

### 1. Build Docker Image

```bash
cd services/clip-runpod-worker

# Build image
docker build -t your-dockerhub-username/heimdex-clip-worker:latest .

# Test locally (CPU mode)
docker run --rm \
  -e EMBEDDING_HMAC_SECRET="your-secret-here" \
  your-dockerhub-username/heimdex-clip-worker:latest
```

### 2. Push to Docker Registry

```bash
# Login to Docker Hub (or your registry)
docker login

# Push image
docker push your-dockerhub-username/heimdex-clip-worker:latest
```

### 3. Create RunPod Endpoint

1. Go to https://www.runpod.io/console/serverless
2. Click "New Endpoint"
3. Configure:
   - **Name**: `heimdex-clip-worker`
   - **Container Image**: `your-dockerhub-username/heimdex-clip-worker:latest`
   - **GPU Type**: Select GPU tier (e.g., RTX 4090, A100)
   - **Workers**:
     - Min: 0 (auto-scale to zero)
     - Max: 3-5 (adjust based on load)
   - **Idle Timeout**: 30 seconds
   - **Execution Timeout**: 60 seconds
   - **Environment Variables**:
     ```
     EMBEDDING_HMAC_SECRET=<generate-strong-random-secret>
     ```

4. Click "Deploy"
5. Copy the **Endpoint ID** (format: `xxxxxxxxxx`)
6. Copy your **API Key** from RunPod settings

### 4. Configure Heimdex Worker (Railway)

Add these environment variables to your Railway worker service:

```bash
# RunPod Configuration
CLIP_INFERENCE_BACKEND=runpod
RUNPOD_API_KEY=<your-runpod-api-key>
RUNPOD_CLIP_ENDPOINT_ID=<your-endpoint-id>
RUNPOD_TIMEOUT_S=60

# Security (MUST match RunPod secret)
EMBEDDING_HMAC_SECRET=<same-secret-as-runpod>

# CLIP Configuration
CLIP_MODEL_NAME=ViT-B-32
CLIP_MODEL_VERSION=openai-vit-b-32-v1
```

## Testing

### Local Testing (Without RunPod)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable
export EMBEDDING_HMAC_SECRET="test-secret"

# Run handler locally
python handler.py
```

### Test with RunPod CLI

```bash
# Install RunPod CLI
pip install runpod

# Generate HMAC signature
python -c "
import hmac, hashlib, time
secret = 'your-secret'
image_url = 'https://example.com/image.jpg'
ts = int(time.time())
message = f'{image_url}|{ts}'
sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
print(f'ts: {ts}')
print(f'sig: {sig}')
"

# Create test_request.json with actual signature
cat > test_request.json << EOF
{
  "input": {
    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1200px-Cat03.jpg",
    "request_id": "test-001",
    "normalize": true,
    "auth": {
      "ts": <timestamp-from-above>,
      "sig": "<signature-from-above>"
    }
  }
}
EOF

# Test endpoint
curl -X POST https://api.runpod.ai/v2/<ENDPOINT_ID>/runsync \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d @test_request.json
```

### Expected Response

```json
{
  "id": "sync-request-id",
  "status": "COMPLETED",
  "output": {
    "request_id": "test-001",
    "embedding": [0.123, -0.456, ...],
    "dim": 512,
    "model": "ViT-B-32",
    "pretrained": "openai",
    "normalized": true,
    "timings": {
      "download_ms": 150.0,
      "inference_ms": 45.0,
      "total_ms": 195.0
    }
  }
}
```

## Smoke Test Script

See `../worker/src/scripts/test_runpod_clip.py` for an end-to-end smoke test that:
1. Generates signed URL from Supabase Storage
2. Creates HMAC signature
3. Calls RunPod endpoint
4. Validates response shape and dimensions

## Performance

**Typical Latency (GPU):**
- Cold start (first request): ~5-10 seconds (model loading)
- Warm request: ~200-500ms total
  - Image download: 50-200ms
  - Inference: 30-150ms (depending on GPU)

**Recommended GPU Tiers:**
- Development: RTX 4090 (~$0.50/hr)
- Production: A100 (~$1.50/hr) or L40S (~$1.00/hr)

## Security

### HMAC Authentication

Prevents unauthorized access to the RunPod endpoint:

1. Heimdex worker generates signature:
   ```python
   message = f"{image_url}|{current_timestamp}"
   signature = hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()
   ```

2. RunPod worker validates:
   - Timestamp within 120 seconds (prevents replay attacks)
   - Signature matches expected value

### Image Download Safety

- Max image size: 10MB (configurable)
- Download timeout: 30 seconds
- Streaming download with size checks
- Validates image format after download

## Monitoring

### RunPod Dashboard

Monitor in RunPod console:
- Request rate
- Error rate
- Average latency
- Worker scaling (active/idle)
- GPU utilization

### Logs

View logs in RunPod console:
```
[INFO] Processing request: scene-abc-123
[INFO] Image downloaded successfully: (1920, 1080)
[INFO] Generated embedding with 512 dimensions
[INFO] Request scene-abc-123 completed in 0.234s (download: 0.150s, inference: 0.084s)
```

## Troubleshooting

### Common Issues

**1. Authentication failures**
```json
{"error": "Authentication failed", "request_id": "..."}
```
- Verify `EMBEDDING_HMAC_SECRET` matches on both sides
- Check timestamp is current (within 120 seconds)
- Ensure signature calculation matches exactly

**2. Image download timeouts**
```json
{"error": "Image download failed: Timeout", "request_id": "..."}
```
- Increase `IMAGE_DOWNLOAD_TIMEOUT`
- Verify image URL is publicly accessible
- Check signed URL expiration

**3. Cold start latency**
- First request after idle period loads model (~5-10s)
- Increase min workers to 1 for always-warm endpoint
- Trade-off: Higher cost vs lower latency

**4. Out of memory errors**
- Reduce `MAX_IMAGE_SIZE_BYTES`
- Use smaller GPU tier (may increase per-request cost)
- Ensure images are reasonable size (<5MB recommended)

## Rollback Plan

If RunPod endpoint has issues, rollback to local CLIP:

```bash
# In Railway worker service
CLIP_INFERENCE_BACKEND=local
```

This will use the existing `ClipEmbedder` adapter on CPU.

Alternatively, disable CLIP entirely:
```bash
CLIP_INFERENCE_BACKEND=off
```

## Cost Optimization

**Minimize cold starts:**
- Set min workers to 1 during peak hours
- Use webhook to keep endpoint warm if needed

**Right-size GPU:**
- Start with RTX 4090 for development
- Monitor GPU utilization in RunPod dashboard
- Upgrade to A100 only if seeing GPU bottlenecks

**Batch processing:**
- For backfill operations, process in batches with controlled concurrency
- Use worker pool to keep RunPod endpoint warm

## Next Steps

1. Deploy RunPod endpoint
2. Configure Heimdex worker environment variables
3. Run smoke test to verify connectivity
4. Process test video to confirm end-to-end flow
5. Monitor logs and performance
6. Adjust worker scaling based on load

## Support

For issues or questions:
- RunPod Documentation: https://docs.runpod.io/
- OpenCLIP Documentation: https://github.com/mlfoundations/open_clip
- Heimdex Internal: See `docs/clip-runpod-migration.md`
