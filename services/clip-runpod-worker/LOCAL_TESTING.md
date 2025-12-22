# Local Testing Guide for CLIP RunPod Worker

This document provides step-by-step instructions for testing the CLIP worker locally before deploying to RunPod.

## Prerequisites

- Docker installed and running
- Internet connection (for downloading test images)

## Build the Image

```bash
cd services/clip-runpod-worker

# Build with no cache to ensure fresh dependencies
docker build --no-cache -t clip-worker:latest .
```

**Expected output:**
- Python 3.10 installation
- CUDA 11.8 torch wheel installation
- CLIP model pre-download
- "Model downloaded successfully" message

## Test 1: Local Smoke Test (No GPU Required)

This runs on CPU and verifies the complete inference pipeline:

```bash
docker run --rm -it clip-worker:latest
```

**Expected output:**
```
============================================================
RunPod CLIP Worker - Startup Diagnostics
============================================================
torch version: 2.1.2+cu118
torch.version.cuda: 11.8
torch.cuda.is_available(): False
============================================================
Initializing CLIP model...
Using device: cpu
CLIP model loaded successfully: ViT-B-32 (openai) in X.XXs on cpu
============================================================
LOCAL SMOKE TEST MODE
============================================================
✓ Model loaded: ViT-B-32 (openai) on cpu
Test image URL: https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=512...
Downloading test image...
✓ Image downloaded in X.XXXs: (512, 341)
Generating embedding...
✓ Embedding generated in X.XXXs
  Dimension: 512
  First 5 values: [0.123, -0.456, ...]
  L2 norm: 1.0000
============================================================
✅ SMOKE TEST PASSED
============================================================
```

Container should exit with code 0.

## Test 2: Custom Test Image

Test with your own image URL:

```bash
docker run --rm -it \
  -e SMOKE_TEST_IMAGE_URL="https://example.com/your-test-image.jpg" \
  clip-worker:latest
```

## Test 3: Verify CUDA Torch Installation

Check that CUDA wheels are installed correctly:

```bash
docker run --rm -it \
  --entrypoint python3.10 \
  clip-worker:latest \
  -c "import torch; print(f'torch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}')"
```

**Expected output:**
```
torch: 2.1.2+cu118
CUDA available: False  # (or True if you have GPU)
CUDA version: 11.8
```

The `+cu118` suffix confirms CUDA 11.8 wheels are installed.

## Test 4: Verify Handler Import

Test that the handler module imports without errors:

```bash
docker run --rm -it \
  --entrypoint python3.10 \
  clip-worker:latest \
  -c "import handler; print('✓ Handler imported successfully')"
```

**Expected output:**
```
============================================================
RunPod CLIP Worker - Startup Diagnostics
============================================================
[... diagnostics ...]
Initializing CLIP model...
CLIP model loaded successfully...
✓ Handler imported successfully
```

## Test 5: Interactive Shell (Debugging)

Drop into an interactive shell to explore the container:

```bash
docker run --rm -it \
  --entrypoint /bin/bash \
  clip-worker:latest
```

Then inside the container:
```bash
# Check Python version
python3.10 --version

# Check installed packages
python3.10 -m pip list | grep -E "torch|clip|runpod|numpy"

# Check cache directories
ls -la /app/.cache/huggingface/
ls -la /app/.cache/torch/

# Run handler manually
python3.10 /app/handler.py
```

## Test 6: GPU Test (If Available)

If you have an NVIDIA GPU and nvidia-docker installed:

```bash
docker run --rm -it --gpus all clip-worker:latest
```

**Expected output should show:**
```
torch.cuda.is_available(): True
CUDA device count: 1
CUDA device name: <your GPU name>
Using device: cuda
```

## Common Issues and Solutions

### Issue: "test_input.json not found, exiting"

**Cause:** You're running an old version of the handler.

**Solution:** Rebuild with `--no-cache`:
```bash
docker build --no-cache -t clip-worker:latest .
```

### Issue: NumPy version warnings

**Cause:** NumPy 2.x installed instead of 1.x.

**Solution:** Check requirements.txt contains `numpy<2.0.0` and rebuild:
```bash
cat requirements.txt | grep numpy  # should show: numpy<2.0.0
docker build --no-cache -t clip-worker:latest .
```

### Issue: Container crashes immediately

**Cause:** Model loading failed or missing dependency.

**Solution:** Check logs with verbose output:
```bash
docker run --rm -it clip-worker:latest 2>&1 | tee output.log
```

Look for traceback in output.log showing the exact error.

### Issue: Slow model loading

**Cause:** CLIP model not cached at build time.

**Solution:** Verify model was downloaded during build:
```bash
# During build, you should see:
# Pre-downloading CLIP model...
# Model downloaded successfully

# Check cache exists in image:
docker run --rm -it --entrypoint ls clip-worker:latest -la /app/.cache/
```

## Testing Checklist

Before deploying to RunPod, verify:

- [ ] Image builds successfully without errors
- [ ] Local smoke test passes (exit code 0)
- [ ] Torch version shows `2.1.2+cu118` (CUDA wheels)
- [ ] Handler imports without errors
- [ ] CLIP model loads successfully
- [ ] Embedding dimension is 512
- [ ] L2 norm is ~1.0 (normalized)
- [ ] No "test_input.json" warning

## Next Steps

Once local testing passes, proceed to:

1. **Push to registry:**
   ```bash
   docker tag clip-worker:latest your-dockerhub-username/clip-worker:latest
   docker push your-dockerhub-username/clip-worker:latest
   ```

2. **Deploy to RunPod:**
   - Use Docker Registry deployment
   - Set environment variable: `EMBEDDING_HMAC_SECRET=your-secret`
   - GPU: RTX 3090 or better
   - Min Workers: 0 (for testing), 1 (for production)
   - Execution Timeout: 120 seconds

3. **Test RunPod endpoint:**
   - See `../worker/src/scripts/test_runpod_clip.py` for end-to-end test
