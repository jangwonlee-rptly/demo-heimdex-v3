# CLIP Visual Embeddings

## Overview

This document describes the CPU-friendly CLIP visual embedding implementation for Heimdex video scene indexing. CLIP (Contrastive Language-Image Pre-training) embeddings enable true visual similarity search by encoding images into a semantic vector space.

## Why CLIP Visual Embeddings?

### Problem with Text-Only Embeddings

The existing system generates embeddings from:
- **Transcript embeddings**: Text from speech-to-text (Whisper)
- **Visual embeddings**: Text descriptions from GPT-4V vision API
- **Summary embeddings**: Text summaries of scenes

All embeddings are **text-based** (via `text-embedding-3-small`), even the "visual" channel. This has limitations:
- Visual queries like "show me red cars" require GPT-4V to generate text descriptions first
- Subtle visual patterns not captured in text descriptions are lost
- Dependence on expensive vision API calls for visual understanding

### Solution: CLIP Image Encoder

CLIP provides a **true visual embedding** by encoding raw images directly:
- **Direct image-to-vector**: No intermediate text description needed
- **Visual-semantic alignment**: Trained on image-text pairs, captures visual patterns
- **Efficient**: Single forward pass through vision encoder (no API calls)
- **CPU-friendly**: Optimized for Railway deployment without GPU requirement

## Architecture

### Model Choice

**OpenCLIP ViT-B-32**:
- **Embedding dimension**: 512 (vs 1536 for text embeddings)
- **Model size**: ~350MB weights
- **CPU inference**: ~100-200ms per image on modern CPU
- **Quality**: Trained on LAION-2B dataset, strong visual-semantic alignment

Alternative models available:
- `ViT-B-16`: Higher quality, slower (768 dim)
- `ViT-L-14`: Best quality, much slower (768 dim)

### Integration Points

1. **Scene Processing** (`sidecar_builder.py:771-805`)
   - After frame quality ranking, encode best frame with CLIP
   - Store embedding and metadata in `SceneSidecar`
   - Graceful degradation: CLIP failure doesn't break pipeline

2. **Database Storage** (`database.py:383-386`)
   - `embedding_visual_clip` column: `vector(512)` with HNSW index
   - `visual_clip_metadata` column: JSONB with generation details

3. **Search** (`infra/migrations/017_add_clip_visual_embeddings.sql:59-100`)
   - RPC function: `search_scenes_by_visual_clip_embedding()`
   - Cosine similarity ranking (1 - cosine_distance)
   - Tenant-safe filtering via `owner_id`

## Configuration

All settings are environment variables with sensible defaults:

```bash
# Feature flag (default: false for safe rollout)
CLIP_ENABLED=false

# Model configuration
CLIP_MODEL_NAME=ViT-B-32        # Model architecture
CLIP_PRETRAINED=openai          # Pretrained weights source
CLIP_DEVICE=cpu                 # "cpu" or "cuda"
CLIP_NORMALIZE=true             # L2-normalize embeddings

# Performance tuning
CLIP_TIMEOUT_S=2.0              # Per-scene timeout (prevent hangs)
CLIP_MAX_IMAGE_SIZE=224         # Resize large images (memory safety)
CLIP_CPU_THREADS=null           # Optional: limit torch CPU threads
CLIP_CACHE_DIR=/tmp/clip_cache  # Model weight cache directory

# Debugging
CLIP_DEBUG_LOG=false            # Verbose logging for troubleshooting
```

## Railway Deployment

### Memory Requirements

**Base worker**: ~500MB RAM
**With CLIP model loaded**: ~500MB (model) + ~200MB (inference) = ~1.2GB total

**Recommendation**: Provision 2GB RAM per worker instance for safety margin.

### CPU Performance

**Inference time** (ViT-B-32 on 2 vCPU):
- Best-case: 100-150ms per scene
- Worst-case: 200-300ms per scene
- Timeout: 2.0s (configurable)

**Model loading time**:
- Cold start (download): 10-30s (first deployment only)
- Warm start (cached): 2-5s
- Lazy loading: Model loaded only when first scene needs embedding

### Cache Strategy

Model weights are cached to `/tmp/clip_cache` by default:
- **Railway ephemeral storage**: Cache survives for container lifetime
- **Cold starts**: Model re-downloaded on new container (acceptable for serverless)
- **Persistent volumes** (future): Mount `/tmp/clip_cache` for faster restarts

### Graceful Degradation

CLIP failures never break video processing:
- **Model load failure**: Logs error, embeddings set to NULL
- **Inference timeout**: Logs warning, embeddings set to NULL
- **Image read error**: Logs error, embeddings set to NULL
- **Pipeline continues**: Transcript and text embeddings still work

## Usage

### Enabling CLIP Embeddings

1. **Apply database migration**:
   ```bash
   psql $DATABASE_URL < infra/migrations/017_add_clip_visual_embeddings.sql
   ```

2. **Enable feature flag**:
   ```bash
   railway variables set CLIP_ENABLED=true
   ```

3. **Deploy worker service**:
   ```bash
   railway up --service worker
   ```

4. **Monitor logs**:
   ```
   Scene 12: Generating CLIP embedding from best frame
   Scene 12: CLIP embedding created (dim=512, time=145.2ms)
   ```

### Searching with CLIP Embeddings

**From API** (future implementation):
```typescript
// Option 1: Upload image and search
const results = await searchByImage({
  imageFile: uploadedFile,
  matchThreshold: 0.7,
  matchCount: 20
});

// Option 2: Use existing scene as query
const results = await searchSimilarScenes({
  sceneId: "uuid-of-reference-scene",
  matchThreshold: 0.7,
  matchCount: 20
});
```

**Direct SQL** (for testing):
```sql
SELECT * FROM search_scenes_by_visual_clip_embedding(
  query_embedding := '[0.1, 0.2, ..., 0.5]'::vector(512),
  match_threshold := 0.7,
  match_count := 20,
  filter_user_id := 'user-uuid'
);
```

## Metadata Structure

Each CLIP embedding includes rich metadata in JSONB:

```json
{
  "model_name": "ViT-B-32",
  "pretrained": "openai",
  "embed_dim": 512,
  "normalized": true,
  "device": "cpu",
  "frame_path": "scene_12_frame_0.jpg",
  "frame_quality": {
    "quality_score": 0.82
  },
  "inference_time_ms": 145.2,
  "created_at": "2025-01-15T12:34:56Z",
  "error": null
}
```

**On failure**:
```json
{
  "model_name": "ViT-B-32",
  "pretrained": "openai",
  "embed_dim": 512,
  "normalized": true,
  "device": "cpu",
  "frame_path": "scene_12_frame_0.jpg",
  "frame_quality": null,
  "inference_time_ms": null,
  "created_at": "2025-01-15T12:34:56Z",
  "error": "Timeout after 2.0s"
}
```

## Benefits

1. **True Visual Search**: Query by images, not just text descriptions
2. **Cost Efficiency**: No GPT-4V API calls for visual encoding
3. **Offline Capability**: Embeddings generated without external APIs
4. **Cross-Lingual**: Visual semantics transcend language barriers
5. **Subtle Patterns**: Captures colors, textures, compositions not in text

## Performance Optimization

### Current Optimization

- **Lazy model loading**: Model loaded only when first needed
- **Singleton pattern**: One model instance per worker process
- **Timeout protection**: Per-scene timeout prevents hanging
- **Memory safety**: Image resizing prevents OOM on large images
- **L2 normalization**: Enables dot-product similarity (faster than cosine)

### Future Optimizations

1. **Batch inference**: Process multiple scenes together (10x faster)
2. **Model quantization**: INT8 quantization for 4x smaller model
3. **Frame caching**: Reuse embeddings for identical frames
4. **GPU support**: Optional CUDA for 100x faster inference
5. **ONNX export**: More efficient runtime (50% faster on CPU)

## Monitoring and Debugging

### Key Metrics to Track

1. **CLIP availability**: `% scenes with embedding_visual_clip IS NOT NULL`
2. **Inference latency**: `AVG(visual_clip_metadata->>'inference_time_ms')`
3. **Failure rate**: `COUNT(*) WHERE visual_clip_metadata->>'error' IS NOT NULL`
4. **Timeout rate**: `COUNT(*) WHERE visual_clip_metadata->>'error' LIKE '%Timeout%'`

### Debug Logs

Enable verbose logging:
```bash
CLIP_DEBUG_LOG=true
```

Expected output:
```
Loading CLIP model: ViT-B-32 (pretrained=openai, device=cpu)
CLIP model loaded successfully: ViT-B-32 (embed_dim=512, device=cpu, load_time=2345.6ms, cache_dir=/tmp/clip_cache)
Scene 12: Generating CLIP embedding from best frame
CLIP embedding created: scene_12_frame_0.jpg, dim=512, time=145.2ms, norm=1.0000
```

### Common Issues

**Issue: Model download timeout**
- **Symptom**: "Failed to load CLIP model" on first deployment
- **Cause**: Railway network timeout during model download
- **Solution**: Increase timeout or pre-bake model into Docker image

**Issue: High memory usage**
- **Symptom**: OOM errors, worker restarts
- **Cause**: Multiple large images in memory
- **Solution**: Reduce `CLIP_MAX_IMAGE_SIZE` or provision more RAM

**Issue: Slow inference**
- **Symptom**: Frequent timeouts, `inference_time_ms > 500`
- **Cause**: CPU contention or underpowered instance
- **Solution**: Increase `CLIP_TIMEOUT_S` or provision more vCPUs

## Backward Compatibility

- **Existing scenes**: `embedding_visual_clip` is NULL (expected)
- **Search**: Falls back to text embeddings if CLIP embeddings unavailable
- **Reprocessing**: Optional backfill script (not included) to generate CLIP embeddings for old videos

## Testing

Run unit tests:
```bash
docker compose -f docker-compose.test.yml run --rm worker-test pytest tests/test_clip_embedder.py -v
```

Expected output:
```
tests/test_clip_embedder.py::TestClipEmbedderDisabled::test_disabled_returns_none PASSED
tests/test_clip_embedder.py::TestClipEmbedderSingleton::test_singleton_returns_same_instance PASSED
tests/test_clip_embedder.py::TestClipEmbedderModelLoading::test_model_loading_success PASSED
tests/test_clip_embedder.py::TestClipEmbedderEmbeddingGeneration::test_embedding_generation_success PASSED
... (15 tests total)
```

## Future Enhancements

1. **Multi-frame pooling**: Average embeddings from top-3 frames per scene
2. **CLIP text encoder**: Enable text-to-image search ("show me sunsets")
3. **Temporal embeddings**: Combine CLIP with motion features for video understanding
4. **Cross-modal fusion**: Combine CLIP visual + text embeddings for hybrid search
5. **Fine-tuning**: Domain-specific fine-tuning on Heimdex dataset

## References

- **OpenCLIP**: https://github.com/mlfoundations/open_clip
- **CLIP paper**: https://arxiv.org/abs/2103.00020
- **Model zoo**: https://github.com/mlfoundations/open_clip/blob/main/docs/openclip_results.csv
- **LAION dataset**: https://laion.ai/blog/laion-5b/

## Migration Path

### Phase 1: Soft Launch (Current)
- CLIP disabled by default (`CLIP_ENABLED=false`)
- Deploy to production, monitor stability
- Enable for internal testing videos

### Phase 2: Gradual Rollout
- Enable CLIP for subset of users (A/B test)
- Monitor memory, CPU, error rates
- Tune timeouts and thresholds

### Phase 3: Full Deployment
- Enable CLIP for all new videos
- Optional: Backfill embeddings for high-value videos
- Integrate visual search into API

### Phase 4: Optimization
- Implement batch inference
- Add GPU support for power users
- Fine-tune model on Heimdex data
