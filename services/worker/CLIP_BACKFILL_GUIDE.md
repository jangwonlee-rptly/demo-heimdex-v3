# CLIP Visual Embeddings Backfill Guide

## Overview

This guide explains how to backfill CLIP visual embeddings for existing video scenes that were processed before CLIP support was added.

## Prerequisites

1. **Database migration applied**: Migration `017_add_clip_visual_embeddings.sql` must be applied
2. **CLIP enabled**: Set `CLIP_ENABLED=true` in environment variables
3. **Worker deployed**: Worker service with CLIP dependencies deployed
4. **Scenes with thumbnails**: Only scenes with `thumbnail_url` will be processed

## Backfill Script

**Location**: `services/worker/src/scripts/backfill_clip_visual_embeddings.py`

### Features

- ✅ **Checkpoint/Resume**: Automatically saves progress every 10 scenes
- ✅ **Rate limiting**: Configurable delay between scenes (default: 0.5s)
- ✅ **Batch processing**: Processes scenes in batches (default: 50)
- ✅ **Graceful degradation**: CLIP failures are recorded but don't stop processing
- ✅ **Dry run mode**: Preview what will be done without changes
- ✅ **Progress tracking**: Detailed logging with counts
- ✅ **Filtering**: Process specific video or user
- ✅ **Thumbnail download**: Automatically downloads thumbnails from Supabase Storage
- ✅ **Cleanup**: Temporary files are cleaned up after processing

### Usage

#### Basic Usage (Dry Run First)

```bash
# Dry run to see what will be processed
python -m src.scripts.backfill_clip_visual_embeddings --dry-run --max-scenes 10

# Run backfill for first 100 scenes
python -m src.scripts.backfill_clip_visual_embeddings --max-scenes 100

# Run backfill for all scenes (unlimited)
python -m src.scripts.backfill_clip_visual_embeddings
```

#### Advanced Options

```bash
# Process specific video only
python -m src.scripts.backfill_clip_visual_embeddings \
  --video-id "12345678-1234-1234-1234-123456789012"

# Process with custom batch size and delay
python -m src.scripts.backfill_clip_visual_embeddings \
  --batch-size 25 \
  --processing-delay 1.0 \
  --clip-timeout 10.0

# Force regenerate even if embeddings exist
python -m src.scripts.backfill_clip_visual_embeddings \
  --force-regenerate \
  --max-scenes 50

# Resume from checkpoint
# (Automatically resumes from .backfill_clip_checkpoint.json if exists)
python -m src.scripts.backfill_clip_visual_embeddings
```

### Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--batch-size` | int | 50 | Number of scenes to fetch per batch |
| `--max-scenes` | int | None | Maximum scenes to process (unlimited if not set) |
| `--processing-delay` | float | 0.5 | Delay between scenes in seconds (CPU breathing room) |
| `--checkpoint-file` | str | `.backfill_clip_checkpoint.json` | Path to checkpoint file |
| `--force-regenerate` | flag | False | Regenerate embeddings even if already present |
| `--dry-run` | flag | False | Preview without making changes |
| `--video-id` | UUID | None | Process only scenes from specific video |
| `--user-id` | UUID | None | Process only scenes from specific user |
| `--clip-timeout` | float | 5.0 | CLIP inference timeout in seconds |

## Running in Docker

### Option 1: Using Docker Compose (Recommended)

```bash
# Build worker image with CLIP dependencies
docker compose build worker

# Run backfill (dry run)
docker compose run --rm worker python -m src.scripts.backfill_clip_visual_embeddings --dry-run --max-scenes 10

# Run actual backfill
docker compose run --rm worker python -m src.scripts.backfill_clip_visual_embeddings --max-scenes 100
```

### Option 2: Using Railway CLI

```bash
# Connect to Railway and run in worker service
railway run --service worker python -m src.scripts.backfill_clip_visual_embeddings --dry-run --max-scenes 10

# Or run directly in Railway shell
railway shell --service worker
python -m src.scripts.backfill_clip_visual_embeddings --max-scenes 100
```

### Option 3: Deploy as One-Off Job

Create a separate Railway service for backfill:

1. **Create new service**: `clip-backfill` (one-off job)
2. **Same image as worker**: Use worker Dockerfile
3. **Command override**:
   ```
   python -m src.scripts.backfill_clip_visual_embeddings --max-scenes 1000
   ```
4. **Environment variables**: Same as worker
5. **Deploy**: One-time deployment, removes after completion

## Checkpoint/Resume

The script automatically creates a checkpoint file (`.backfill_clip_checkpoint.json`) that tracks:
- Last processed scene ID
- Total processed, updated, skipped, errors
- Start time

### Resume After Interruption

```bash
# Script was interrupted (Ctrl+C, crash, etc.)
# Simply run again - it will resume from checkpoint
python -m src.scripts.backfill_clip_visual_embeddings
```

### Start Fresh

```bash
# Delete checkpoint to start from beginning
rm .backfill_clip_checkpoint.json
python -m src.scripts.backfill_clip_visual_embeddings
```

### Checkpoint Example

```json
{
  "last_scene_id": "12345678-1234-1234-1234-123456789012",
  "total_processed": 250,
  "total_updated": 200,
  "total_skipped": 40,
  "total_errors": 10,
  "started_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T11:45:00Z"
}
```

## Performance Considerations

### Expected Throughput

- **CLIP inference**: ~100-200ms per scene (CPU)
- **Thumbnail download**: ~50-100ms per scene
- **Database update**: ~50ms per scene
- **Total per scene**: ~200-400ms
- **Batch of 50 scenes**: ~15-30 seconds
- **1000 scenes**: ~5-10 minutes

### Resource Usage

- **Memory**: ~1.5GB (model + processing)
- **CPU**: 1-2 vCPU (single-threaded)
- **Network**: ~50KB per scene (thumbnail download)
- **Disk**: Temporary files cleaned up automatically

### Tuning for Performance

**Faster (more aggressive)**:
```bash
python -m src.scripts.backfill_clip_visual_embeddings \
  --batch-size 100 \
  --processing-delay 0.2 \
  --clip-timeout 3.0
```

**Safer (more conservative)**:
```bash
python -m src.scripts.backfill_clip_visual_embeddings \
  --batch-size 25 \
  --processing-delay 1.0 \
  --clip-timeout 10.0
```

## Monitoring Progress

### Real-Time Monitoring

```bash
# Watch logs in real-time
tail -f backfill.log

# Or use Railway logs
railway logs --service worker --tail
```

### Log Output Example

```
2025-01-15 10:30:00 - INFO - ================================================================================
2025-01-15 10:30:00 - INFO - CLIP Visual Embedding Backfill Started
2025-01-15 10:30:00 - INFO - ================================================================================
2025-01-15 10:30:00 - INFO - Batch size: 50
2025-01-15 10:30:00 - INFO - Max scenes: unlimited
2025-01-15 10:30:00 - INFO - Processing delay: 0.5s
2025-01-15 10:30:00 - INFO - CLIP timeout: 5.0s
2025-01-15 10:30:00 - INFO - CLIP model: ViT-B-32 (pretrained=openai)
2025-01-15 10:30:00 - INFO - ================================================================================
2025-01-15 10:30:05 - INFO - Fetching batch (offset=0, limit=50)...
2025-01-15 10:30:06 - INFO - Processing 50 scenes...
2025-01-15 10:30:07 - INFO - Scene 12: Generating CLIP embedding...
2025-01-15 10:30:07 - INFO - Scene 12: Updated with CLIP embedding (dim=512, time=145.2ms)
...
2025-01-15 10:30:30 - INFO - Progress: processed=50, updated=45, skipped=3, errors=2
```

### Database Monitoring

```sql
-- Check backfill progress
SELECT
  COUNT(*) FILTER (WHERE embedding_visual_clip IS NOT NULL) AS with_clip,
  COUNT(*) FILTER (WHERE embedding_visual_clip IS NULL) AS without_clip,
  ROUND(100.0 * COUNT(*) FILTER (WHERE embedding_visual_clip IS NOT NULL) / COUNT(*), 2) AS coverage_pct
FROM video_scenes
WHERE thumbnail_url IS NOT NULL;

-- Check recent backfills
SELECT
  COUNT(*) AS count,
  DATE_TRUNC('hour', (visual_clip_metadata->>'created_at')::timestamp) AS hour
FROM video_scenes
WHERE visual_clip_metadata IS NOT NULL
  AND (visual_clip_metadata->>'created_at')::timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;

-- Check error distribution
SELECT
  visual_clip_metadata->>'error' AS error_type,
  COUNT(*) AS count
FROM video_scenes
WHERE visual_clip_metadata->>'error' IS NOT NULL
GROUP BY visual_clip_metadata->>'error'
ORDER BY count DESC;
```

## Error Handling

### Common Errors

**1. Model Load Failure**
```
ERROR - Failed to initialize CLIP embedder: No module named 'open_clip'
```
**Solution**: Ensure dependencies are installed (`torch`, `open-clip-torch`)

**2. Thumbnail Download Failure**
```
WARNING - Failed to download thumbnail: user_id/video_id/thumbnails/scene_12.jpg
```
**Solution**: Check Supabase Storage permissions and URL format

**3. CLIP Timeout**
```
WARNING - Scene 12: CLIP embedding failed: Timeout after 5.0s
```
**Solution**: Increase `--clip-timeout` or provision more CPU

**4. Out of Memory**
```
ERROR - CUDA out of memory / MemoryError
```
**Solution**: Reduce `--batch-size` or use CPU device (`CLIP_DEVICE=cpu`)

### Error Recovery

The backfill script is designed to be resilient:
- **Errors are logged but don't stop processing**
- **Failed scenes have metadata with error recorded**
- **Checkpoint saves progress even with errors**
- **Can be re-run to retry failed scenes with `--force-regenerate`**

## Best Practices

### 1. Start with Dry Run

Always test with dry run first to estimate scope:
```bash
python -m src.scripts.backfill_clip_visual_embeddings --dry-run --max-scenes 100
```

### 2. Process in Batches

For large datasets, process in chunks:
```bash
# Day 1: First 1000 scenes
python -m src.scripts.backfill_clip_visual_embeddings --max-scenes 1000

# Day 2: Next 1000 scenes (automatically resumes)
python -m src.scripts.backfill_clip_visual_embeddings --max-scenes 2000
```

### 3. Monitor Resource Usage

```bash
# Watch memory and CPU
docker stats

# Or in Railway
railway logs --service worker --tail
```

### 4. Run During Off-Peak Hours

CLIP processing is CPU-intensive, so run during low-traffic periods.

### 5. Verify Results

After backfill, verify embeddings were generated:
```sql
-- Check coverage
SELECT
  COUNT(*) FILTER (WHERE embedding_visual_clip IS NOT NULL) AS with_clip,
  COUNT(*) AS total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE embedding_visual_clip IS NOT NULL) / COUNT(*), 2) AS coverage_pct
FROM video_scenes
WHERE thumbnail_url IS NOT NULL;
```

## Troubleshooting

### Issue: Backfill is Slow

**Symptoms**: <10 scenes/minute

**Diagnosis**:
```bash
# Check CPU usage
docker stats

# Check CLIP logs
grep "inference_time_ms" backfill.log
```

**Solutions**:
1. Increase CPU allocation (Railway: higher plan)
2. Reduce `--clip-timeout` to fail fast on slow scenes
3. Reduce `--batch-size` to prevent memory pressure

### Issue: Many Timeouts

**Symptoms**: High error count with "Timeout" errors

**Diagnosis**:
```sql
SELECT
  COUNT(*) FILTER (WHERE visual_clip_metadata->>'error' LIKE '%Timeout%') AS timeouts,
  COUNT(*) AS total_errors
FROM video_scenes
WHERE visual_clip_metadata->>'error' IS NOT NULL;
```

**Solutions**:
1. Increase `--clip-timeout` (e.g., `--clip-timeout 10.0`)
2. Provision more CPU
3. Check for CPU contention (other services)

### Issue: Checkpoint Not Resuming

**Symptoms**: Backfill starts from beginning every time

**Diagnosis**:
```bash
# Check if checkpoint file exists
ls -la .backfill_clip_checkpoint.json

# Check contents
cat .backfill_clip_checkpoint.json
```

**Solutions**:
1. Ensure checkpoint file is in working directory
2. Use absolute path: `--checkpoint-file /app/.backfill_clip_checkpoint.json`
3. Check file permissions

## Example Workflows

### Workflow 1: Full Backfill (All Scenes)

```bash
# Step 1: Dry run to check scope
python -m src.scripts.backfill_clip_visual_embeddings --dry-run --max-scenes 10

# Step 2: Run backfill (unlimited)
nohup python -m src.scripts.backfill_clip_visual_embeddings > backfill.log 2>&1 &

# Step 3: Monitor progress
tail -f backfill.log

# Step 4: Verify results
psql $DATABASE_URL -c "
SELECT
  COUNT(*) FILTER (WHERE embedding_visual_clip IS NOT NULL) AS with_clip,
  COUNT(*) AS total
FROM video_scenes
WHERE thumbnail_url IS NOT NULL;
"
```

### Workflow 2: Incremental Backfill (Batched)

```bash
# Day 1: First 1000 scenes
python -m src.scripts.backfill_clip_visual_embeddings --max-scenes 1000

# Day 2: Next 1000 scenes
python -m src.scripts.backfill_clip_visual_embeddings --max-scenes 2000

# Day 3: Remaining scenes
python -m src.scripts.backfill_clip_visual_embeddings
```

### Workflow 3: Single Video Backfill

```bash
# Get video ID
VIDEO_ID="12345678-1234-1234-1234-123456789012"

# Run backfill for specific video
python -m src.scripts.backfill_clip_visual_embeddings --video-id "$VIDEO_ID"

# Verify
psql $DATABASE_URL -c "
SELECT COUNT(*)
FROM video_scenes
WHERE video_id = '$VIDEO_ID'
  AND embedding_visual_clip IS NOT NULL;
"
```

## FAQ

**Q: Can I run backfill multiple times?**
A: Yes, by default it skips scenes that already have embeddings. Use `--force-regenerate` to re-process.

**Q: What happens if I interrupt backfill (Ctrl+C)?**
A: Checkpoint is saved automatically. Simply run again to resume.

**Q: How long will it take to backfill N scenes?**
A: Approximately N * 0.3 seconds = 300ms per scene average. 1000 scenes ≈ 5 minutes.

**Q: Can I run backfill while worker is processing new videos?**
A: Yes, backfill and normal processing don't interfere. But monitor CPU usage.

**Q: What if some thumbnails are missing?**
A: Scenes without `thumbnail_url` are automatically skipped (logged as "no_thumbnail").

**Q: Should I enable CLIP for new videos during backfill?**
A: Yes, set `CLIP_ENABLED=true` so new videos get CLIP embeddings automatically.

**Q: Can I run backfill in parallel (multiple instances)?**
A: Not recommended. Use a single instance with checkpointing for safety.

## Post-Backfill Verification

### 1. Check Coverage

```sql
SELECT
  COUNT(*) FILTER (WHERE embedding_visual_clip IS NOT NULL) AS with_clip,
  COUNT(*) FILTER (WHERE embedding_visual_clip IS NULL AND thumbnail_url IS NOT NULL) AS missing_clip,
  COUNT(*) FILTER (WHERE thumbnail_url IS NULL) AS no_thumbnail,
  ROUND(100.0 * COUNT(*) FILTER (WHERE embedding_visual_clip IS NOT NULL) /
        COUNT(*) FILTER (WHERE thumbnail_url IS NOT NULL), 2) AS coverage_pct
FROM video_scenes;
```

### 2. Check Quality

```sql
-- Average inference time
SELECT
  AVG((visual_clip_metadata->>'inference_time_ms')::float) AS avg_ms,
  MIN((visual_clip_metadata->>'inference_time_ms')::float) AS min_ms,
  MAX((visual_clip_metadata->>'inference_time_ms')::float) AS max_ms
FROM video_scenes
WHERE visual_clip_metadata->>'inference_time_ms' IS NOT NULL;

-- Error rate
SELECT
  COUNT(*) FILTER (WHERE visual_clip_metadata->>'error' IS NOT NULL) AS errors,
  COUNT(*) AS total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE visual_clip_metadata->>'error' IS NOT NULL) / COUNT(*), 2) AS error_pct
FROM video_scenes
WHERE visual_clip_metadata IS NOT NULL;
```

### 3. Test Search

```sql
-- Find similar scenes to a reference scene
WITH reference AS (
  SELECT embedding_visual_clip FROM video_scenes
  WHERE id = 'reference-scene-uuid'
)
SELECT * FROM search_scenes_by_visual_clip_embedding(
  query_embedding := (SELECT embedding_visual_clip FROM reference),
  match_threshold := 0.7,
  match_count := 10,
  filter_user_id := 'user-uuid'
);
```

## Support

If you encounter issues:
1. Check logs with `--clip-timeout 10.0` for more time
2. Try dry run first: `--dry-run --max-scenes 10`
3. Review error distribution in database
4. Check CLIP model loading with `CLIP_DEBUG_LOG=true`
