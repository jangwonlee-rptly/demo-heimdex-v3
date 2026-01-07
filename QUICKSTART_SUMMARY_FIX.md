# Summary Search Fix - Quick Start Guide

**5-minute guide to verify the fix works**

---

## Prerequisites

- Docker and docker-compose installed
- Heimdex services running (`docker-compose up -d`)
- Valid auth token for API access

---

## Step 1: Verify Fix is Applied (30 seconds)

```bash
# Check worker config
docker-compose run --rm worker python -c "from src.config import settings; print('✓ Summary enabled' if settings.embedding_summary_enabled else '✗ Summary DISABLED')"

# Expected output:
# ✓ Summary enabled
```

**If you see "✗ Summary DISABLED":**
```bash
# Config not applied - rebuild worker
docker-compose build worker
docker-compose restart worker
```

---

## Step 2: Run Unit Tests (1 minute)

```bash
docker-compose run --rm worker pytest test_summary_embedding.py -v
```

**Expected output:**
```
test_create_multi_channel_embeddings_with_summary PASSED
test_summary_embedding_integration_with_build_sidecar PASSED
==================== 6 passed in 2.34s ====================
```

**If tests fail:** Check logs for error details. Most common issue is missing OpenAI API key.

---

## Step 3: Check Existing Data (1 minute)

```bash
# Inspect first 5 scenes
docker-compose run --rm api python /app/scripts/debug_summary_search.py --limit 5
```

**Expected output:**
```
[2] Summary Statistics:
  Total scenes checked: 5
  Scenes with visual_summary text: 5 (100%)
  Scenes with embedding_summary vector: 0 (0%)  ← Need to backfill!
```

**If embedding_summary = 0%:** Scenes were processed before the fix. Continue to Step 4.

**If embedding_summary = 100%:** Great! Skip to Step 5.

---

## Step 4: Backfill Scenes (2-30 minutes)

### Option A: Test with 10 scenes (recommended for first run)

```bash
docker-compose run --rm worker python -m src.scripts.backfill_scene_embeddings_v3 \
  --max-scenes 10 \
  --batch-size 10
```

**Expected output:**
```
Backfill v3-multi embeddings: batch 1/1 (10 scenes)
Scene 0: Backfilled v3-multi embeddings: [transcript, visual, summary]
Scene 1: Backfilled v3-multi embeddings: [transcript, visual, summary]
...
Summary: 10/10 processed, 10 updated, 0 skipped
```

**Time:** ~30 seconds
**Cost:** <$0.01

### Option B: Backfill all scenes

```bash
docker-compose run --rm worker python -m src.scripts.backfill_scene_embeddings_v3 \
  --batch-size 100
```

**Time:** ~20 minutes per 1000 scenes
**Cost:** ~$0.50 per 1000 scenes

---

## Step 5: Test Summary Search (1 minute)

```bash
# 1. Get a scene's summary text
SUMMARY=$(docker-compose run --rm api python -c "
import sys
sys.path.insert(0, '/app/src')
from adapters.database import Database
from config import settings

db = Database(settings.supabase_url, settings.supabase_service_key)
scenes = db.client.table('video_scenes').select('visual_summary').limit(1).execute()
if scenes.data:
    print(scenes.data[0]['visual_summary'][:100])
" 2>/dev/null)

echo "Summary text: $SUMMARY"

# 2. Search using summary text (replace YOUR_TOKEN)
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$SUMMARY\", \"channel_weights\": {\"summary\": 1.0}, \"limit\": 5}" \
  | python3 -m json.tool
```

**Expected output:**
```json
{
  "query": "비디오는 밤의 파리에서...",
  "results": [
    {
      "id": "...",
      "visual_summary": "비디오는 밤의 파리에서 에펠탑이...",
      "score": 0.95
    }
  ],
  "total": 3,
  "fusion_weights": {"summary": 1.0},
  "channel_candidate_counts": {
    "summary": 5  // ← Non-zero! Summary search works!
  }
}
```

**Success criteria:**
- ✅ `channel_candidate_counts.summary > 0`
- ✅ Results contain scenes with matching summary text
- ✅ Top result has high score (>0.8)

---

## Troubleshooting

### Problem: "Summary DISABLED" in Step 1

**Fix:**
```bash
# Edit config file
vim services/worker/src/config.py
# Change line 85: embedding_summary_enabled: bool = True

# Rebuild
docker-compose build worker
docker-compose restart worker
```

### Problem: Tests fail with "OpenAI API key not found"

**Fix:**
```bash
# Add to services/worker/.env
OPENAI_API_KEY=sk-your-key-here

# Restart
docker-compose restart worker
```

### Problem: Backfill shows "No scenes found"

**Cause:** No videos processed yet

**Fix:**
```bash
# Upload a test video first
curl -X POST http://localhost:8000/videos/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/video.mp4"

# Wait for processing (~1 minute per minute of video)
```

### Problem: Search returns `"channel_candidate_counts": {"summary": 0}`

**Diagnosis:**
```bash
# Check if embeddings exist
docker-compose run --rm api python /app/scripts/debug_summary_search.py --limit 5

# If "embedding_summary vector: 0 (0%)" → Run backfill (Step 4)
# If "embedding_summary vector: 100%" → Check search threshold
```

**Fix for threshold issue:**
```bash
# Lower threshold in search request
curl -X POST http://localhost:8000/search \
  -H "..." \
  -d '{"query": "...", "threshold": 0.1}'  # Lower threshold
```

---

## Next Steps

After verifying the fix works:

1. **Enable debug mode** to see detailed metrics:
   ```bash
   # Add to services/api/.env
   SEARCH_DEBUG=true

   docker-compose restart api
   ```

2. **Backfill all scenes** (if Step 4 used test subset):
   ```bash
   docker-compose run --rm worker python -m src.scripts.backfill_scene_embeddings_v3 --batch-size 100
   ```

3. **Monitor costs** in OpenAI dashboard:
   - Summary embeddings add ~10% to embedding costs
   - Budget: $0.50 per 1000 scenes for backfill
   - Ongoing: $0.0001 per scene for new videos

4. **Collect user feedback:**
   - Ask users to try summary-based searches
   - Compare relevance vs. transcript-only searches
   - Adjust default summary weight based on feedback

---

## Success!

If all steps passed, summary search is now working:

✅ New scenes generate summary embeddings automatically
✅ Backfilled scenes have summary embeddings
✅ Summary weight controls ranking
✅ Debug visibility shows channel activity

**Time to completion:** ~5 minutes (+ backfill time)

For detailed verification, see: `docs/summary-search-fix-verification.md`

---

**Questions?** Check the full analysis: `docs/summary-search-bug-analysis.md`
