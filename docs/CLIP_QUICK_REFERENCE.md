# CLIP Visual Search - Quick Reference

**Last Updated:** 2025-12-28

---

## Quick Start

### Setup (5 minutes)

1. **Apply DB migration:**
   ```bash
   psql $DATABASE_URL -f infra/migrations/018_add_clip_batch_scoring.sql
   ```

2. **Configure environment:**
   ```bash
   export CLIP_RUNPOD_URL=https://api-xxxx.runpod.net
   export CLIP_RUNPOD_SECRET=your-secret
   export VISUAL_MODE=auto
   export MULTI_DENSE_ENABLED=true
   export WEIGHT_VISUAL=0.25
   ```

3. **Test:**
   ```bash
   python tests/integration/test_clip_search.py
   ```

---

## Visual Modes

| Mode | Use Case | CLIP Role |
|------|----------|-----------|
| `recall` | Strong visual queries | Retrieves candidates |
| `rerank` | Moderate visual queries | Reranks candidates |
| `auto` | General search | Router decides |
| `skip` | Speech queries | Disabled |

**Default:** `auto` (recommended)

---

## Example Queries

| Query | Router → Mode | Why |
|-------|--------------|-----|
| "red car" | recall | Strong visual (color + object) |
| "person walking" | recall | Action + object |
| "he says hello" | skip | Speech keyword ("says") |
| "the quote about love" | skip | Dialogue keyword ("quote") |
| "tteokbokki scene" | rerank | Mixed (visual food + context) |

---

## Configuration Cheat Sheet

```bash
# Essential
CLIP_RUNPOD_URL=<url>          # RunPod endpoint
CLIP_RUNPOD_SECRET=<secret>    # HMAC key
VISUAL_MODE=auto               # recall|rerank|auto|skip
MULTI_DENSE_ENABLED=true       # Required
WEIGHT_VISUAL=0.25             # Visual channel weight

# Tuning
RERANK_CLIP_WEIGHT=0.3         # 30% CLIP, 70% base
RERANK_CANDIDATE_POOL_SIZE=500 # Candidates to rerank
CLIP_TEXT_EMBEDDING_TIMEOUT_S=1.5  # Request timeout
```

---

## Testing Commands

```bash
# Unit tests
pytest tests/unit/test_visual_router.py -v

# Integration tests
python tests/integration/test_clip_search.py

# Manual test
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "red car", "limit": 10}'
```

---

## Debugging

### Check CLIP is working
```bash
grep "CLIP text embedding generated" logs/api.log
```

### Check router decisions
```bash
grep "Visual intent router" logs/api.log
```

### Check rerank activity
```bash
grep "CLIP rerank" logs/api.log
```

### Verify CLIP service
```bash
curl $CLIP_RUNPOD_URL/health
```

---

## Common Issues

| Problem | Solution |
|---------|----------|
| "CLIP not configured" | Set `CLIP_RUNPOD_URL` and `CLIP_RUNPOD_SECRET` |
| "CLIP timeout" | Increase `CLIP_TEXT_EMBEDDING_TIMEOUT_S` |
| "Visual channel returns 0" | Check CLIP embeddings in DB: `SELECT COUNT(embedding_visual_clip) FROM video_scenes` |
| "Auth failed" | Verify `CLIP_RUNPOD_SECRET` matches service |

---

## Performance Tips

1. **CLIP adds ~120ms** to query latency (acceptable)
2. **Rerank is more stable** than recall (use as default if unsure)
3. **Auto mode is smart** but can be overridden per-request
4. **Monitor P95 latency** - alert if > 500ms

---

## Rollback (1 minute)

```bash
# Disable CLIP completely
export VISUAL_MODE=skip
docker-compose restart api

# Verify
grep "visual_mode=skip" logs/api.log
```

---

## Key Files

| File | Purpose |
|------|---------|
| `src/adapters/clip_client.py` | CLIP RunPod client |
| `src/domain/visual_router.py` | Visual intent router |
| `src/domain/search/rerank.py` | Rerank logic |
| `src/routes/search.py` | Main integration |
| `migrations/018_*.sql` | Batch scoring RPC |

---

## Monitoring Queries

```sql
-- CLIP usage last hour
SELECT visual_mode, COUNT(*)
FROM search_logs
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY visual_mode;

-- CLIP latency
SELECT
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY clip_embedding_ms) AS p50,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY clip_embedding_ms) AS p95
FROM search_logs
WHERE clip_embedding_ms > 0;
```

---

## Support

- **Docs:** `docs/CLIP_VISUAL_SEARCH_IMPLEMENTATION.md`
- **Tests:** `tests/integration/test_clip_search.py`
- **Issues:** Check logs first, then contact team

---

**For full details, see:** `docs/CLIP_VISUAL_SEARCH_IMPLEMENTATION.md`
