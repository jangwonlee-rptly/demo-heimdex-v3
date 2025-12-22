# CLIP RunPod Migration Guide

## Overview

This guide covers the migration of CLIP image embedding generation from local CPU inference (in Railway) to RunPod Serverless GPU infrastructure. This change improves performance, reduces Railway memory pressure, and enables cost-effective GPU acceleration.

## Architecture Changes

### Before (Local CPU)

```
Video Processing Pipeline (Railway Worker)
├─ Extract scene keyframes
├─ Upload thumbnails to Supabase Storage
├─ Load CLIP model in-process (CPU, ~500MB RAM)
├─ Generate embedding locally (2-5 seconds per scene on CPU)
└─ Store embedding in PostgreSQL (pgvector)
```

**Issues:**
- Slow inference on CPU (2-5 seconds per scene)
- High memory usage (~500MB for model + inference overhead)
- Railway deployment constraints (memory limits, cost)

### After (RunPod GPU)

```
Video Processing Pipeline (Railway Worker)
├─ Extract scene keyframes
├─ Upload thumbnails to Supabase Storage
├─ Generate signed URL (5-minute expiration)
├─ Call RunPod CLIP endpoint with HMAC authentication
│  └─ RunPod Worker (GPU):
│     ├─ Validate HMAC signature
│     ├─ Download image from signed URL
│     ├─ Run CLIP inference (30-150ms on GPU)
│     └─ Return embedding vector
└─ Store embedding in PostgreSQL (pgvector)
```

**Benefits:**
- Fast inference on GPU (30-150ms per scene, 10-50x faster)
- No local CLIP model loading (Railway memory freed)
- Auto-scaling (RunPod scales workers based on load)
- Cost-effective (pay only for GPU time used)

## Components

### 1. RunPod Worker Service

**Location:** `services/clip-runpod-worker/`

**Files:**
- `handler.py` - RunPod serverless handler with CLIP model
- `Dockerfile` - GPU-optimized container image (CUDA 11.8)
- `requirements.txt` - Python dependencies
- `README.md` - Deployment instructions

**Key Features:**
- Pre-loads CLIP model at startup (reduces cold start latency)
- GPU acceleration with CUDA support
- HMAC authentication for security
- Structured error handling and logging

### 2. Heimdex Worker Adapter

**Location:** `services/worker/src/adapters/clip_inference.py`

**Key Features:**
- RunPod API client with retry logic
- HMAC signature generation
- Exponential backoff for transient failures
- Structured exceptions (auth, network, timeout)

### 3. Supabase Storage Integration

**Location:** `services/worker/src/adapters/supabase.py`

**New Method:** `create_signed_url(storage_path, expires_in=300)`

Generates short-lived signed URLs for secure image access by RunPod workers.

### 4. Ingestion Pipeline Updates

**Location:** `services/worker/src/domain/sidecar_builder.py`

**Changes:**
- Backend routing logic (`runpod` / `local` / `off`)
- `_generate_clip_embedding_runpod()` - RunPod GPU path
- `_generate_clip_embedding_local()` - Local CPU fallback
- Thumbnail upload + signed URL generation

## Deployment Steps

### Step 1: Build and Push RunPod Docker Image

```bash
cd services/clip-runpod-worker

# Build the image
docker build -t your-dockerhub-username/heimdex-clip-worker:latest .

# Test locally (optional)
docker run --rm \
  -e EMBEDDING_HMAC_SECRET="test-secret-123" \
  your-dockerhub-username/heimdex-clip-worker:latest

# Push to registry
docker login
docker push your-dockerhub-username/heimdex-clip-worker:latest
```

### Step 2: Create RunPod Endpoint

1. Go to https://www.runpod.io/console/serverless
2. Click "New Endpoint"
3. Configure:
   - **Name**: `heimdex-clip-worker`
   - **Container Image**: `your-dockerhub-username/heimdex-clip-worker:latest`
   - **GPU Type**: RTX 4090 or A100 (recommended: start with RTX 4090)
   - **Min Workers**: 0 (auto-scale to zero when idle)
   - **Max Workers**: 3-5 (adjust based on expected load)
   - **Idle Timeout**: 30 seconds
   - **Execution Timeout**: 60 seconds

4. Set Environment Variables:
   ```
   EMBEDDING_HMAC_SECRET=<generate-strong-random-secret>
   ```

   Generate a strong secret:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

5. Click "Deploy" and wait for endpoint to be ready

6. **Save the following:**
   - Endpoint ID (format: `xxxxxxxxxx`)
   - Your RunPod API Key (from account settings)

### Step 3: Configure Railway Worker Environment Variables

Add these variables to your Railway worker service:

```bash
# CLIP Backend Configuration
CLIP_INFERENCE_BACKEND=runpod
CLIP_MODEL_VERSION=openai-vit-b-32-v1

# RunPod Configuration
RUNPOD_API_KEY=<your-runpod-api-key>
RUNPOD_CLIP_ENDPOINT_ID=<your-endpoint-id>
RUNPOD_TIMEOUT_S=60

# Security (MUST match RunPod secret exactly)
EMBEDDING_HMAC_SECRET=<same-secret-as-runpod>

# Keep existing CLIP config
CLIP_ENABLED=true
CLIP_MODEL_NAME=ViT-B-32
```

**Important:** `EMBEDDING_HMAC_SECRET` must be identical on both Railway and RunPod.

### Step 4: Deploy Railway Worker

```bash
# Commit changes
git add .
git commit -m "Migrate CLIP inference to RunPod GPU backend"
git push

# Railway will auto-deploy
# Monitor logs for CLIP backend confirmation
```

### Step 5: Smoke Test

Run the smoke test script:

```bash
cd services/worker

# Set environment variables
export RUNPOD_API_KEY="<your-api-key>"
export RUNPOD_CLIP_ENDPOINT_ID="<your-endpoint-id>"
export EMBEDDING_HMAC_SECRET="<your-secret>"

# Run test
python -m src.scripts.test_runpod_clip
```

Expected output:
```
✓ RunPod CLIP endpoint reachable
✓ Signed URL generation working
✓ HMAC authentication working
✓ Embedding generated: 512 dimensions
✓ Latency: 234ms (download: 50ms, inference: 45ms)
```

### Step 6: Process Test Video

```bash
# Process a small test video end-to-end
python -m src.scripts.process_video --video-id <test-video-uuid>

# Verify in logs:
# - "CLIP embedding generated (backend=runpod)"
# - "RunPod CLIP embedding generated (dim=512, inference=45ms)"
# - No errors or timeouts
```

### Step 7: Verify Database

```sql
-- Check that embeddings are being stored
SELECT
  id,
  index,
  embedding_visual_clip IS NOT NULL as has_clip,
  visual_clip_metadata->>'backend' as backend,
  visual_clip_metadata->>'inference_time_ms' as inference_ms
FROM video_scenes
WHERE video_id = '<test-video-uuid>'
ORDER BY index;

-- Expected:
-- has_clip | backend | inference_ms
-- true     | runpod  | 45.2
-- true     | runpod  | 52.1
-- ...
```

## Configuration Reference

### Environment Variables

#### Railway Worker (Required)

| Variable | Description | Example |
|----------|-------------|---------|
| `CLIP_INFERENCE_BACKEND` | Backend mode | `runpod` (GPU), `local` (CPU), `off` (disabled) |
| `RUNPOD_API_KEY` | RunPod API key | `ABC123...` |
| `RUNPOD_CLIP_ENDPOINT_ID` | RunPod endpoint ID | `abc123xyz` |
| `RUNPOD_TIMEOUT_S` | Request timeout | `60` |
| `EMBEDDING_HMAC_SECRET` | Shared secret for auth | (64-char hex) |
| `CLIP_MODEL_VERSION` | Model version identifier | `openai-vit-b-32-v1` |

#### Railway Worker (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `CLIP_ENABLED` | Enable CLIP embeddings | `true` |
| `CLIP_MODEL_NAME` | Model architecture | `ViT-B-32` |

#### RunPod Endpoint (Required)

| Variable | Description | Example |
|----------|-------------|---------|
| `EMBEDDING_HMAC_SECRET` | Shared secret (must match Railway) | (64-char hex) |

#### RunPod Endpoint (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `CLIP_MODEL_NAME` | Model architecture | `ViT-B-32` |
| `CLIP_PRETRAINED` | Pretrained weights | `openai` |
| `MAX_IMAGE_SIZE_BYTES` | Max image download size | `10485760` (10MB) |
| `IMAGE_DOWNLOAD_TIMEOUT` | Image download timeout | `30` (seconds) |
| `AUTH_TIME_WINDOW_SECONDS` | HMAC timestamp tolerance | `120` (2 minutes) |

## Rollback Procedures

### Option 1: Switch to Local CPU Backend

If RunPod has issues, immediately switch back to local CLIP:

```bash
# In Railway worker environment variables
CLIP_INFERENCE_BACKEND=local
```

Railway will restart and use the existing `ClipEmbedder` on CPU. This is slower but fully functional.

### Option 2: Disable CLIP Entirely

If you need to disable CLIP temporarily:

```bash
# In Railway worker environment variables
CLIP_INFERENCE_BACKEND=off
# OR
CLIP_ENABLED=false
```

Ingestion will continue without CLIP embeddings. Search will still work using text embeddings.

### Option 3: Full Rollback

To completely revert the migration:

1. Set `CLIP_INFERENCE_BACKEND=local`
2. Deploy previous git commit:
   ```bash
   git revert HEAD
   git push
   ```
3. Delete RunPod endpoint (optional)

## Troubleshooting

### Authentication Errors

**Symptom:**
```
ERROR: RunPod authentication error: Authentication failed
```

**Fix:**
1. Verify `EMBEDDING_HMAC_SECRET` is identical on Railway and RunPod
2. Check for whitespace/newline issues in secret
3. Regenerate secret and update both sides

### Timeout Errors

**Symptom:**
```
ERROR: RunPod timeout: Request timeout after 60.0s
```

**Fix:**
1. Check RunPod endpoint status (may be cold starting)
2. Increase `RUNPOD_TIMEOUT_S` to 90 or 120 seconds
3. Set min workers to 1 to avoid cold starts
4. Check RunPod logs for worker errors

### Image Download Failures

**Symptom:**
```
ERROR: RunPod error: Image download failed: Timeout
```

**Fix:**
1. Verify Supabase Storage is publicly accessible
2. Check signed URL expiration (default: 5 minutes)
3. Increase `IMAGE_DOWNLOAD_TIMEOUT` in RunPod env vars
4. Verify network connectivity from RunPod to Supabase

### Embedding Dimension Mismatch

**Symptom:**
```
ERROR: Unexpected embedding dimension: 768 (expected 512)
```

**Fix:**
1. Verify `CLIP_MODEL_NAME` is `ViT-B-32` (512-dim) on both sides
2. Check RunPod logs for model loading errors
3. Rebuild RunPod image if model was changed

### RunPod Endpoint Not Responding

**Symptom:**
```
ERROR: Connection error: Failed to connect to api.runpod.ai
```

**Fix:**
1. Check RunPod status page: https://status.runpod.io
2. Verify `RUNPOD_API_KEY` and `RUNPOD_CLIP_ENDPOINT_ID` are correct
3. Check Railway worker has internet access
4. Test endpoint with curl (see Smoke Test section)

## Cost Analysis

### RunPod GPU Costs

**RTX 4090:**
- Hourly rate: ~$0.50/hr
- Per-request cost: ~$0.000007 (assuming 50ms inference)
- 1000 scenes: ~$0.007 (~0.7 cents)

**A100:**
- Hourly rate: ~$1.50/hr
- Per-request cost: ~$0.000021 (assuming 50ms inference)
- 1000 scenes: ~$0.021 (~2 cents)

### Railway Memory Savings

**Before (local CLIP):**
- CLIP model: ~500MB RAM
- Inference overhead: ~200MB RAM
- **Total:** ~700MB RAM saved per worker

**After (RunPod):**
- CLIP model: 0MB (offloaded)
- Inference overhead: 0MB
- **Total:** ~700MB RAM freed

### Performance Improvements

| Metric | Local (CPU) | RunPod (GPU) | Improvement |
|--------|-------------|--------------|-------------|
| Cold start | N/A (always loaded) | 5-10s | N/A |
| Warm request | 2000-5000ms | 30-150ms | 10-50x faster |
| Throughput | ~0.2-0.5 scenes/sec | ~5-10 scenes/sec | 20-50x faster |
| Memory usage | 700MB | 0MB | 100% reduction |

## Monitoring

### RunPod Dashboard

Monitor in https://www.runpod.io/console/serverless:
- Request rate
- Error rate
- Average latency (p50, p95, p99)
- Worker scaling (active/idle)
- GPU utilization
- Cost per day

### Railway Logs

Look for these log patterns:

**Success:**
```
Scene 5: Generating CLIP embedding from best frame (backend=runpod)
Scene 5: RunPod CLIP embedding generated (dim=512, inference=45.2ms, total=234.5ms)
```

**Failure (with fallback):**
```
Scene 5: RunPod timeout: Request timeout after 60.0s
Scene 5: CLIP embedding failed: Timeout
```

### Database Monitoring

```sql
-- Count embeddings by backend
SELECT
  visual_clip_metadata->>'backend' as backend,
  COUNT(*) as count,
  AVG((visual_clip_metadata->>'inference_time_ms')::float) as avg_inference_ms
FROM video_scenes
WHERE embedding_visual_clip IS NOT NULL
GROUP BY backend;

-- Expected output:
-- backend | count | avg_inference_ms
-- runpod  | 1523  | 47.3
```

## Backfilling Existing Videos

If you want to regenerate CLIP embeddings for existing videos using RunPod:

```bash
cd services/worker

# Backfill all scenes without CLIP embeddings
python -m src.scripts.backfill_clip_visual_embeddings \
  --batch-size 50 \
  --clip-timeout 60.0

# Regenerate all CLIP embeddings (force mode)
python -m src.scripts.backfill_clip_visual_embeddings \
  --batch-size 50 \
  --clip-timeout 60.0 \
  --force-regenerate

# Dry run to see what would be processed
python -m src.scripts.backfill_clip_visual_embeddings \
  --dry-run
```

**Note:** The backfill script will automatically use the configured backend (RunPod or local).

## Security Considerations

### HMAC Authentication

- **Purpose:** Prevents unauthorized access to RunPod endpoint
- **Mechanism:** HMAC-SHA256 signature of `image_url|timestamp`
- **Time window:** 120 seconds (prevents replay attacks)
- **Secret strength:** 64-character hex (256-bit entropy)

### Signed URLs

- **Purpose:** Temporary access to thumbnails in Supabase Storage
- **Expiration:** 5 minutes (enough for RunPod, short-lived)
- **Scope:** Read-only access to specific file
- **Revocation:** Automatic after expiration

### Best Practices

1. **Rotate secrets regularly:** Update `EMBEDDING_HMAC_SECRET` every 90 days
2. **Monitor failed auth:** Set up alerts for authentication failures
3. **Restrict RunPod access:** Use RunPod's IP allowlist if available
4. **Audit logs:** Review RunPod request logs monthly

## Performance Tuning

### Cold Start Optimization

**Problem:** First request after idle period is slow (5-10s)

**Solutions:**
1. Set min workers to 1 (keeps endpoint warm)
   - Trade-off: Higher cost (~$0.50/hr continuous)
   - Use for production with consistent traffic

2. Pre-warm endpoint before batch processing:
   ```bash
   # Send a test request to wake up workers
   curl -X POST https://api.runpod.ai/v2/${ENDPOINT_ID}/runsync \
     -H "Authorization: Bearer ${API_KEY}" \
     -d '{"input": {"image_url": "..."}}'
   ```

### Concurrency Tuning

**Railway Worker Side:**

```bash
# Adjust max concurrent scene processing
MAX_SCENE_WORKERS=5  # Process 5 scenes in parallel

# Each scene may call RunPod CLIP endpoint
# Total RunPod concurrency = MAX_SCENE_WORKERS
```

**RunPod Side:**

```
Max Workers = 5  # Allow 5 concurrent GPU workers
```

Match RunPod max workers to Railway concurrency for optimal throughput.

### GPU Selection

| GPU | Cost/hr | Inference | Throughput | Best For |
|-----|---------|-----------|------------|----------|
| RTX 4090 | $0.50 | 30-50ms | ~20 req/sec | Development, low volume |
| A100 | $1.50 | 20-40ms | ~25 req/sec | Production, high volume |
| L40S | $1.00 | 25-45ms | ~22 req/sec | Balanced cost/performance |

**Recommendation:** Start with RTX 4090, upgrade to A100 if you see GPU bottlenecks.

## Future Enhancements

### Possible Improvements

1. **Batch Processing:**
   - Send multiple images in one RunPod request
   - Reduce network overhead
   - Requires handler.py changes

2. **Embedding Cache:**
   - Cache embeddings by image hash
   - Avoid re-processing identical frames
   - Requires cache infrastructure (Redis)

3. **Multi-Model Support:**
   - Deploy different CLIP models (ViT-L-14, etc.)
   - Allow per-request model selection
   - Higher dimensions for better accuracy

4. **Auto-Scaling Rules:**
   - Scale RunPod workers based on queue depth
   - Integrate with Railway metrics
   - Cost optimization

## Support

### Documentation

- RunPod Docs: https://docs.runpod.io/serverless/overview
- OpenCLIP: https://github.com/mlfoundations/open_clip
- Heimdex Internal: See `services/clip-runpod-worker/README.md`

### Getting Help

1. Check RunPod logs in dashboard
2. Check Railway worker logs
3. Run smoke test script
4. Review this migration guide
5. Contact team lead if issues persist

## Migration Checklist

- [ ] Build and push RunPod Docker image
- [ ] Create RunPod endpoint with correct settings
- [ ] Generate strong HMAC secret
- [ ] Configure Railway environment variables
- [ ] Deploy Railway worker
- [ ] Run smoke test script
- [ ] Process test video end-to-end
- [ ] Verify embeddings in database
- [ ] Monitor RunPod dashboard for 24 hours
- [ ] Set up cost alerts in RunPod
- [ ] Document any issues or adjustments
- [ ] Update team on migration completion

## Conclusion

The CLIP RunPod migration improves performance by 10-50x, reduces Railway memory usage by ~700MB, and enables cost-effective GPU acceleration with auto-scaling. The migration is designed to be reversible with minimal downtime through the `CLIP_INFERENCE_BACKEND` configuration flag.

For questions or issues, refer to the troubleshooting section or contact the team lead.
