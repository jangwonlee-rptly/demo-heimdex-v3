# Summary Search Fix - Verification Guide

**Date:** 2025-01-07
**Fix:** Enable summary embeddings for scenes with visual_summary text

## What Was Fixed

1. **Worker Config** (`services/worker/src/config.py:85`)
   - Changed `embedding_summary_enabled = True` (was `False`)

2. **Sidecar Builder** (`services/worker/src/domain/sidecar_builder.py:1045`)
   - Pass `summary=visual_summary` (was `summary=None`)

3. **Backfill Script** (`services/worker/src/scripts/backfill_scene_embeddings_v3.py`)
   - Updated to use `visual_summary` field
   - Made idempotent (only regenerates missing embeddings by default)

4. **API Debug Fields** (`services/api/src/domain/schemas.py` + `routes/search.py`)
   - Added `channel_candidate_counts` to show retrieval counts per channel
   - Added `effective_weights_after_redistribution` to show actual weights used

5. **Unit Tests** (`services/worker/test_summary_embedding.py`)
   - Tests that fail if summary embeddings are not generated

---

## Verification Steps

### Step 1: Run Unit Tests

Verify the fix works at the code level:

```bash
# Run summary embedding tests
docker-compose run --rm worker pytest test_summary_embedding.py -v

# Expected output:
# test_create_multi_channel_embeddings_with_summary PASSED
# test_summary_embedding_integration_with_build_sidecar PASSED
# All tests should PASS
```

**What this verifies:**
- Summary embeddings are generated when `visual_summary` exists
- The `_create_multi_channel_embeddings()` function works correctly
- The `build_sidecar()` integration produces non-null `embedding_summary`

---

### Step 2: Process a Test Video

Upload and process a new video to verify summary embeddings are generated:

```bash
# 1. Upload a test video via API (use your actual auth token)
curl -X POST http://localhost:8000/videos/upload \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -F "file=@/path/to/test-video.mp4"

# Response will contain video_id
# {"id": "550e8400-e29b-41d4-a716-446655440000", ...}

# 2. Wait for processing to complete (~30-60 seconds for a 1-minute video)
# Check status:
curl http://localhost:8000/videos/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"

# Status should be "completed"
```

**What this verifies:**
- New videos processed after the fix generate summary embeddings
- Worker config change is active

---

### Step 3: Verify Summary Embedding in Database

Check that scenes have non-null `embedding_summary`:

```bash
# Run debug script to inspect scenes
docker-compose run --rm api python /app/scripts/debug_summary_search.py \
  --video-id 550e8400-e29b-41d4-a716-446655440000 \
  --limit 5

# Expected output:
# [2] Summary Statistics:
#   Scenes with visual_summary text: 5 (100%)
#   Scenes with embedding_summary vector: 5 (100%)  ← CRITICAL
#   Scenes with v3-multi embedding version: 5 (100%)
```

**What this verifies:**
- Scenes have both `visual_summary` text AND `embedding_summary` vector
- The fix is working end-to-end

**If embedding_summary is still NULL:**
- Check worker logs: `docker-compose logs worker | grep "summary"`
- Verify config: `docker-compose run --rm worker python -c "from src.config import settings; print(settings.embedding_summary_enabled)"`
- Should print `True`

---

### Step 4: Backfill Existing Scenes

Generate summary embeddings for scenes processed before the fix:

```bash
# Option A: Dry run (see what would be done)
docker-compose run --rm worker python -m src.scripts.backfill_scene_embeddings_v3 \
  --dry-run \
  --limit 10

# Expected output:
# Scene X: DRY RUN - Would generate embeddings for summary=True

# Option B: Backfill missing embeddings only (idempotent, safe to re-run)
docker-compose run --rm worker python -m src.scripts.backfill_scene_embeddings_v3 \
  --batch-size 100 \
  --max-scenes 1000

# Expected output:
# Scene X: Backfilled v3-multi embeddings: [transcript, visual, summary]
# Progress: 150/1000 scenes processed...

# Option C: Force regenerate ALL embeddings (use for data corruption)
docker-compose run --rm worker python -m src.scripts.backfill_scene_embeddings_v3 \
  --force-regenerate \
  --batch-size 50
```

**What this verifies:**
- Existing scenes can be updated with summary embeddings
- Backfill script is idempotent (won't re-process scenes that already have embeddings)

**Estimated time & cost:**
- 100 scenes: ~2 minutes, $0.05
- 1000 scenes: ~20 minutes, $0.50
- 10,000 scenes: ~3 hours, $5.00

---

### Step 5: Test Summary-Based Search

Search for a scene using its exact summary text:

```bash
# 1. Get a scene's summary
docker-compose run --rm api python /app/scripts/debug_summary_search.py \
  --limit 1

# Copy the visual_summary text from output, e.g.:
# "비디오는 밤의 파리에서 에펠탑이 빛나는 장면으로 시작된다..."

# 2. Search using that summary text (via API with debug=True)
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "비디오는 밤의 파리에서 에펠탑이 빛나는 장면으로",
    "limit": 10,
    "channel_weights": {
      "transcript": 0.0,
      "visual": 0.0,
      "summary": 1.0,
      "lexical": 0.0
    }
  }'
```

**Expected response (with SEARCH_DEBUG=true in .env):**

```json
{
  "query": "비디오는 밤의 파리에서...",
  "results": [
    {
      "id": "...",
      "visual_summary": "비디오는 밤의 파리에서 에펠탑이 빛나는 장면으로 시작된다...",
      "score": 0.95,
      "score_type": "multi_dense_minmax_mean"
    }
  ],
  "total": 3,
  "fusion_method": "multi_dense_minmax_mean",
  "fusion_weights": {
    "transcript": 0.0,
    "visual": 0.0,
    "summary": 1.0,
    "lexical": 0.0
  },
  "channel_candidate_counts": {
    "transcript": 0,
    "visual": 0,
    "summary": 5,     // ← CRITICAL: Summary channel has candidates!
    "lexical": 0
  },
  "effective_weights_after_redistribution": {
    "summary": 1.0    // ← Weight stays at 1.0 (no redistribution)
  },
  "channels_active": ["summary"],
  "channels_empty": ["transcript", "visual", "lexical"]
}
```

**What this verifies:**
- Summary channel retrieves candidates (`channel_candidate_counts.summary > 0`)
- Summary weight is respected (no redistribution to other channels)
- Scenes are ranked by summary similarity

---

### Step 6: Test Weight Redistribution

Verify that when summary channel is empty, weight redistributes correctly:

```bash
# Search with a query that has NO summary matches
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "xyz nonexistent query abc",
    "channel_weights": {
      "transcript": 0.0,
      "visual": 0.0,
      "summary": 1.0,
      "lexical": 0.0
    }
  }'
```

**Expected response:**

```json
{
  "results": [],  // No results (all channels empty)
  "channel_candidate_counts": {
    "transcript": 0,
    "visual": 0,
    "summary": 0,   // ← Summary channel is empty
    "lexical": 0
  },
  "effective_weights_after_redistribution": null,  // All channels empty
  "channels_active": [],
  "channels_empty": ["transcript", "visual", "summary", "lexical"]
}
```

**What this verifies:**
- System handles empty summary channel gracefully
- No crashes when all channels are empty

---

### Step 7: Compare Before/After (Integration Test)

Test the exact scenario from the bug report:

```bash
# BEFORE FIX (expected behavior):
# Query: Exact Korean summary text
# Summary weight: 1.0
# Result: 0 results (summary channel always empty)

# AFTER FIX (expected behavior):
# Query: Exact Korean summary text
# Summary weight: 1.0
# Result: Scene with that summary ranks #1

# Run integration test:
docker-compose run --rm api python -c "
import sys
sys.path.insert(0, '/app/src')

from adapters.database import Database
from adapters.openai_client import OpenAIClient
from config import settings
from uuid import UUID

db = Database(settings.supabase_url, settings.supabase_service_key)
openai = OpenAIClient(settings.openai_api_key)

# Get a scene with summary
scenes = db.client.table('video_scenes').select('id, visual_summary, embedding_summary').limit(1).execute()
if not scenes.data:
    print('ERROR: No scenes found')
    sys.exit(1)

scene = scenes.data[0]
scene_id = scene['id']
summary_text = scene['visual_summary']
has_embedding = scene['embedding_summary'] is not None

print(f'Scene ID: {scene_id}')
print(f'Summary text (first 100 chars): {summary_text[:100]}...')
print(f'Has embedding_summary: {has_embedding}')

if not has_embedding:
    print('FAIL: Scene has visual_summary but NO embedding_summary!')
    sys.exit(1)

# Search by summary
query_emb = openai.create_embedding(summary_text[:100])
results = db.search_scenes_summary_embedding(
    query_embedding=query_emb,
    user_id=UUID('00000000-0000-0000-0000-000000000000'),  # Replace with actual user
    match_count=10,
    threshold=0.3,
)

print(f'Search results: {len(results)}')
if results:
    print(f'Top result: scene_id={results[0][0]}, similarity={results[0][2]:.4f}')
    if results[0][0] == scene_id:
        print('SUCCESS: Found the exact scene!')
    else:
        print('WARN: Different scene ranked #1')
else:
    print('FAIL: No results from summary search!')
    sys.exit(1)
"
```

**Expected output:**

```
Scene ID: 550e8400-e29b-41d4-a716-446655440000
Summary text (first 100 chars): 비디오는 밤의 파리에서 에펠탑이 빛나는 장면으로 시작된다. 금색 조명에 둘러싸인...
Has embedding_summary: True
Search results: 5
Top result: scene_id=550e8400-e29b-41d4-a716-446655440000, similarity=0.9532
SUCCESS: Found the exact scene!
```

---

## Acceptance Criteria Checklist

### ✅ Criterion 1: Newly processed scenes produce non-null `embedding_summary`

**Verification:**
```bash
docker-compose run --rm api python /app/scripts/debug_summary_search.py --video-id <new-video-id>
```

**Expected:**
- `Scenes with embedding_summary vector: X (100%)`

---

### ✅ Criterion 2: `search_scenes_by_summary_embedding` returns candidates

**Verification:**
```bash
# See Step 7 integration test above
```

**Expected:**
- Function returns results (not empty list)
- Similarity > 0.7 for near-identical queries

---

### ✅ Criterion 3: Summary weight meaningfully changes ranking

**Test A: Summary weight = 1.0**
```bash
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "에펠탑", "channel_weights": {"summary": 1.0}}'
```

**Test B: Summary weight = 0.0**
```bash
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "에펠탑", "channel_weights": {"summary": 0.0, "transcript": 1.0}}'
```

**Expected:**
- Different scenes in top 3 results
- Test A prioritizes scenes with "에펠탑" in `visual_summary`
- Test B prioritizes scenes with "에펠탑" in `transcript_segment`

---

### ✅ Criterion 4: Debug visibility shows candidate counts & effective weights

**Verification:**
```bash
# Ensure SEARCH_DEBUG=true in services/api/.env
docker-compose restart api

curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "channel_weights": {"summary": 1.0}}'
```

**Expected response includes:**
```json
{
  "channel_candidate_counts": {
    "transcript": 150,
    "visual": 80,
    "summary": 5,    // ← Visible
    "lexical": 200
  },
  "effective_weights_after_redistribution": {
    "transcript": 0.0,
    "visual": 0.0,
    "summary": 1.0,  // ← Visible
    "lexical": 0.0
  }
}
```

---

## Troubleshooting

### Problem: Unit tests fail

**Symptom:**
```
test_summary_embedding_integration_with_build_sidecar FAILED
AssertionError: embedding_summary MUST be non-null
```

**Fix:**
1. Check worker config:
   ```bash
   docker-compose run --rm worker python -c "from src.config import settings; print(settings.embedding_summary_enabled)"
   ```
2. Should print `True`. If `False`, edit `services/worker/src/config.py:85`
3. Rebuild: `docker-compose build worker`

---

### Problem: Backfill script doesn't generate summary embeddings

**Symptom:**
```
Scene X: Backfilled v3-multi embeddings: [transcript, visual]  # Missing 'summary'
```

**Fix:**
1. Check if scenes have `visual_summary`:
   ```bash
   docker-compose run --rm api python /app/scripts/debug_summary_search.py --limit 5
   ```
2. If `visual_summary` is NULL, scenes were processed without visual analysis
3. Re-process video or manually add summary text

---

### Problem: Search returns 0 summary candidates

**Symptom:**
```json
"channel_candidate_counts": {"summary": 0}
```

**Diagnosis:**
1. Check if embeddings exist:
   ```bash
   docker-compose run --rm api python /app/scripts/debug_summary_search.py
   ```
2. If `embedding_summary` is NULL, run backfill
3. If embeddings exist but query returns 0, check threshold:
   - Lower threshold: `"threshold": 0.1` in search request

---

### Problem: summary weight = 1.0 but other channels are used

**Symptom:**
```json
"effective_weights_after_redistribution": {
  "transcript": 0.5,
  "summary": 0.5  // ← Should be 1.0
}
```

**Cause:**
- Summary channel returned 0 candidates
- Weights were redistributed to active channels

**Fix:**
- Check `channel_candidate_counts.summary` in response
- If 0, verify embeddings exist (see Problem #2)
- If embeddings exist, lower threshold or check query relevance

---

## Rollback Plan

If the fix causes issues:

```bash
# 1. Revert worker config
git checkout HEAD -- services/worker/src/config.py

# 2. Revert sidecar_builder
git checkout HEAD -- services/worker/src/domain/sidecar_builder.py

# 3. Rebuild worker
docker-compose build worker
docker-compose restart worker

# 4. Existing scenes with embedding_summary are safe (no data loss)
# They will be ignored (empty channel) in search
```

---

## Success Metrics

After deploying the fix, monitor:

1. **Summary channel usage:**
   - Query logs with `channel_candidate_counts.summary > 0`
   - Target: >20% of searches use summary channel

2. **Summary weight in preferences:**
   - User preferences with `summary > 0.0`
   - Target: >10% of users adjust summary weight

3. **Search quality:**
   - User feedback on summary-based searches
   - A/B test summary weight = 0.1 vs 0.0

4. **Cost impact:**
   - OpenAI API costs for summary embeddings
   - Estimated: +10% token usage (summary adds 1 embedding per scene)

---

**End of Verification Guide**
