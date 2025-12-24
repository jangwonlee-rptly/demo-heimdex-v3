# CLIP Pod Deployment Checklist

Use this checklist to deploy the CLIP Pod service step-by-step.

---

## Pre-Deployment

### 1. Build Docker Image

```bash
cd services/clip-runpod-worker

# Build
docker build -f Dockerfile.pod -t YOUR_DOCKERHUB_USERNAME/clip-pod-worker:2.0 .

# Test locally (optional)
docker run --rm -p 8000:8000 \
  -e EMBEDDING_HMAC_SECRET=test-secret \
  -e ALLOW_INSECURE_AUTH=1 \
  YOUR_DOCKERHUB_USERNAME/clip-pod-worker:2.0

# In another terminal, test health
curl http://localhost:8000/health
```

**Expected Output:**
```json
{
  "status": "ok",
  "model_name": "ViT-B-32",
  "device": "cpu",
  "torch_version": "2.5.1",
  ...
}
```

- [ ] Docker build succeeds
- [ ] Local health check returns 200

### 2. Push to Registry

```bash
docker login
docker push YOUR_DOCKERHUB_USERNAME/clip-pod-worker:2.0
```

- [ ] Image pushed to Docker Hub

---

## RunPod Pod Creation

### 3. Create Pod on RunPod

Go to: https://www.runpod.io/console/pods

**Configuration:**

1. **GPU Selection:**
   - [ ] Selected GPU: RTX 4090 (recommended) or A100
   - [ ] GPU Count: 1

2. **Container Image:**
   - [ ] Image: `YOUR_DOCKERHUB_USERNAME/clip-pod-worker:2.0`
   - [ ] Container Disk: 20GB

3. **Expose HTTP Ports:**
   - [ ] HTTP Port: `8000`
   - [ ] ✅ HTTP Service enabled

4. **Environment Variables:**
   ```
   EMBEDDING_HMAC_SECRET=<COPY_THIS_SECRET_FOR_LATER>
   LOG_LEVEL=INFO
   ```

   **Generate secret:**
   ```bash
   openssl rand -hex 32
   ```

   - [ ] Generated and set `EMBEDDING_HMAC_SECRET`
   - [ ] Copied secret to secure location

5. **Deploy:**
   - [ ] Click "Deploy"
   - [ ] Wait for Pod to start (~2-3 minutes)

### 4. Verify Pod

**Get Proxy URL:**
- [ ] Copied Pod Proxy URL (format: `https://<pod-id>-8000.proxy.runpod.net`)

**Test Health:**
```bash
curl https://<pod-id>-8000.proxy.runpod.net/health
```

**Expected:**
```json
{
  "status": "ok",
  "model_name": "ViT-B-32",
  "device": "cuda",
  "cuda_version": "12.4",
  ...
}
```

- [ ] Health check returns 200
- [ ] Device is "cuda" (not "cpu")
- [ ] Model loaded successfully

---

## Worker Client Configuration

### 5. Update Railway Environment Variables

Go to: Railway → heimdex-worker → Variables

**Add/Update:**
```bash
CLIP_INFERENCE_BACKEND=runpod_pod
CLIP_POD_BASE_URL=https://<pod-id>-8000.proxy.runpod.net
EMBEDDING_HMAC_SECRET=<same-secret-as-pod>
```

- [ ] Set `CLIP_INFERENCE_BACKEND=runpod_pod`
- [ ] Set `CLIP_POD_BASE_URL` (Pod Proxy URL)
- [ ] Set `EMBEDDING_HMAC_SECRET` (same as Pod)
- [ ] Saved changes
- [ ] Railway redeployed worker

### 6. Verify Worker Logs

Check Railway logs:

**Look for:**
```
[INFO] RunPod Pod CLIP client initialized successfully
```

- [ ] Worker started successfully
- [ ] No CLIP configuration errors

---

## Integration Testing

### 7. Test Single Image Embedding

```bash
export CLIP_POD_BASE_URL=https://<pod-id>-8000.proxy.runpod.net
export EMBEDDING_HMAC_SECRET=<your-secret>

python3 << 'EOF'
import hashlib
import hmac
import time
import requests
import os

base_url = os.environ['CLIP_POD_BASE_URL']
secret = os.environ['EMBEDDING_HMAC_SECRET']

image_url = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=512"
ts = int(time.time())

canonical = f"POST|/v1/embed/image|{image_url}"
message = f"{canonical}|{ts}"
sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

r = requests.post(
    f"{base_url}/v1/embed/image",
    json={
        "image_url": image_url,
        "request_id": "deploy-test-1",
        "normalize": True,
        "auth": {"ts": ts, "sig": sig}
    },
    timeout=30
)

print(f"Status: {r.status_code}")
data = r.json()
print(f"Dimension: {data['dim']}")
print(f"Device: {data['device']}")
print(f"Inference time: {data['timings']['inference_ms']}ms")
print(f"First 5 values: {data['embedding'][:5]}")

assert r.status_code == 200
assert data['dim'] == 512
assert data['device'] == 'cuda'
print("\n✅ Single image embedding test PASSED")
EOF
```

- [ ] Test returns 200
- [ ] Embedding has 512 dimensions
- [ ] Device is "cuda"
- [ ] Inference time < 200ms

### 8. Test Batch Embedding

```bash
python3 << 'EOF'
import hashlib
import hmac
import time
import requests
import os

base_url = os.environ['CLIP_POD_BASE_URL']
secret = os.environ['EMBEDDING_HMAC_SECRET']

urls = [
    "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=512",
    "https://images.unsplash.com/photo-1472214103451-9374bd1c798e?w=512",
]

ts = int(time.time())
items = []

for i, url in enumerate(urls):
    canonical = f"POST|/v1/embed/image-batch|{url}"
    message = f"{canonical}|{ts}"
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    items.append({
        "image_url": url,
        "request_id": f"batch-test-{i}",
        "normalize": True,
        "auth": {"ts": ts, "sig": sig}
    })

r = requests.post(
    f"{base_url}/v1/embed/image-batch",
    json={"items": items},
    timeout=60
)

print(f"Status: {r.status_code}")
data = r.json()
print(f"Batch size: {len(items)}")
print(f"Results: {len(data['results'])}")
print(f"Total time: {data['batch_timings']['total_ms']}ms")
print(f"Inference time: {data['batch_timings']['total_inference_ms']}ms")

assert r.status_code == 200
assert len(data['results']) == len(items)
assert all('embedding' in result for result in data['results'])
print("\n✅ Batch embedding test PASSED")
EOF
```

- [ ] Batch test returns 200
- [ ] All items have embeddings
- [ ] Batch inference time < 300ms

### 9. Test Text Embedding

```bash
python3 << 'EOF'
import hashlib
import hmac
import time
import requests
import os

base_url = os.environ['CLIP_POD_BASE_URL']
secret = os.environ['EMBEDDING_HMAC_SECRET']

text = "a person walking in the rain"
ts = int(time.time())

text_hash = hashlib.sha256(text.encode()).hexdigest()
canonical = f"POST|/v1/embed/text|{text_hash}"
message = f"{canonical}|{ts}"
sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

r = requests.post(
    f"{base_url}/v1/embed/text",
    json={
        "text": text,
        "request_id": "text-test-1",
        "normalize": True,
        "auth": {"ts": ts, "sig": sig}
    },
    timeout=30
)

print(f"Status: {r.status_code}")
data = r.json()
print(f"Dimension: {data['dim']}")
print(f"Inference time: {data['timings']['inference_ms']}ms")
print(f"First 5 values: {data['embedding'][:5]}")

assert r.status_code == 200
assert data['dim'] == 512
print("\n✅ Text embedding test PASSED")
EOF
```

- [ ] Text test returns 200
- [ ] Embedding has 512 dimensions
- [ ] Inference time < 50ms

---

## End-to-End Testing

### 10. Process Test Video

```bash
# In heimdex-worker, trigger a video processing job
# Check logs for CLIP embedding generation

# Expected in logs:
# "RunPod Pod request completed: status=200"
# "CLIP embedding generated successfully"
```

- [ ] Video processing completes
- [ ] CLIP embeddings generated
- [ ] No authentication errors
- [ ] No timeout errors

---

## Monitoring

### 11. Set Up Monitoring

**Pod Logs (RunPod Console):**
- [ ] No error logs
- [ ] Request logs show successful embeddings
- [ ] GPU utilization visible

**Worker Logs (Railway):**
- [ ] CLIP client initialized
- [ ] Embeddings generated successfully
- [ ] Latency within acceptable range

**Metrics to Track:**
- [ ] Request rate (requests/second)
- [ ] Latency (p50, p95, p99)
- [ ] Error rate
- [ ] GPU utilization

---

## Rollback (If Needed)

### If Issues Occur:

**Option 1: Revert to Serverless**
```bash
# In Railway
CLIP_INFERENCE_BACKEND=runpod_serverless
RUNPOD_API_KEY=<your-api-key>
RUNPOD_CLIP_ENDPOINT_ID=<endpoint-id>
```

**Option 2: Disable CLIP**
```bash
CLIP_INFERENCE_BACKEND=off
```

- [ ] Rollback plan tested and ready

---

## Post-Deployment

### 12. Cleanup

- [ ] Remove test environment variables
- [ ] Document Pod URL and secret in secure location
- [ ] Update team documentation
- [ ] Schedule cost review (1 week)
- [ ] Schedule performance review (1 week)

---

## Sign-Off

**Deployment Date:** __________________

**Deployed By:** __________________

**Pod URL:** __________________

**Environment:**
- [ ] Railway worker configured
- [ ] RunPod Pod running
- [ ] Tests passing
- [ ] Monitoring enabled

**Status:**
- [ ] ✅ Deployment successful
- [ ] ⚠️ Partial success (issues documented below)
- [ ] ❌ Rolled back

**Notes:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

## Quick Reference

**Pod Proxy URL:**
```
https://<pod-id>-8000.proxy.runpod.net
```

**Railway Environment:**
```bash
CLIP_INFERENCE_BACKEND=runpod_pod
CLIP_POD_BASE_URL=https://<pod-id>-8000.proxy.runpod.net
EMBEDDING_HMAC_SECRET=<secret>
```

**Health Check:**
```bash
curl https://<pod-id>-8000.proxy.runpod.net/health
```

**Logs:**
- Pod: RunPod Console → Pods → Logs
- Worker: Railway → Deployments → Logs
