# Display Score Calibration Implementation

## Overview

This document describes the implementation of per-query score calibration for UI display. The feature adds a `display_score` field to search results that is calibrated to avoid overconfident "100%" displays while preserving ranking order.

## Problem Statement

**Issue:** Per-query min-max normalization always assigns `1.0` to the top-ranked result in each channel, leading to overconfident "100%" displays even for mediocre matches (e.g., query "heimdex" with actual cosine similarity of 0.65 shows as "100%").

**Solution:** Add post-fusion calibration that transforms fused scores into display scores using exponential squashing, capping at ~97% to indicate uncertainty while preserving ranking.

---

## Implementation Summary

### Files Modified/Created

#### Backend (API)
1. **`/services/api/src/domain/search/display_score.py`** (NEW)
   - Core calibration logic
   - Implements `calibrate_display_scores()` with two methods:
     - `exp_squash` (recommended): Exponential squashing `y = 1 - exp(-alpha * x)`
     - `pctl_ceiling`: Percentile-based ceiling normalization

2. **`/services/api/src/domain/schemas.py`**
   - Added `display_score: Optional[float]` field to `VideoSceneResponse`
   - Description: "Per-query calibrated score for UI display (0..1, capped at 0.95-0.97)"

3. **`/services/api/src/config.py`**
   - Added feature flag settings:
     - `enable_display_score_calibration: bool = False`
     - `display_score_method: str = "exp_squash"`
     - `display_score_max_cap: float = 0.97`
     - `display_score_alpha: float = 3.0`

4. **`/services/api/src/routes/search.py`**
   - Lines 775-802: Post-fusion calibration logic
   - Lines 250-255: Updated `_hydrate_scenes()` signature to accept `display_score_map`
   - Lines 315: Added `display_score` to response construction

#### Frontend
5. **`/services/frontend/src/types/index.ts`**
   - Added `display_score?: number` to `VideoScene` interface

6. **`/services/frontend/src/app/search/page.tsx`**
   - Line 469-473: Updated score rendering to prefer `display_score` over `similarity`
   - Uses fallback chain: `scene.display_score ?? scene.similarity`

#### Tests
7. **`/services/api/tests/unit/test_display_score.py`** (NEW)
   - 40+ unit tests covering:
     - Edge cases (empty, single, flat distributions)
     - Monotonicity preservation
     - Max cap enforcement
     - Alpha tuning behavior

8. **`/services/api/tests/integration/test_display_score_integration.py`** (NEW)
   - Integration tests for:
     - Ranking stability
     - Feature flag behavior
     - Fusion + calibration pipeline
     - Empty/single result handling

---

## How It Works

### Calibration Algorithm (Exponential Squashing)

```python
# 1. Normalize scores to [0, 1] using min-max within the query result set
normalized = [(s - min(scores)) / (max(scores) - min(scores) + eps) for s in scores]

# 2. Apply exponential squashing to reduce overconfidence
squashed = [1.0 - exp(-alpha * x) for x in normalized]

# 3. Cap at max_cap (typically 0.97) to prevent 100% displays
display_scores = [min(max_cap, max(0.0, y)) for y in squashed]
```

**Key properties:**
- **Monotonic:** If `score_a > score_b`, then `display(a) >= display(b)` (ranking preserved)
- **Bounded:** All scores are in `[0, max_cap]`, never 1.0
- **Smooth:** Provides interpretable confidence gradient

### Integration into Search Pipeline

```
Search Request
    ↓
Generate embeddings (OpenAI + CLIP)
    ↓
Parallel retrieval (transcript, visual, summary, lexical)
    ↓
Fusion (multi_channel_minmax_fuse)
    ↓
[NEW] Display score calibration (if feature flag enabled)
    ↓
Hydrate scenes with metadata
    ↓
Return SearchResponse (with display_score field)
    ↓
Frontend renders display_score ?? similarity
```

---

## Configuration & Tuning

### Environment Variables

Add to `/services/api/.env`:

```bash
# Display score calibration (feature flag)
ENABLE_DISPLAY_SCORE_CALIBRATION=false  # Set to true to enable
DISPLAY_SCORE_METHOD=exp_squash          # Options: exp_squash, pctl_ceiling
DISPLAY_SCORE_MAX_CAP=0.97               # Maximum display score (0.95-0.99)
DISPLAY_SCORE_ALPHA=3.0                  # Exponential squashing parameter (2.0-5.0)
```

### Tuning `alpha` Parameter

Controls how aggressively scores are compressed:

| Alpha | Top Score Behavior | Use Case |
|-------|-------------------|----------|
| 2.0   | Gentle squashing (~86% of max_cap) | When you want minimal change from fused scores |
| 3.0   | Moderate squashing (~95% of max_cap) | **Recommended** - balanced confidence |
| 5.0   | Aggressive squashing (~99% of max_cap) | When you want to maximize top score display |

**Formula:** For normalized score `x=1.0`, `display = 1 - exp(-alpha)`:
- alpha=2.0 → 0.86
- alpha=3.0 → 0.95
- alpha=5.0 → 0.99

Then multiply by `max_cap` (e.g., 0.97) for final value.

### Tuning `max_cap` Parameter

Caps the maximum display score:

| max_cap | Top Display | Use Case |
|---------|-------------|----------|
| 0.95    | 95%         | Conservative - emphasize uncertainty |
| 0.97    | 97%         | **Recommended** - balanced |
| 0.99    | 99%         | Optimistic - minimal adjustment |

---

## Testing

### Run Unit Tests (Docker)

```bash
# In services/api container
docker-compose run api pytest tests/unit/test_display_score.py -v
```

Expected output:
```
test_empty_list PASSED
test_single_score_neutral PASSED
test_flat_distribution_all_equal PASSED
test_monotonic_increasing PASSED
test_extremes_min_near_zero PASSED
test_extremes_max_near_cap PASSED
test_never_reaches_100 PASSED
...
40 tests passed
```

### Run Integration Tests (Docker)

```bash
# In services/api container
docker-compose run api pytest tests/integration/test_display_score_integration.py -v
```

Or run standalone:
```bash
docker-compose run api python tests/integration/test_display_score_integration.py
```

### Manual Testing

1. **Enable feature flag:**
   ```bash
   # In services/api/.env
   ENABLE_DISPLAY_SCORE_CALIBRATION=true
   DISPLAY_SCORE_METHOD=exp_squash
   DISPLAY_SCORE_MAX_CAP=0.97
   DISPLAY_SCORE_ALPHA=3.0
   SEARCH_DEBUG=true  # Optional: see calibration logs
   ```

2. **Restart API:**
   ```bash
   docker-compose restart api
   ```

3. **Test query (e.g., "heimdex"):**
   ```bash
   curl -X POST http://localhost:8000/search \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -d '{
       "query": "heimdex",
       "limit": 10
     }'
   ```

4. **Verify response:**
   ```json
   {
     "results": [
       {
         "id": "...",
         "score": 1.0,           // Ranking score (unchanged)
         "similarity": 1.0,       // Legacy field (unchanged)
         "display_score": 0.954,  // NEW: Calibrated for display
         "...": "..."
       }
     ]
   }
   ```

5. **Check frontend:**
   - Open search UI at `http://localhost:3000/search`
   - Query "heimdex"
   - Verify top result shows ~95% instead of 100%

---

## Acceptance Criteria

✅ **With flag OFF:**
- API response unchanged (no `display_score` field)
- Frontend renders `similarity` (backward compatible)
- No breaking changes for existing clients

✅ **With flag ON:**
- API returns `display_score` in `[0, max_cap]` for all results
- `display_score` is always <= `max_cap` (never 1.0)
- Frontend prefers `display_score` over `similarity`

✅ **Ranking stability:**
- Scene ordering is **identical** regardless of flag state
- `score` field (used for ranking) is **unchanged**
- Only `display_score` is added/modified

✅ **Typical behavior:**
- Query "heimdex" with top-k=20:
  - Before: Top result = 100%
  - After: Top result = ~95-97% (with alpha=3.0, max_cap=0.97)

---

## Rollout Plan

### Phase 1: Internal Testing (Day 1-2)
1. Deploy with `ENABLE_DISPLAY_SCORE_CALIBRATION=false` (default off)
2. Enable for internal users only
3. Verify:
   - No performance degradation
   - Scores look reasonable (not too low)
   - No ranking changes observed

### Phase 2: A/B Test (Day 3-7)
1. Enable for 10% of users
2. Log metrics:
   - `display_score` distribution
   - User click-through rate (CTR)
   - User feedback on result quality
3. Compare against control group (flag off)

### Phase 3: Full Rollout (Day 8+)
1. If A/B test passes (no CTR drop), enable globally
2. Update documentation
3. Monitor for 1 week

### Rollback Plan
If issues detected:
1. Set `ENABLE_DISPLAY_SCORE_CALIBRATION=false` in `.env`
2. Restart API: `docker-compose restart api`
3. Frontend automatically falls back to `similarity`

---

## Performance Impact

### Computational Cost
- **Per-query overhead:** ~0.5-1ms for calibration (negligible)
  - Algorithm: O(n) where n = top_k (typically 10-50)
  - Operations: min/max, normalize, exp(), clamp
- **No database impact:** Pure in-memory computation
- **No caching needed:** Fast enough to compute on every request

### Memory Impact
- **Additional memory:** ~400 bytes per search result
  - `display_score_map: dict[str, float]` with ~50 entries
- **Negligible for typical workloads**

---

## Debugging

### Enable Debug Logging

```bash
# In services/api/.env
SEARCH_DEBUG=true
ENABLE_DISPLAY_SCORE_CALIBRATION=true
```

Check logs:
```bash
docker-compose logs -f api | grep "Display score calibration"
```

Expected output:
```
[INFO] Display score calibration: method=exp_squash, max_cap=0.97, alpha=3.0, range=[0.1245, 0.9543]
```

### Common Issues

**Issue 1: Display scores all identical**
- **Cause:** Flat score distribution (all fused scores equal)
- **Solution:** This is expected behavior (neutral ~0.5)
- **Check:** Verify input `fused_scores` are not all the same

**Issue 2: Top score is 1.0**
- **Cause:** Feature flag disabled or max_cap=1.0
- **Solution:** Check `ENABLE_DISPLAY_SCORE_CALIBRATION=true` and `DISPLAY_SCORE_MAX_CAP<1.0`

**Issue 3: Ranking changed**
- **Cause:** Bug in calibration implementation (should never happen)
- **Solution:** Run unit tests to verify monotonicity
- **Check:** Compare `scene_id` order before/after calibration

---

## Why Exponential Squashing?

### Alternatives Considered

1. **Percentile normalization** (implemented as `pctl_ceiling`)
   - Pro: Simple, intuitive
   - Con: Sensitive to outliers in small result sets

2. **Z-score + sigmoid**
   - Pro: Handles outliers well
   - Con: Requires mean/std (unstable for small top_k)

3. **Min-max with absolute floor**
   - Pro: Preserves absolute similarity
   - Con: Doesn't solve overconfidence issue

4. **Exponential squashing** (chosen)
   - ✅ Smooth, interpretable confidence scaling
   - ✅ Stable for small top_k (5-50)
   - ✅ Tunable via single `alpha` parameter
   - ✅ Never produces 1.0 (always < max_cap)

### Mathematical Properties

```
y = min(max_cap, 1 - exp(-alpha * x))

where x = normalized score in [0, 1]
```

**Properties:**
- `y(0) = 0` (minimum input → 0 output)
- `y(1) ≈ max_cap` (maximum input → near max_cap)
- `dy/dx > 0` for all x (strictly increasing → monotonic)
- `d²y/dx² < 0` (concave → diminishing returns)

**Intuition:** Early confidence increases are easy (0.5 → 0.7), but pushing to high confidence (0.9 → 0.95) requires much stronger signal.

---

## Future Enhancements

### Phase 2 (if needed)

1. **Per-channel calibration**
   - Calibrate each channel separately before fusion
   - Useful if channels have different score distributions

2. **Global calibration stats**
   - Track percentile stats across all queries (7-day window)
   - Use for more stable calibration (less query-dependent)

3. **User-specific calibration**
   - Learn user's click patterns
   - Adjust `alpha` per user (e.g., expert vs novice)

4. **A/B testing framework**
   - Support multiple calibration methods simultaneously
   - Log method used for analytics

---

## References

- **Original issue:** Per-query min-max normalization causes overconfident 100% displays
- **Implementation doc:** `/Users/jangwonlee/Projects/demo-heimdex-v3/DISPLAY_SCORE_IMPLEMENTATION.md`
- **Calibration module:** `/services/api/src/domain/search/display_score.py`
- **Unit tests:** `/services/api/tests/unit/test_display_score.py`
- **Integration tests:** `/services/api/tests/integration/test_display_score_integration.py`

---

## Contact

For questions or issues:
1. Check logs: `docker-compose logs -f api | grep calibration`
2. Run tests: `docker-compose run api pytest tests/unit/test_display_score.py -v`
3. Review this document and inline code comments
