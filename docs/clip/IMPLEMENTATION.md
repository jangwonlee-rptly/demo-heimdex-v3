# CLIP Visual Search Implementation Guide

**Version:** 1.0
**Date:** 2025-12-28
**Status:** Production-Ready

---

## Executive Summary

This document describes the implementation of CLIP-based visual search for Heimdex, enabling true multimodal search that matches query text against actual visual content in videos (not just textual descriptions).

### Key Features
- **True Visual Search:** CLIP text embeddings (512d) compared against CLIP image embeddings (512d) from keyframes
- **Three Modes:** recall (CLIP participates in retrieval), rerank (CLIP refines results), auto (intelligent routing)
- **Visual Intent Router:** Automatically detects visual vs speech queries
- **Production-Safe:** Graceful degradation, timeout protection, comprehensive logging
- **Backward Compatible:** Existing search continues to work if CLIP is disabled

---

## 1. Architecture Overview

### 1.1 The Problem (Before)

**Old behavior:**
```
Query: "red car"
  → OpenAI text embedding (1536d)
  → Searches embedding_visual (1536d OpenAI embeddings of visual_description text)
  → Matches: text descriptions like "vehicle with reddish paint"
  → NOT true visual search!
```

**Issue:** Visual channel used text-to-text similarity, not vision-grounded similarity.

### 1.2 The Solution (After)

**New behavior:**
```
Query: "red car"
  → CLIP text embedding (512d) via RunPod /v1/embed/text
  → Searches embedding_visual_clip (512d CLIP image embeddings from keyframes)
  → Matches: actual visual features (color, shape, objects) in images
  → TRUE multimodal visual search!
```

### 1.3 Search Modes

| Mode | Description | When to Use | CLIP Participation |
|------|-------------|-------------|-------------------|
| **recall** | CLIP retrieves candidates in parallel with other channels | Strong visual queries ("red car") | Full (retrieval + fusion) |
| **rerank** | CLIP only reranks candidates from other channels | Moderate visual queries | Post-fusion only |
| **auto** | Visual intent router decides per-query | General search | Determined by router |
| **skip** | CLIP disabled | Speech/dialogue queries | None |

---

## 2. Files Changed

### 2.1 New Files

| File | Purpose |
|------|---------|
| `services/api/src/adapters/clip_client.py` | CLIP RunPod HTTP client with HMAC auth |
| `services/api/src/domain/visual_router.py` | Visual intent classification (auto mode) |
| `services/api/src/domain/search/rerank.py` | CLIP reranking logic |
| `infra/migrations/018_add_clip_batch_scoring.sql` | Batch CLIP scoring RPC (rerank mode) |
| `services/api/tests/unit/test_visual_router.py` | Router unit tests |
| `services/api/tests/integration/test_clip_search.py` | CLIP integration tests |

### 2.2 Modified Files

| File | Changes |
|------|---------|
| `services/api/src/config.py` | Added CLIP config, visual_mode, rerank settings |
| `services/api/src/adapters/database.py` | Added `search_scenes_visual_clip_embedding()`, `batch_score_scenes_clip()` |
| `services/api/src/domain/search/fusion.py` | Added `ScoreType.RERANK_CLIP` |
| `services/api/src/routes/search.py` | Integrated CLIP embeddings, router, rerank mode |

---

## 3. Configuration

### 3.1 Required Environment Variables

```bash
# CLIP RunPod Configuration
CLIP_RUNPOD_URL=https://api-xxxx.runpod.net  # From RunPod deployment
CLIP_RUNPOD_SECRET=your-hmac-secret-key      # Must match RunPod service
CLIP_TEXT_EMBEDDING_TIMEOUT_S=1.5            # Request timeout
CLIP_TEXT_EMBEDDING_MAX_RETRIES=1            # Retry count for transient failures

# Visual Search Mode
VISUAL_MODE=auto                              # recall | rerank | auto | skip

# Multi-Dense (must be enabled for CLIP visual channel)
MULTI_DENSE_ENABLED=true
WEIGHT_VISUAL=0.25                            # Visual channel weight (0.0-1.0)

# Rerank Mode Settings
RERANK_CANDIDATE_POOL_SIZE=500               # Candidates to rerank
RERANK_CLIP_WEIGHT=0.3                       # CLIP contribution in rerank (0.0-1.0)
RERANK_MIN_SCORE_RANGE=0.05                  # Skip if CLIP scores are flat
```

### 3.2 Configuration Validation

Run configuration check:
```bash
cd services/api
python -c "from src.config import settings; print(f'Visual mode: {settings.visual_mode}')"
```

---

## 4. Database Migration

### 4.1 Apply Migration

```bash
cd infra/migrations
psql $DATABASE_URL -f 018_add_clip_batch_scoring.sql
```

### 4.2 Verify Migration

```sql
-- Check RPC exists
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_name = 'batch_score_scenes_clip';

-- Should return: batch_score_scenes_clip | FUNCTION
```

---

## 5. Testing Guide

### 5.1 Unit Tests

```bash
cd services/api
pytest tests/unit/test_visual_router.py -v
```

**Expected output:**
```
test_strong_visual_intent PASSED
test_strong_speech_intent PASSED
test_mixed_intent PASSED
test_korean_food_terms PASSED
test_deterministic PASSED
... [all tests pass]
```

### 5.2 Integration Tests

```bash
cd services/api
python tests/integration/test_clip_search.py
```

**Expected output:**
```
=== Test 1: CLIP Client Availability ===
✅ CLIP client is configured

=== Test 2: CLIP Text Embedding ===
Query: 'red car'
  - Embedding dim: 512
  - L2 norm: 1.0000
  - Latency: 120.3ms
✅ All CLIP text embeddings generated successfully

... [all tests pass]

🎉 All tests passed!
```

### 5.3 Manual Test Queries

Test with these queries to verify different modes:

**Strong Visual (should use recall mode):**
```json
POST /search
{
  "query": "red car driving fast",
  "limit": 10
}
```

**Speech/Dialogue (should skip CLIP):**
```json
POST /search
{
  "query": "the line where he says we're in this together",
  "limit": 10
}
```

**Mixed (should use rerank mode):**
```json
POST /search
{
  "query": "tteokbokki scene",
  "limit": 10
}
```

### 5.4 Verify CLIP Usage in Logs

Check logs for CLIP activity:

```bash
# Search for CLIP text embedding generation
grep "CLIP text embedding generated" logs/api.log

# Search for visual router decisions
grep "Visual intent router" logs/api.log

# Search for CLIP rerank activity
grep "CLIP rerank" logs/api.log
```

**Example log output:**
```
[INFO] CLIP text embedding generated: dim=512, elapsed_ms=115
[INFO] Visual intent router: mode=recall, confidence=0.90, reason=Strong visual intent: object:car, attr:red
[INFO] CLIP rerank: Scoring 500 candidates from top 500 results
[INFO] CLIP rerank complete: scored=487, skipped=False, clip_weight=0.3, elapsed_ms=45
```

---

## 6. Visual Intent Router

### 6.1 How It Works

The router analyzes query text for visual and speech signals:

**Visual Signals:**
- **Objects:** person, car, food, building, sign, etc.
- **Actions:** walking, running, eating, dancing, etc.
- **Attributes:** red, bright, close-up, blurry, etc.
- **Phrases:** "show me scenes with", "looks like", "wearing"

**Speech Signals:**
- **Keywords:** says, mentions, quote, dialogue, talks about
- **Phrases:** "he says", "the line where", "the quote"
- **Quotes:** Text in "quotes" or 'quotes'
- **Long questions:** "What is the meaning of...?" (likely seeking dialogue/meaning)

### 6.2 Router Logic

```python
if visual_score >= 3 and speech_score == 0:
    mode = "recall"  # Strong visual, use full CLIP retrieval

elif visual_score >= 2 and speech_score <= 1:
    mode = "rerank"  # Moderate visual, use CLIP to refine

elif speech_score >= 2 and visual_score == 0:
    mode = "skip"  # Strong speech, disable CLIP

else:
    mode = "rerank"  # Default safe mode
```

### 6.3 Example Classifications

| Query | Mode | Confidence | Reason |
|-------|------|-----------|--------|
| "red car driving" | recall | 0.9 | Strong visual (car, red, driving) |
| "person in crowd" | rerank | 0.7 | Moderate visual (person, crowd) |
| "he says goodbye" | skip | 0.9 | Strong speech (says, dialogue) |
| "tteokbokki scene" | rerank | 0.5 | Mixed (visual food + scene context) |
| "what is the theme?" | skip | 0.7 | Long question (seeking meaning) |

---

## 7. Rerank Mode Details

### 7.1 Why Rerank?

**Recall mode risks:**
- CLIP may dominate fusion if visual features are strong but irrelevant
- Relies on CLIP service availability during retrieval

**Rerank advantages:**
- CLIP refines results from stable channels (transcript, lexical)
- Controlled contribution via `rerank_clip_weight`
- Fails gracefully if CLIP unavailable

### 7.2 Rerank Algorithm

```python
1. Retrieve candidates from non-CLIP channels (transcript, summary, lexical)
   → Top 500 candidates (configurable)

2. Batch score candidates with CLIP in single DB query
   → Efficient: O(1) query, not O(N)

3. Normalize CLIP scores to [0, 1]

4. Blend: final_score = (1 - clip_weight) * base_score + clip_weight * clip_score
   → Default: 70% base, 30% CLIP

5. Re-sort and return
```

### 7.3 Flat Score Detection

If CLIP scores are nearly uniform (max - min < 0.05), skip CLIP:

```python
clip_scores = [0.72, 0.73, 0.71, 0.72]  # max-min = 0.02 < 0.05
→ Skip CLIP, return base ranking
→ Log: "CLIP rerank: Skipping due to flat scores (range=0.02)"
```

---

## 8. Performance Characteristics

### 8.1 Latency Breakdown (Typical)

| Component | Recall Mode | Rerank Mode | Skip Mode |
|-----------|-------------|-------------|-----------|
| OpenAI embed | 80ms | 80ms | 80ms |
| CLIP embed | 120ms | 120ms | 0ms |
| Retrieval | 150ms | 150ms | 150ms |
| CLIP rerank | 0ms | 45ms | 0ms |
| Fusion | 5ms | 5ms | 5ms |
| **Total** | **~355ms** | **~400ms** | **~235ms** |

### 8.2 Optimization Tips

1. **Caching:** Cache CLIP embeddings for frequent queries (TODO)
2. **Parallel execution:** OpenAI + CLIP embeddings run concurrently
3. **Batch size:** Limit rerank pool to 500 (good balance of quality vs speed)
4. **Timeout tuning:** Adjust `CLIP_TEXT_EMBEDDING_TIMEOUT_S` based on P95 latency

---

## 9. Troubleshooting

### 9.1 CLIP Service Unreachable

**Symptoms:**
```
[WARNING] CLIP text embedding failed: CLIP network error: Connection refused
[INFO] Visual intent router: mode=skip (degraded to speech-only search)
```

**Resolution:**
1. Check `CLIP_RUNPOD_URL` is correct
2. Verify RunPod endpoint is deployed and healthy
3. Test connectivity: `curl $CLIP_RUNPOD_URL/health`

### 9.2 CLIP Authentication Failed

**Symptoms:**
```
[ERROR] CLIP authentication failed: 401 Unauthorized
```

**Resolution:**
1. Verify `CLIP_RUNPOD_SECRET` matches RunPod service config
2. Check HMAC signature algorithm matches (SHA256)
3. Ensure canonical message format is consistent

### 9.3 Visual Channel Returns No Results

**Symptoms:**
```
[DEBUG] CLIP visual search: 0 results
[INFO] Visual channel skipped: no CLIP embedding
```

**Possible causes:**
1. CLIP embeddings not backfilled in DB (check `embedding_visual_clip IS NOT NULL`)
2. Threshold too high (`THRESHOLD_VISUAL > max similarity`)
3. CLIP service down → degraded to skip mode

**Resolution:**
```sql
-- Check CLIP embedding coverage
SELECT COUNT(*) as total_scenes,
       COUNT(embedding_visual_clip) as with_clip,
       ROUND(100.0 * COUNT(embedding_visual_clip) / COUNT(*), 2) as coverage_pct
FROM video_scenes;
```

### 9.4 Rerank Not Applied

**Symptoms:**
```
[INFO] CLIP rerank: Skipping due to flat scores (range=0.03)
```

**Explanation:** This is expected when CLIP scores are too uniform (not discriminative).

**Tuning:** Lower `RERANK_MIN_SCORE_RANGE` if you want CLIP to apply even with weak signals (not recommended).

---

## 10. Known Limitations

### 10.1 Current Limitations

1. **No CLIP query caching:** Every query generates new CLIP embedding (adds ~120ms)
2. **Single keyframe per scene:** Uses best keyframe, not multi-frame fusion
3. **No cross-modal attention:** Text and image embeddings are independent
4. **Language support:** Router optimized for English/Korean, may miss visual signals in other languages

### 10.2 Future Enhancements

**Recommended next steps:**

1. **CLIP Caching:**
   - Cache CLIP text embeddings for frequent queries
   - TTL: 1 hour (balance freshness vs hit rate)
   - Expected impact: -100ms for cache hits (~30% of queries)

2. **Multi-Frame Fusion:**
   - Store CLIP embeddings for top-N keyframes per scene
   - Aggregate: max/avg/attention-weighted similarity
   - Better coverage of scene content

3. **Adaptive Thresholds:**
   - Learn optimal thresholds per video/genre
   - Adjust `rerank_clip_weight` based on query type
   - Personalize based on user behavior

4. **Cross-Modal Reranking:**
   - Use CLIP to rerank across modalities (text ↔ image)
   - Boost results where text and visual signals agree

---

## 11. Monitoring & Metrics

### 11.1 Key Metrics to Track

**Usage:**
- % queries using CLIP (recall/rerank/skip breakdown)
- Router mode distribution
- CLIP embedding cache hit rate

**Performance:**
- P50/P95/P99 CLIP embedding latency
- P50/P95/P99 total search latency (by mode)
- CLIP timeout rate

**Quality:**
- CLIP score range distribution (detect flat scores)
- % queries where CLIP rerank was skipped
- User engagement with CLIP-ranked results

### 11.2 Alerts to Configure

```yaml
# CLIP Service Health
- alert: ClipServiceDown
  expr: clip_request_errors > 10 per 5min
  action: Fallback to skip mode + page on-call

# Latency Degradation
- alert: ClipLatencyHigh
  expr: clip_embedding_p95_latency > 500ms
  action: Investigate RunPod capacity

# Quality Issue
- alert: ClipScoresFlatHigh
  expr: clip_rerank_skipped_pct > 50%
  action: Review query distribution + threshold tuning
```

---

## 12. Deployment Checklist

- [ ] Apply DB migration 018 to production
- [ ] Configure all CLIP environment variables
- [ ] Deploy RunPod CLIP service and verify /health endpoint
- [ ] Test CLIP client connectivity from API service
- [ ] Run integration tests (`test_clip_search.py`)
- [ ] Deploy API service with new code
- [ ] Monitor logs for CLIP activity
- [ ] Test sample queries (visual/speech/mixed)
- [ ] Set up monitoring dashboards
- [ ] Configure alerts
- [ ] Document runbook for CLIP service issues

---

## 13. Rollback Plan

If CLIP causes issues, graceful rollback:

**Option 1: Disable CLIP entirely**
```bash
# Set environment variable
VISUAL_MODE=skip
# or
WEIGHT_VISUAL=0.0

# Restart API service
docker-compose restart api
```

**Option 2: Disable only rerank mode**
```bash
VISUAL_MODE=recall  # Use CLIP only for retrieval, not rerank
```

**Option 3: Disable auto routing**
```bash
VISUAL_MODE=rerank  # Always use rerank, no router
```

**No code rollback needed** - all changes degrade gracefully via config.

---

## 14. Support & Contact

**For issues:**
1. Check logs: `grep "CLIP\|visual_router" logs/api.log`
2. Run integration tests: `python tests/integration/test_clip_search.py`
3. Review this guide's Troubleshooting section
4. Contact: [Your Team/Email]

**For feature requests:**
- See "Future Enhancements" section
- Submit issue with label `enhancement:clip-search`

---

**End of Document**
