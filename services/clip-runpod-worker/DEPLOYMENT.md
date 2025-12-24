# RunPod CLIP Worker - Complete Deployment Guide

## Part 1: Push Docker Image to Docker Hub

### 1.1 Login to Docker Hub

```bash
docker login
# Enter your Docker Hub username and password
```

### 1.2 Push the Image

```bash
# The image is already tagged as jleeheimdex/heimdex-clip-worker:latest
docker push jleeheimdex/heimdex-clip-worker:latest
```

This will take a few minutes to upload (~6GB image).

**Expected output:**
```
The push refers to repository [docker.io/jleeheimdex/heimdex-clip-worker]
xxxxx: Pushed
xxxxx: Pushed
...
latest: digest: sha256:xxxxx size: xxxx
```

### 1.3 Verify Upload

Visit: https://hub.docker.com/r/jleeheimdex/heimdex-clip-worker/tags

You should see the `latest` tag with recent push time.

---

## Part 2: Configure RunPod Serverless Endpoint

### 2.1 Generate HMAC Secret

First, generate a secure HMAC secret that both Railway and RunPod will use:

```bash
# Generate a 32-character random secret
openssl rand -hex 32
```

**Save this value** - you'll need it for both RunPod and Railway configuration.

Example output: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0`

### 2.2 Access RunPod Dashboard

1. Go to https://www.runpod.io/
2. Sign in to your account
3. Click on **"Serverless"** in the left sidebar
4. Click **"+ New Endpoint"** button

### 2.3 Configure Endpoint - Basic Settings

**Endpoint Name:**
```
heimdex-clip-worker
```

**Select GPU:**
- GPU Types: **RTX 3090** (best price/performance)
- Also enable: **RTX 4090**, **A5000** (for fallback availability)
- ⚠️ **DO NOT** select A100 or H100 (overkill and expensive)

### 2.4 Configure Endpoint - Container Settings

**Container Image:**
```
jleeheimdex/heimdex-clip-worker:latest
```

**Container Registry Credentials:**
- Leave blank (public Docker Hub image)

**Container Disk:**
- 20 GB (default is fine)

### 2.5 Configure Endpoint - Environment Variables

Click **"+ Environment Variable"** and add:

| Name | Value |
|------|-------|
| `EMBEDDING_HMAC_SECRET` | `<paste your HMAC secret from step 2.1>` |

**Important:** This is the ONLY environment variable you need. `RUNPOD_SERVERLESS=1` is already set in the Dockerfile.

### 2.6 Configure Endpoint - Advanced Settings

**Idle Timeout:**
```
5 seconds
```
(Workers shut down after 5 seconds of inactivity to save costs)

**Execution Timeout:**
```
120 seconds
```
(Maximum time for a single request - allows for slow downloads)

**Max Workers:**
```
3
```
(Maximum concurrent workers for scaling)

**Min Workers:**

**For Testing:**
```
1
```
(Keeps one worker warm - no cold starts, but costs ~$0.30/hour idle)

**For Production (cost-optimized):**
```
0
```
(Workers spin up on demand - ~30-60s cold start for first request)

**GPUs per Worker:**
```
1
```

### 2.7 Review and Create

1. Review all settings
2. Click **"Deploy"** or **"Create Endpoint"**
3. Wait for deployment (~2-5 minutes)

**Expected statuses:**
- Initial: "Initializing"
- Then: "Active" (ready to receive requests)

### 2.8 Get Endpoint ID and API Key

After deployment, you'll see:

**Endpoint ID:**
```
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```
(Something like: `abc123-def456-ghi789`)

**API Key:**
- Click on your profile icon (top right)
- Go to **"Settings"** → **"API Keys"**
- Copy your API key (starts with `RUNPOD_...`)
- Or create a new one: Click **"+ Create API Key"**

**Save both values** - you'll need them for Railway configuration.

---

## Part 3: Test the RunPod Endpoint

### 3.1 Prepare Test Request

Get the RunPod endpoint URL:
```
https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync
```

Replace `{ENDPOINT_ID}` with your actual endpoint ID.

### 3.2 Generate Test HMAC Signature

```bash
# Set your HMAC secret
export HMAC_SECRET="<your-hmac-secret-from-step-2.1>"

# Test image URL (public Unsplash image)
export IMAGE_URL="https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=512"

# Current timestamp
export TIMESTAMP=$(date +%s)

# Generate HMAC signature
export SIGNATURE=$(echo -n "${IMAGE_URL}|${TIMESTAMP}" | openssl dgst -sha256 -hmac "${HMAC_SECRET}" | cut -d' ' -f2)

echo "Timestamp: ${TIMESTAMP}"
echo "Signature: ${SIGNATURE}"
```

### 3.3 Test with curl

```bash
# Replace with your actual values
export RUNPOD_API_KEY="your-runpod-api-key"
export ENDPOINT_ID="your-endpoint-id"

curl -X POST "https://api.runpod.ai/v2/${ENDPOINT_ID}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "image_url": "'"${IMAGE_URL}"'",
      "request_id": "test-smoke",
      "normalize": true,
      "auth": {
        "ts": '"${TIMESTAMP}"',
        "sig": "'"${SIGNATURE}"'"
      }
    }
  }'
```

### 3.4 Expected Response

**Success (200 OK):**
```json
{
  "delayTime": 1234,
  "executionTime": 567,
  "id": "sync-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "output": {
    "request_id": "test-smoke",
    "embedding": [0.123, -0.456, 0.789, ...],
    "dim": 512,
    "model": "ViT-B-32",
    "pretrained": "openai",
    "normalized": true,
    "timings": {
      "download_ms": 234.56,
      "inference_ms": 123.45,
      "total_ms": 358.01
    }
  },
  "status": "COMPLETED"
}
```

**First request timing:**
- If Min Workers = 0: ~30-60 seconds (cold start - container starting)
- If Min Workers = 1: ~200-500ms (worker already warm)

**Subsequent requests:** ~200-500ms

### 3.5 Troubleshooting

**Status: FAILED with authentication error:**
```json
{
  "output": {
    "error": "Authentication failed",
    "request_id": "test-smoke"
  },
  "status": "COMPLETED"
}
```
→ Check that `EMBEDDING_HMAC_SECRET` in RunPod matches the secret used to generate signature

**Status: IN_QUEUE for several minutes:**
- No available GPU workers
- Try changing GPU type to RTX 3090 or RTX 4090
- Or increase Max Workers

**Status: FAILED with "Container exited":**
- Check RunPod logs: Go to endpoint → "Logs" tab
- Look for error messages in startup diagnostics

---

## Part 4: Configure Railway Worker

### 4.1 Add Environment Variables to Railway

Go to your Railway project for the Heimdex worker service and add:

```bash
# RunPod Configuration
CLIP_INFERENCE_BACKEND=runpod
RUNPOD_API_KEY=<your-runpod-api-key>
RUNPOD_CLIP_ENDPOINT_ID=<your-endpoint-id>
RUNPOD_TIMEOUT_S=60.0

# HMAC Secret (MUST match RunPod)
EMBEDDING_HMAC_SECRET=<your-hmac-secret-from-step-2.1>
```

### 4.2 Deploy Railway Changes

Railway will automatically redeploy when you save the environment variables.

### 4.3 Monitor Railway Logs

Watch for log messages like:
```
Scene X: Generating CLIP embedding (backend=runpod)
✓ CLIP embedding generated via RunPod in 0.234s
```

---

## Part 5: End-to-End Test

### 5.1 Run Smoke Test Script

From the Heimdex worker service:

```bash
cd services/worker

# Set environment variables
export RUNPOD_API_KEY="your-api-key"
export RUNPOD_CLIP_ENDPOINT_ID="your-endpoint-id"
export EMBEDDING_HMAC_SECRET="your-hmac-secret"
export SUPABASE_URL="your-supabase-url"
export SUPABASE_SERVICE_ROLE_KEY="your-service-key"

# Run smoke test
python -m src.scripts.test_runpod_clip
```

### 5.2 Expected Output

```
============================================================
RunPod CLIP Endpoint Smoke Test
============================================================

Validating configuration...
✓ RUNPOD_API_KEY: RUNPOD_XXX...
✓ RUNPOD_CLIP_ENDPOINT_ID: abc123-de...
✓ EMBEDDING_HMAC_SECRET: a1b2c3d4e5...
✓ SUPABASE_URL: https://xxx...
✓ SUPABASE_SERVICE_ROLE_KEY: eyJhbGciO...
✓ Configuration valid

Uploading test image: clip_smoke_test.jpg
✓ Image uploaded: https://xxx.supabase.co/storage/v1/object/public/...
✓ Signed URL created: https://xxx.supabase.co/storage/v1/object/sign/...

Calling RunPod CLIP endpoint (request_id=smoke-test)...
✓ RunPod request completed in 0.456s

Validating response...
✓ Field 'embedding' present
✓ Field 'dim' present
✓ Field 'model' present
✓ Field 'normalized' present
✓ Field 'request_id' present
✓ Embedding is a list
✓ Embedding dimension: 512
✓ Embedding values are numeric
✓ Embedding is normalized (L2 norm: 1.0000)

Timing breakdown:
  Download: 123.45ms
  Inference: 89.12ms
  Total: 212.57ms

Model information:
  Model: ViT-B-32
  Pretrained: openai
  Normalized: True

============================================================
✅ Smoke test PASSED
============================================================
```

---

## Part 6: Monitor and Optimize

### 6.1 Monitor RunPod Costs

- Go to RunPod Dashboard → Billing
- Check hourly costs
- RTX 3090: ~$0.30/hour when active
- With Min Workers = 0, you only pay for execution time

### 6.2 Adjust Min Workers Based on Usage

**Low traffic (< 10 requests/hour):**
```
Min Workers: 0
```
Cold starts acceptable, cost-optimized

**Medium traffic (10-100 requests/hour):**
```
Min Workers: 1
```
Always warm, consistent latency

**High traffic (> 100 requests/hour):**
```
Min Workers: 2-3
Max Workers: 5-10
```
Scale with demand

### 6.3 Monitor Performance

Check RunPod endpoint analytics:
- Request count
- Average execution time
- Error rate
- GPU utilization

---

## Rollback Plan

If RunPod has issues, instantly rollback to local CPU:

**In Railway, change environment variable:**
```bash
CLIP_INFERENCE_BACKEND=local  # or "off"
```

Railway will redeploy in ~30 seconds and use local CPU CLIP again.

---

## Quick Reference

### Docker Hub Image
```
jleeheimdex/heimdex-clip-worker:latest
```

### RunPod Endpoint URL Format
```
https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync
```

### Required Environment Variables (Railway)
```bash
CLIP_INFERENCE_BACKEND=runpod
RUNPOD_API_KEY=<from RunPod settings>
RUNPOD_CLIP_ENDPOINT_ID=<from endpoint page>
EMBEDDING_HMAC_SECRET=<generated secret>
RUNPOD_TIMEOUT_S=60.0
```

### Required Environment Variables (RunPod)
```bash
EMBEDDING_HMAC_SECRET=<same as Railway>
```

### Recommended GPU Types (in order)
1. RTX 3090 (best value)
2. RTX 4090 (faster, more expensive)
3. A5000 (fallback)

### Cost Estimates (RTX 3090)
- Per request: ~$0.0001 (0.01 cents)
- 1000 requests: ~$0.10
- Min Workers = 1: ~$0.30/hour idle + per-request
- Min Workers = 0: per-request only

---

## Next Steps

1. ✅ Push Docker image to Docker Hub
2. ✅ Generate HMAC secret
3. ✅ Create RunPod endpoint
4. ✅ Test RunPod endpoint with curl
5. ✅ Configure Railway environment variables
6. ✅ Run end-to-end smoke test
7. ✅ Process test video and verify embeddings
8. ✅ Monitor costs and performance
9. ✅ Adjust Min Workers based on traffic patterns
