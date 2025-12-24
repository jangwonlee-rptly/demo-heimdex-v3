# Heimdex Admin Metrics - Phase 2 Implementation Summary

**Date:** 2025-12-23
**Status:** ✅ Complete - Ready for Deployment
**Goal:** Upgrade admin metrics to support precise performance tracking, RTF calculation, and failure attribution

---

## Table of Contents

1. [Overview](#overview)
2. [What Changed in Phase 2](#what-changed-in-phase-2)
3. [Metrics Now Available](#metrics-now-available)
4. [What's Precise vs. Approximate](#whats-precise-vs-approximate)
5. [Deployment Instructions](#deployment-instructions)
6. [API Endpoints](#api-endpoints)
7. [Database Schema Changes](#database-schema-changes)
8. [Worker Instrumentation](#worker-instrumentation)
9. [Backfill Strategy](#backfill-strategy)
10. [Testing the Implementation](#testing-the-implementation)
11. [Phase 2 vs. Phase 1 Comparison](#phase-2-vs-phase-1-comparison)

---

## Overview

Phase 1 delivered approximate admin metrics using existing schema (`updated_at` as proxy for completion time).
**Phase 2** adds precise timing instrumentation to enable:

- **Processing duration** percentiles (p50/p95/p99)
- **RTF (Real-Time Factor)** = processing_time / video_duration
- **Queue vs Run time** separation for capacity planning
- **Failure attribution** by processing stage
- **Precise throughput** using actual completion timestamps

---

## What Changed in Phase 2

### 1. Database Schema (Migration 019)

Added 5 new columns to `videos` table:

| Column | Type | Purpose |
|--------|------|---------|
| `queued_at` | TIMESTAMPTZ | When job was enqueued (for queue time) |
| `processing_started_at` | TIMESTAMPTZ | When worker began processing |
| `processing_finished_at` | TIMESTAMPTZ | When processing completed (success/failure) |
| `processing_duration_ms` | INTEGER | Total processing time in milliseconds |
| `processing_stage` | TEXT | Last active stage (for failure attribution) |

**Indexes added:**
- `idx_videos_processing_finished_at` - For throughput queries
- `idx_videos_processing_duration_ms` - For percentile queries
- `idx_videos_processing_stage` - For failure analysis

### 2. Worker Instrumentation

The worker now tracks timing at major boundaries:

```python
# Start of processing
processing_started_at = datetime.utcnow()
db.update_video_processing_start(video_id, processing_started_at)

# Stage updates
db.update_video_processing_stage(video_id, "downloading")
db.update_video_processing_stage(video_id, "metadata")
db.update_video_processing_stage(video_id, "scene_detection")
db.update_video_processing_stage(video_id, "transcription")
db.update_video_processing_stage(video_id, "scene_processing")
db.update_video_processing_stage(video_id, "finalizing")

# Completion
processing_finished_at = datetime.utcnow()
processing_duration_ms = int((processing_finished_at - processing_started_at).total_seconds() * 1000)
db.update_video_processing_finish(video_id, processing_finished_at, processing_duration_ms, "completed")
```

**Stage values:**
- `queued` - Job enqueued
- `downloading` - Downloading video from storage
- `metadata` - Extracting video metadata
- `scene_detection` - Running scene detection
- `transcription` - Running Whisper transcription
- `scene_processing` - Processing scenes (vision + embeddings)
- `indexing` - Indexing to OpenSearch
- `finalizing` - Final cleanup and status update
- `completed` - Processing succeeded
- `failed` - Processing failed

### 3. Database RPC Functions (Migration 020)

Added 5 new PostgreSQL functions:

1. **`get_admin_processing_latency(days)`** - p50/p95/p99 processing time + queue time
2. **`get_admin_rtf_distribution(days)`** - RTF percentiles and averages
3. **`get_admin_queue_analysis(days)`** - Queue vs processing time breakdown
4. **`get_admin_failures_by_stage(days)`** - Failures grouped by stage
5. **`get_admin_throughput_timeseries_v2(days)`** - Enhanced throughput with precise timing

### 4. API Endpoints

Added 5 new admin endpoints:

- `GET /v1/admin/performance/latency?range=30d`
- `GET /v1/admin/performance/rtf?range=30d`
- `GET /v1/admin/performance/queue?range=30d`
- `GET /v1/admin/failures/by-stage?range=30d`
- `GET /v1/admin/timeseries/throughput-v2?range=30d`

---

## Metrics Now Available

### Performance Metrics

**Processing Latency:**
- p50 (median), p95, p99 processing time in milliseconds
- Average queue time (how long jobs wait before worker picks them up)
- Average total time (queue + processing)

**RTF (Real-Time Factor):**
- RTF = `processing_duration_seconds / video_duration_seconds`
- Example: RTF of 2.0 means it takes 2 seconds to process each second of video
- Lower is better (RTF < 1.0 means faster than real-time)
- Percentiles: p50, p95, p99

**Queue Analysis:**
- Average queue time vs. average processing time
- Percentage breakdown (queue time vs. processing time)
- Helps identify if bottleneck is in queuing or processing

### Reliability Metrics

**Failures by Stage:**
- Count and percentage of failures at each processing stage
- Example output:
  ```json
  {
    "data": [
      {"processing_stage": "transcription", "failure_count": 15, "failure_pct": 45.5},
      {"processing_stage": "scene_detection", "failure_count": 10, "failure_pct": 30.3},
      {"processing_stage": "scene_processing", "failure_count": 8, "failure_pct": 24.2}
    ]
  }
  ```

### Throughput Metrics (Enhanced)

**Enhanced Time Series:**
- Videos completed per day (using `processing_finished_at` not `updated_at`)
- Videos failed per day
- Hours of video processed per day
- **NEW:** Average processing time per day
- **NEW:** Average RTF per day

---

## What's Precise vs. Approximate

### ✅ PRECISE (Phase 2 with new instrumentation)

All videos processed **after** Phase 2 deployment will have:

- ✅ **Exact processing duration** (worker-measured)
- ✅ **Exact queue time** (enqueue timestamp - processing start)
- ✅ **Exact RTF** (calculated from precise durations)
- ✅ **Failure stage attribution** (which stage failed)
- ✅ **Exact completion time** (`processing_finished_at` not `updated_at`)

### ⚠️ APPROXIMATE (Backfilled historical data)

Videos processed **before** Phase 2 deployment will have:

- ✅ **Completion time backfilled** from `updated_at` (good for throughput trends)
- ❌ **No processing duration** (NULL - cannot fabricate)
- ❌ **No queue time** (NULL - cannot fabricate)
- ❌ **No RTF** (NULL - requires duration)
- ❌ **No failure stage** (NULL - not tracked before Phase 2)

**Impact:**
- **Throughput charts** will include historical data (backfilled completion times)
- **Latency/RTF/Queue charts** will only show data from Phase 2 onward (correct behavior)
- **Failure attribution** will only work for failures that occur after Phase 2 deployment

---

## Deployment Instructions

### Step 1: Apply Migration 019 (Timing Columns)

```bash
cd /Users/jangwonlee/Projects/demo-heimdex-v3

# Local database
psql $DATABASE_URL -f infra/migrations/019_add_video_processing_timing.sql

# Production (Supabase SQL Editor)
# Copy/paste migration 019 and run
```

### Step 2: Apply Migration 020 (RPC Functions)

```bash
# Local database
psql $DATABASE_URL -f infra/migrations/020_add_admin_performance_rpc_functions.sql

# Production (Supabase SQL Editor)
# Copy/paste migration 020 and run
```

### Step 3: Deploy Code Changes

Phase 2 code changes are across 3 services:

**API Service (services/api/):**
- `src/adapters/database.py` - Added Phase 2 RPC methods
- `src/adapters/queue.py` - Sets `queued_at` when enqueuing
- `src/routes/admin.py` - Added 5 new endpoints
- `src/domain/admin_schemas.py` - Added Phase 2 response schemas

**Worker Service (services/worker/):**
- `src/adapters/database.py` - Added timing helper methods
- `src/domain/video_processor.py` - Instrumented with timing calls

**Deployment:**
```bash
# Docker Compose
docker-compose down
docker-compose up --build -d

# Railway (API)
git push railway main  # Auto-deploys

# Railway (Worker)
# Push to worker service repository or redeploy
```

### Step 4: Backfill Historical Data (Optional)

Backfills `processing_finished_at` from `updated_at` for existing videos:

```bash
cd services/api

# Dry run first
python3 -m src.scripts.backfill_video_timing --dry-run

# Execute backfill
python3 -m src.scripts.backfill_video_timing
```

**What gets backfilled:**
- ✅ `processing_finished_at` = `updated_at` (for throughput trends)

**What does NOT get backfilled:**
- ❌ `processing_started_at` (no precise data - remains NULL)
- ❌ `processing_duration_ms` (no precise data - remains NULL)
- ❌ `queued_at` (no precise data - remains NULL)

### Step 5: Verify Deployment

**Check migrations applied:**
```sql
-- Should show columns exist
\d videos
```

**Check RPC functions exist:**
```sql
-- Should list Phase 2 functions
\df get_admin_processing_latency
\df get_admin_rtf_distribution
\df get_admin_queue_analysis
\df get_admin_failures_by_stage
\df get_admin_throughput_timeseries_v2
```

**Test API endpoints:**
```bash
# Get JWT token from browser (after logging in as admin)
TOKEN="your-jwt-token"

# Test latency endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/performance/latency?range=7d

# Test RTF endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/performance/rtf?range=30d
```

---

## API Endpoints

### Phase 2 Endpoints

#### 1. Processing Latency

```http
GET /v1/admin/performance/latency?range=30d
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "videos_measured": 150,
  "avg_processing_ms": 45230.5,
  "p50_processing_ms": 42000.0,
  "p95_processing_ms": 78000.0,
  "p99_processing_ms": 95000.0,
  "avg_queue_ms": 1250.3,
  "avg_total_ms": 46480.8
}
```

#### 2. RTF Distribution

```http
GET /v1/admin/performance/rtf?range=30d
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "videos_measured": 150,
  "avg_rtf": 1.85,
  "p50_rtf": 1.75,
  "p95_rtf": 2.80,
  "p99_rtf": 3.20,
  "avg_video_duration_s": 180.5,
  "avg_processing_duration_s": 334.0
}
```

**Interpretation:**
- RTF of 1.75 (median) means it takes 1.75 seconds to process each second of video
- p95 of 2.80 means 95% of videos process at RTF <= 2.80

#### 3. Queue Analysis

```http
GET /v1/admin/performance/queue?range=30d
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "videos_measured": 150,
  "avg_queue_time_s": 1.25,
  "avg_processing_time_s": 45.2,
  "avg_total_time_s": 46.45,
  "queue_time_pct": 2.7,
  "processing_time_pct": 97.3
}
```

**Interpretation:**
- Only 2.7% of time is waiting in queue
- 97.3% of time is actual processing
- **Bottleneck is in processing, not queuing** (good worker saturation)

#### 4. Failures by Stage

```http
GET /v1/admin/failures/by-stage?range=30d
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "data": [
    {"processing_stage": "transcription", "failure_count": 8, "failure_pct": 53.3},
    {"processing_stage": "scene_detection", "failure_count": 4, "failure_pct": 26.7},
    {"processing_stage": "downloading", "failure_count": 3, "failure_pct": 20.0}
  ]
}
```

**Interpretation:**
- Most failures occur during transcription (53.3%)
- This suggests Whisper API issues or audio extraction problems

#### 5. Enhanced Throughput Time Series

```http
GET /v1/admin/timeseries/throughput-v2?range=14d
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "data": [
    {
      "day": "2025-12-23",
      "videos_ready": 45,
      "videos_failed": 2,
      "hours_ready": 8.5,
      "avg_processing_s": 42.3,
      "avg_rtf": 1.75
    },
    {
      "day": "2025-12-22",
      "videos_ready": 38,
      "videos_failed": 1,
      "hours_ready": 7.2,
      "avg_processing_s": 45.1,
      "avg_rtf": 1.82
    }
  ]
}
```

---

## Database Schema Changes

### Added Columns (Migration 019)

```sql
ALTER TABLE videos
ADD COLUMN queued_at TIMESTAMPTZ,
ADD COLUMN processing_started_at TIMESTAMPTZ,
ADD COLUMN processing_finished_at TIMESTAMPTZ,
ADD COLUMN processing_duration_ms INTEGER,
ADD COLUMN processing_stage TEXT;
```

### Added Indexes (Migration 019)

```sql
CREATE INDEX idx_videos_processing_finished_at
  ON videos(processing_finished_at)
  WHERE processing_finished_at IS NOT NULL;

CREATE INDEX idx_videos_processing_duration_ms
  ON videos(processing_duration_ms)
  WHERE processing_duration_ms IS NOT NULL;

CREATE INDEX idx_videos_processing_stage
  ON videos(processing_stage)
  WHERE status = 'FAILED';
```

**No breaking changes:**
- All columns are nullable (existing rows remain valid)
- No columns dropped or renamed
- No RLS policy changes

---

## Worker Instrumentation

### Timing Points

**Enqueue (API service):**
```python
# services/api/src/adapters/queue.py
queued_at = datetime.utcnow()
db.update_video_queued_at(video_id, queued_at)
process_video.send(str(video_id))
```

**Processing Start:**
```python
# services/worker/src/domain/video_processor.py
processing_started_at = datetime.utcnow()
db.update_video_processing_start(video_id, processing_started_at)
```

**Stage Updates:**
```python
db.update_video_processing_stage(video_id, "downloading")
db.update_video_processing_stage(video_id, "metadata")
db.update_video_processing_stage(video_id, "scene_detection")
db.update_video_processing_stage(video_id, "transcription")
db.update_video_processing_stage(video_id, "scene_processing")
db.update_video_processing_stage(video_id, "finalizing")
```

**Completion (Success):**
```python
processing_finished_at = datetime.utcnow()
processing_duration_ms = int((processing_finished_at - processing_started_at).total_seconds() * 1000)
db.update_video_processing_finish(video_id, processing_finished_at, processing_duration_ms, "completed")
```

**Completion (Failure):**
```python
processing_finished_at = datetime.utcnow()
processing_duration_ms = int((processing_finished_at - processing_started_at).total_seconds() * 1000)
db.update_video_processing_finish(video_id, processing_finished_at, processing_duration_ms, "failed")
```

---

## Backfill Strategy

### Safe Backfill

The backfill script ONLY sets `processing_finished_at = updated_at` for existing videos.

**What gets backfilled:**
```sql
UPDATE videos
SET processing_finished_at = updated_at
WHERE processing_finished_at IS NULL
  AND status IN ('READY', 'FAILED');
```

**What does NOT get backfilled:**
- `processing_started_at` - NULL (no precise data)
- `processing_duration_ms` - NULL (no precise data)
- `queued_at` - NULL (no precise data)

**Rationale:**
- Backfilling `processing_finished_at` enables historical throughput trends
- NOT backfilling durations prevents incorrect performance metrics
- Latency/RTF/Queue metrics will naturally populate as new videos process

**Run backfill:**
```bash
cd services/api
python3 -m src.scripts.backfill_video_timing --dry-run  # Preview
python3 -m src.scripts.backfill_video_timing             # Execute
```

---

## Testing the Implementation

### 1. Test Timing Instrumentation

**Process a new video:**
1. Upload a video through the frontend
2. Wait for processing to complete
3. Query the database:

```sql
SELECT
    id,
    status,
    queued_at,
    processing_started_at,
    processing_finished_at,
    processing_duration_ms,
    processing_stage,
    duration_s,
    (processing_duration_ms / 1000.0) / NULLIF(duration_s, 0) AS rtf
FROM videos
WHERE id = '<your-video-id>';
```

**Expected:**
- `queued_at` should be set (when job was enqueued)
- `processing_started_at` should be set (when worker started)
- `processing_finished_at` should be set (when processing completed)
- `processing_duration_ms` should match the time difference
- `processing_stage` should be 'completed' or 'failed'
- RTF should be calculated correctly

### 2. Test API Endpoints

**Processing Latency:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/performance/latency?range=7d
```

**RTF Distribution:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/performance/rtf?range=30d
```

**Queue Analysis:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/performance/queue?range=30d
```

**Failures by Stage:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/failures/by-stage?range=30d
```

### 3. Test RPC Functions Directly

```sql
-- Processing latency
SELECT * FROM get_admin_processing_latency(7);

-- RTF distribution
SELECT * FROM get_admin_rtf_distribution(30);

-- Queue analysis
SELECT * FROM get_admin_queue_analysis(30);

-- Failures by stage
SELECT * FROM get_admin_failures_by_stage(30);

-- Enhanced throughput
SELECT * FROM get_admin_throughput_timeseries_v2(14);
```

---

## Phase 2 vs. Phase 1 Comparison

| Feature | Phase 1 | Phase 2 |
|---------|---------|---------|
| **Completion Time** | Proxy (`updated_at`) | Precise (`processing_finished_at`) |
| **Processing Duration** | ❌ Not available | ✅ Worker-measured (ms) |
| **Queue Time** | ❌ Not available | ✅ Enqueue → Start |
| **RTF (Real-Time Factor)** | ❌ Not available | ✅ duration / video_duration |
| **Percentiles (p50/p95/p99)** | ❌ Not available | ✅ Processing time |
| **Failure Attribution** | ❌ Not available | ✅ By processing stage |
| **Throughput Precision** | Approximate | Precise |
| **Schema Changes** | None | 5 new columns |
| **RPC Functions** | 5 functions | 10 functions (5 new) |
| **API Endpoints** | 5 endpoints | 10 endpoints (5 new) |
| **Worker Changes** | None | Timing instrumentation |

---

## Known Limitations & Future Work

### Phase 2 Limitations (By Design)

1. **Per-stage timing not tracked** - Only last active stage recorded
2. **No file size tracking** - Storage metrics require schema changes
3. **No cost accounting** - Requires mapping timing to model costs
4. **Text-based failure stage** - No enum constraint (flexibility vs. safety trade-off)

### Future Enhancements (Phase 3+)

- **Cost Accounting:** Map processing time → GPU/model costs
- **Per-Stage Timing:** Track time spent in each stage
- **Storage Metrics:** Track file sizes for storage cost analysis
- **Alerting:** Automated alerts for anomalies (high RTF, queue buildup, failure spikes)
- **Capacity Planning:** Predictive models for worker scaling

---

## Summary

✅ **Phase 2 Complete** - All deliverables implemented:

1. ✅ Migration 019: Timing columns and indexes
2. ✅ Migration 020: Performance RPC functions
3. ✅ Worker instrumentation: Timing at all major boundaries
4. ✅ API endpoints: 5 new performance/reliability endpoints
5. ✅ Backfill script: Safe historical data backfill
6. ✅ Documentation: This comprehensive README

**Next Steps:**
1. Apply migrations to database
2. Deploy code changes (API + Worker)
3. Run backfill script (optional)
4. Test endpoints with real data
5. Monitor Phase 2 metrics as new videos process

**No Breaking Changes:**
- All schema changes are additive
- No RLS policy changes
- No user workflow disruptions
- Historical data preserved and backfilled

**Contact:** Phase 2 implementation complete - ready for production deployment.
