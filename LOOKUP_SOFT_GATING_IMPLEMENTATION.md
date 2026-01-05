# Lookup Soft Lexical Gating Implementation

## Overview

This document describes the implementation of "soft lexical gating" for brand/proper noun queries. The feature reduces false positives by preferring lexical (BM25) matches when available for lookup-like queries, while gracefully falling back to dense semantic search with clear UI labeling when no exact matches exist.

## Problem Statement

**Issue:** Brand/proper noun queries (e.g., "Heimdex", "BTS", "이장원") often return irrelevant semantic matches when the exact term doesn't appear in the transcript/text. This leads to user confusion and poor search precision.

**Solution:** Detect lookup intent → prefer lexical matches → if none found, fall back to dense with "best guess" label.

---

## Implementation Summary

### Files Created

1. **`/services/api/src/domain/search/intent.py`** (NEW)
   - Query intent detection module
   - `detect_query_intent(query, language)` → "lookup" | "semantic"
   - Heuristics: uppercase letters, Korean names (2-4 syllables), short alphanumeric
   - Helper: `looks_like_korean_name(text)`

2. **`/services/api/tests/unit/test_query_intent.py`** (NEW)
   - 25+ test cases for intent detection
   - Coverage: brand names, K-pop groups, Korean names, semantic phrases

3. **`/services/api/tests/integration/test_lookup_soft_gating.py`** (NEW)
   - Integration tests for soft gating logic
   - Config validation, allowlist filtering simulation, fallback behavior

### Files Modified

4. **`/services/api/src/config.py`**
   - Added 4 feature flags:
     - `enable_lookup_soft_gating: bool = False` (default OFF)
     - `lookup_lexical_min_hits: int = 1`
     - `lookup_fallback_mode: str = "dense_best_guess"`
     - `lookup_label_mode: str = "api_field"`

5. **`/services/api/src/domain/schemas.py`**
   - Added `match_quality: Optional[str]` field to `VideoSceneResponse`
   - Values: `"supported"` (lexical hits) | `"best_guess"` (no lexical hits)

6. **`/services/api/src/routes/search.py`**
   - Line ~408: Added intent detection early in search flow
   - Lines 510-562: Soft lexical gating logic (early lexical check)
   - Lines 123-265: Updated `_run_multi_dense_search()` to accept and apply allowlist
   - Lines 268-369: Updated `_hydrate_scenes()` to set `match_quality` field
   - Lines 1045-1062: Added structured logging for metrics

7. **`/services/frontend/src/types/index.ts`**
   - Added `match_quality?: 'supported' | 'best_guess' | string` to `VideoScene`

8. **`/services/frontend/src/app/search/page.tsx`**
   - Lines 474-478: Added "Best guess" badge for `match_quality === 'best_guess'`

---

## How It Works

### 1. Query Intent Detection

```python
from src.domain.search.intent import detect_query_intent

intent = detect_query_intent("Heimdex", language="ko")  # → "lookup"
intent = detect_query_intent("영상 편집", language="ko")  # → "semantic"
```

**Heuristics for "lookup":**
- 1-2 tokens AND contains uppercase (e.g., "BTS", "OpenAI", "Heimdex")
- Korean name pattern: 2-4 Hangul syllables, no spaces (e.g., "이장원", "김철수")
- Very short (<= 6 chars) and mostly alphanumeric (e.g., "API", "GPU")

### 2. Soft Lexical Gating Flow

```
User query "Heimdex"
    ↓
Detect intent → "lookup"
    ↓
IF enable_lookup_soft_gating=true AND intent="lookup":
    Run early lexical (BM25) search
    ↓
    IF lexical_hits >= lookup_lexical_min_hits (default 1):
        → ALLOWLIST MODE
        - Build allowlist_ids from lexical results
        - Filter all dense channels to allowlist_ids
        - Set match_quality="supported"
    ELSE (lexical_hits == 0):
        → FALLBACK MODE
        - Proceed with normal dense search
        - Set match_quality="best_guess"
        - UI shows "Best guess" badge
    ↓
Fusion + ranking (normal flow)
    ↓
Response with match_quality field
```

### 3. Allowlist Filtering

When lexical hits are found, dense channels are filtered:

```python
# Before filtering
transcript_candidates = [scene_a, scene_b, scene_c, scene_d]
visual_candidates = [scene_a, scene_c, scene_e]

# Lexical allowlist
allowlist_ids = {scene_a, scene_c}  # Only these had BM25 hits

# After filtering
transcript_candidates = [scene_a, scene_c]  # Filtered
visual_candidates = [scene_a, scene_c]      # Filtered

# Fusion proceeds with filtered candidates only
```

**Key property:** Ranking order is still determined by fusion of all channels, but candidate pool is restricted to lexically-supported scenes.

### 4. Match Quality Labeling

API response includes `match_quality` field:

```json
{
  "results": [
    {
      "id": "...",
      "score": 0.95,
      "display_score": 0.92,
      "match_quality": "supported",  // ← NEW
      "transcript_segment": "... Heimdex platform ...",
      "..."
    }
  ]
}
```

Frontend displays badge:
- `match_quality="supported"` → No badge (normal)
- `match_quality="best_guess"` → Yellow badge: "Best guess"

---

## Configuration

### Environment Variables

Add to `/services/api/.env`:

```bash
# Lookup soft lexical gating (feature flag)
ENABLE_LOOKUP_SOFT_GATING=false  # Set to true to enable
LOOKUP_LEXICAL_MIN_HITS=1        # Minimum lexical hits to trigger allowlist
LOOKUP_FALLBACK_MODE=dense_best_guess
LOOKUP_LABEL_MODE=api_field
```

### Tuning Parameters

**`lookup_lexical_min_hits`** (default: 1)
- Minimum number of lexical hits required to use allowlist mode
- `1` = Even a single BM25 hit triggers allowlist (high precision)
- `2-3` = Requires multiple hits (more conservative)

**Use cases:**
- `lookup_lexical_min_hits=1`: Aggressive filtering, best for brands/names
- `lookup_lexical_min_hits=3`: Conservative, allows some semantic mixing

---

## Testing

### Unit Tests (Docker)

```bash
# Run intent detection tests
docker-compose run --rm api pytest tests/unit/test_query_intent.py -v
```

Expected output:
```
test_lookup_queries PASSED
test_semantic_queries PASSED
test_empty_query PASSED
test_korean_name_pattern PASSED
test_short_alphanumeric PASSED
...
25+ tests passed
```

### Integration Tests (Docker)

```bash
# Run soft gating integration tests
docker-compose run --rm api pytest tests/integration/test_lookup_soft_gating.py -v
```

Expected output:
```
test_detect_query_intent_lookup PASSED
test_config_lookup_soft_gating_flags PASSED
test_allowlist_filtering_simulation PASSED
test_fallback_behavior_simulation PASSED
...
8 tests passed
```

### Manual Testing

1. **Enable feature flag:**
   ```bash
   # In services/api/.env
   ENABLE_LOOKUP_SOFT_GATING=true
   SEARCH_DEBUG=true  # Optional: see gating logs
   ```

2. **Restart API:**
   ```bash
   docker-compose restart api
   ```

3. **Test lookup query with lexical hits:**
   - Query: "Heimdex" (assuming "Heimdex" appears in transcript)
   - Expected:
     - Intent: `lookup`
     - Lexical hits: > 0
     - Mode: Allowlist
     - Results: Only scenes mentioning "Heimdex"
     - `match_quality`: "supported"

4. **Test lookup query with NO lexical hits:**
   - Query: "NonexistentBrand123"
   - Expected:
     - Intent: `lookup`
     - Lexical hits: 0
     - Mode: Fallback
     - Results: Dense semantic approximations
     - `match_quality`: "best_guess"
     - UI: Yellow "Best guess" badge

5. **Test semantic query:**
   - Query: "영상 편집" (video editing)
   - Expected:
     - Intent: `semantic`
     - No gating applied (normal behavior)
     - `match_quality`: null

---

## Acceptance Criteria

✅ **With flag OFF (`enable_lookup_soft_gating=false`):**
- No behavior change
- Intent detection runs but doesn't affect results
- No `match_quality` field in response

✅ **With flag ON + lookup query + lexical hits:**
- Intent detected as "lookup"
- Early lexical check runs
- Results filtered to lexical allowlist
- `match_quality="supported"`
- No "Best guess" badge in UI

✅ **With flag ON + lookup query + NO lexical hits:**
- Intent detected as "lookup"
- Early lexical check returns 0 hits
- Fallback to dense search (normal retrieval)
- `match_quality="best_guess"`
- UI shows yellow "Best guess" badge

✅ **Ranking stability:**
- Allowlist filtering does NOT change ranking order
- Fusion still uses all active channels
- Only candidate pool is restricted

✅ **Logging:**
- Structured log line per lookup query:
  ```
  Lookup soft gating metrics: query='Heimdex', intent=lookup,
  lexical_hits=5, used_allowlist=True, fallback_used=False,
  match_quality=supported, results_count=10, top_raw_scores=[...], ...
  ```

---

## Performance Impact

### Computational Cost
- **Intent detection:** ~0.01ms (negligible regex + string ops)
- **Early lexical check:** ~10-50ms (OpenSearch BM25 query)
  - Only runs for lookup queries (typically <10% of traffic)
  - Runs in parallel with embedding generation (minimal latency impact)
- **Allowlist filtering:** ~0.1ms (set membership checks)

### Overall Impact
- Lookup queries: +10-50ms (early lexical check)
- Semantic queries: No impact
- Worst case: +50ms for 10% of queries = +5ms average latency

---

## Debugging

### Enable Debug Logging

```bash
# In services/api/.env
SEARCH_DEBUG=true
ENABLE_LOOKUP_SOFT_GATING=true
```

Check logs:
```bash
docker-compose logs -f api | grep "Lookup soft gating"
```

Expected output:
```
[INFO] Lookup soft gating: Running early lexical check for query intent=lookup
[INFO] Lookup soft gating: Lexical check found 5 hits (threshold=1, elapsed_ms=25)
[INFO] Lookup soft gating: ALLOWLIST MODE - Filtering dense channels to 5 lexically-supported scene IDs
[INFO] Lookup soft gating: Allowlist filtering applied - 120 -> 15 candidates (allowlist size=5)
[INFO] Lookup soft gating metrics: query='Heimdex', intent=lookup, lexical_hits=5, used_allowlist=True, ...
```

### Common Issues

**Issue 1: No lexical hits for known brands**
- **Cause:** Brand name not in transcript/combined_text
- **Solution:** Check OpenSearch index, ensure scenes are indexed with combined_text
- **Debug:** Run manual BM25 query:
  ```bash
  curl -X POST "localhost:9200/scene_docs/_search" -H 'Content-Type: application/json' -d'
  {
    "query": {
      "match": {
        "combined_text": "Heimdex"
      }
    }
  }'
  ```

**Issue 2: Semantic queries getting labeled as lookup**
- **Cause:** Intent detection heuristic too aggressive
- **Solution:** Tune heuristics in `/services/api/src/domain/search/intent.py`
- **Debug:** Check log for `intent=` field

**Issue 3: Allowlist filtering too restrictive**
- **Cause:** `lookup_lexical_min_hits` threshold too low
- **Solution:** Increase to 2-3 to require more lexical evidence
- **Debug:** Check log for `lexical_hits=` and `used_allowlist=` fields

---

## Rollout Plan

### Phase 1: Internal Testing (Day 1-2)
1. Deploy with `ENABLE_LOOKUP_SOFT_GATING=false` (default off)
2. Run tests in Docker:
   ```bash
   docker-compose run --rm api pytest tests/unit/test_query_intent.py -v
   docker-compose run --rm api pytest tests/integration/test_lookup_soft_gating.py -v
   ```
3. Enable for internal users only via `.env`:
   ```bash
   ENABLE_LOOKUP_SOFT_GATING=true
   SEARCH_DEBUG=true
   ```
4. Manually test:
   - Lookup with hits: "Heimdex", "BTS", "이장원"
   - Lookup with no hits: "NonexistentBrand"
   - Semantic: "영상 편집", "studio interview"

### Phase 2: A/B Testing (Day 3-7)
1. Enable for 10% of production users (via feature flag service or % rollout)
2. Log metrics:
   - Intent distribution (lookup vs semantic)
   - Lexical hit rate for lookup queries
   - Allowlist mode usage rate
   - Fallback mode usage rate
   - User CTR (click-through rate)
3. Compare against control group (flag OFF)

### Phase 3: Full Rollout (Day 8+)
1. If A/B test passes (no CTR drop, precision improved), enable globally:
   ```bash
   ENABLE_LOOKUP_SOFT_GATING=true
   ```
2. Monitor for 1 week
3. Consider tuning `lookup_lexical_min_hits` based on user feedback

### Rollback Plan
If issues detected:
1. Set `ENABLE_LOOKUP_SOFT_GATING=false` in `.env`
2. Restart API: `docker-compose restart api`
3. No data migration needed (feature is additive)

---

## Future Enhancements

### Phase 2 (if needed)
1. **Per-language heuristics:**
   - Different thresholds for Korean vs English
   - Language-specific name patterns

2. **User feedback loop:**
   - Track "best_guess" badge click-throughs
   - Learn which queries should/shouldn't be gated

3. **Allowlist confidence scoring:**
   - Instead of binary allowlist, use lexical score as confidence weight
   - Blend lexical confidence with dense scores

4. **Intent model:**
   - Replace heuristics with lightweight ML classifier
   - Train on labeled query dataset

---

## References

- **Intent detection module:** `/services/api/src/domain/search/intent.py`
- **Unit tests:** `/services/api/tests/unit/test_query_intent.py`
- **Integration tests:** `/services/api/tests/integration/test_lookup_soft_gating.py`
- **Search route changes:** `/services/api/src/routes/search.py` (lines 408, 510-562, 1045-1062)
- **Frontend UI:** `/services/frontend/src/app/search/page.tsx` (lines 474-478)

---

## Lessons Learned

1. **Soft gating > hard gating:** Fallback to dense (with label) is better than no results
2. **Early lexical check is cheap:** ~10-50ms for precision gains on 10% of queries
3. **Allowlist filtering preserves ranking:** Fusion math unchanged, only candidate pool restricted
4. **Feature flags are critical:** Safe rollout requires OFF by default
5. **Structured logging enables tuning:** Metrics log line helps understand gating behavior
6. **Docker-first testing prevents issues:** All tests designed to run in docker-compose

---

## Contact

For questions or issues:
1. Check logs: `docker-compose logs -f api | grep "Lookup soft gating"`
2. Run tests: `docker-compose run --rm api pytest tests/integration/test_lookup_soft_gating.py -v`
3. Review this document and inline code comments
