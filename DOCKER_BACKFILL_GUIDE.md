# Running Phase 2 Backfill in Docker

This guide explains how to run the Phase 2 video timing backfill script in your Docker environment.

---

## Prerequisites

1. **Docker Compose services running:**
   ```bash
   docker-compose up -d
   ```

2. **Migrations applied:**
   - Migration 019 (timing columns)
   - Migration 020 (RPC functions)

3. **Database accessible** from API container

---

## Quick Start

### Option 1: Using the Helper Script (Recommended)

The easiest way to run the backfill:

```bash
# From project root directory
./run-backfill.sh
```

**Dry run first (recommended):**
```bash
./run-backfill.sh --dry-run
```

### Option 2: Direct Docker Compose Command

```bash
# Dry run
docker-compose exec api python3 -m src.scripts.backfill_video_timing --dry-run

# Execute backfill
docker-compose exec api python3 -m src.scripts.backfill_video_timing
```

### Option 3: Interactive Shell

```bash
# Enter the API container
docker-compose exec api bash

# Run the script inside the container
python3 -m src.scripts.backfill_video_timing --dry-run
python3 -m src.scripts.backfill_video_timing
```

---

## Step-by-Step Guide

### Step 1: Verify Docker Services

Check that all services are running:

```bash
docker-compose ps
```

Expected output:
```
NAME                                    STATUS
demo-heimdex-v3-api-1                  Up
demo-heimdex-v3-worker-1               Up
demo-heimdex-v3-redis-1                Up
demo-heimdex-v3-opensearch-1           Up
```

### Step 2: Verify Database Connection

Test database connectivity from the API container:

```bash
docker-compose exec api python3 -c "from src.adapters.database import db; print('Database connected:', db.client is not None)"
```

Expected output:
```
Database connected: True
```

### Step 3: Check Migrations Applied

Verify that the timing columns exist:

```bash
docker-compose exec api python3 -c "
from src.adapters.database import db
result = db.client.table('videos').select('queued_at, processing_started_at, processing_finished_at, processing_duration_ms, processing_stage').limit(1).execute()
print('Timing columns exist:', True)
"
```

If this succeeds, migrations are applied correctly.

### Step 4: Run Dry Run

Preview what would be updated:

```bash
./run-backfill.sh --dry-run
```

Expected output:
```
========================================
Phase 2 Video Timing Backfill (Docker)
========================================

✓ Database connection OK

Running in DRY RUN mode (no changes will be made)

Running backfill script...

2025-12-23 15:30:00 - INFO - ============================================================
2025-12-23 15:30:00 - INFO - Phase 2 Video Timing Backfill Script
2025-12-23 15:30:00 - INFO - ============================================================
2025-12-23 15:30:00 - INFO - DRY RUN MODE - No changes will be made
2025-12-23 15:30:00 - INFO -
2025-12-23 15:30:01 - INFO - Querying videos that need backfilling...
2025-12-23 15:30:02 - INFO - Found 45 videos to backfill:
2025-12-23 15:30:02 - INFO -   - Videos with status READY or FAILED
2025-12-23 15:30:02 - INFO -   - Missing processing_finished_at timestamp
2025-12-23 15:30:02 - INFO -
2025-12-23 15:30:02 - INFO - Breakdown:
2025-12-23 15:30:02 - INFO -   - READY: 42 videos
2025-12-23 15:30:02 - INFO -   - FAILED: 3 videos
2025-12-23 15:30:02 - INFO -
2025-12-23 15:30:02 - INFO - DRY RUN: Would backfill processing_finished_at from updated_at
2025-12-23 15:30:02 - INFO - DRY RUN: Would NOT backfill processing_started_at or processing_duration_ms
2025-12-23 15:30:02 - INFO -          (those require precise measurement and cannot be fabricated)
2025-12-23 15:30:02 - INFO -
2025-12-23 15:30:02 - INFO - To execute the backfill, run without --dry-run flag
```

### Step 5: Execute Backfill

If the dry run looks good, run the actual backfill:

```bash
./run-backfill.sh
```

Expected output:
```
========================================
Phase 2 Video Timing Backfill (Docker)
========================================

✓ Database connection OK

Running backfill script...

2025-12-23 15:35:00 - INFO - ============================================================
2025-12-23 15:35:00 - INFO - Phase 2 Video Timing Backfill Script
2025-12-23 15:35:00 - INFO - ============================================================
2025-12-23 15:35:01 - INFO - Querying videos that need backfilling...
2025-12-23 15:35:02 - INFO - Found 45 videos to backfill:
2025-12-23 15:35:02 - INFO -   - Videos with status READY or FAILED
2025-12-23 15:35:02 - INFO -   - Missing processing_finished_at timestamp
2025-12-23 15:35:02 - INFO -
2025-12-23 15:35:02 - INFO - Breakdown:
2025-12-23 15:35:02 - INFO -   - READY: 42 videos
2025-12-23 15:35:02 - INFO -   - FAILED: 3 videos
2025-12-23 15:35:02 - INFO -
2025-12-23 15:35:02 - INFO - Executing backfill...
2025-12-23 15:35:02 - INFO - This will set processing_finished_at = updated_at for these videos
2025-12-23 15:35:02 - INFO -
2025-12-23 15:35:03 - INFO -   Progress: 45/45 videos updated...
2025-12-23 15:35:03 - INFO -
2025-12-23 15:35:03 - INFO - ✅ Backfill complete! Updated 45 videos
2025-12-23 15:35:03 - INFO -
2025-12-23 15:35:03 - INFO - What was backfilled:
2025-12-23 15:35:03 - INFO -   ✅ processing_finished_at = updated_at
2025-12-23 15:35:03 - INFO -
2025-12-23 15:35:03 - INFO - What was NOT backfilled (intentionally):
2025-12-23 15:35:03 - INFO -   ❌ processing_started_at (remains NULL - no precise data)
2025-12-23 15:35:03 - INFO -   ❌ processing_duration_ms (remains NULL - no precise data)
2025-12-23 15:35:03 - INFO -   ❌ queued_at (remains NULL - no precise data)
2025-12-23 15:35:03 - INFO -
2025-12-23 15:35:03 - INFO - Impact on Phase 2 metrics:
2025-12-23 15:35:03 - INFO -   - Throughput time series will now include historical data
2025-12-23 15:35:03 - INFO -   - Latency percentiles will only use newly processed videos (correct)
2025-12-23 15:35:03 - INFO -   - RTF calculations will only use newly processed videos (correct)
2025-12-23 15:35:03 - INFO -   - Queue analysis will only use newly processed videos (correct)
2025-12-23 15:35:03 - INFO -
2025-12-23 15:35:03 - INFO - Going forward, all new videos will have precise timing from worker instrumentation.

========================================
Backfill script completed
========================================
```

### Step 6: Verify Results

Check that videos were backfilled:

```bash
docker-compose exec api python3 -c "
from src.adapters.database import db
response = db.client.table('videos').select('id, status, processing_finished_at').is_('processing_finished_at', 'not.null').limit(5).execute()
print(f'Videos with processing_finished_at: {len(response.data)}')
for video in response.data[:3]:
    print(f\"  - {video['id']}: {video['status']} - {video['processing_finished_at']}\")
"
```

---

## Troubleshooting

### Issue: "API container is not running"

**Solution:** Start Docker Compose services:
```bash
docker-compose up -d
```

Wait a few seconds for services to fully start, then retry.

### Issue: "Cannot connect to database"

**Possible causes:**

1. **DATABASE_URL not set correctly**

   Check the environment variable:
   ```bash
   docker-compose exec api printenv DATABASE_URL
   ```

   Should output something like:
   ```
   postgresql://postgres:password@db.oxmfngfqmedbzgknyijj.supabase.co:5432/postgres
   ```

2. **Database not accessible**

   Test connection manually:
   ```bash
   docker-compose exec api python3 -c "
   from src.config import settings
   print('DATABASE_URL:', settings.database_url)
   "
   ```

3. **Migrations not applied**

   Apply migrations 019 and 020 first (see main README).

### Issue: "Module not found" errors

**Solution:** Rebuild the API container:
```bash
docker-compose down
docker-compose up --build -d
```

### Issue: Script runs but no videos found

This is normal if:
- All videos already have `processing_finished_at` set (backfill already run)
- No videos have been processed yet (database is empty)

Verify:
```bash
docker-compose exec api python3 -c "
from src.adapters.database import db
response = db.client.table('videos').select('status, processing_finished_at').execute()
total = len(response.data)
backfilled = len([v for v in response.data if v['processing_finished_at'] is not None])
print(f'Total videos: {total}')
print(f'Already backfilled: {backfilled}')
print(f'Need backfilling: {total - backfilled}')
"
```

### Issue: Permission denied on run-backfill.sh

**Solution:** Make the script executable:
```bash
chmod +x run-backfill.sh
```

---

## Manual SQL Verification

If you want to verify the backfill manually using SQL:

```sql
-- Count videos that need backfilling
SELECT COUNT(*) as needs_backfill
FROM videos
WHERE processing_finished_at IS NULL
  AND status IN ('READY', 'FAILED');

-- Count videos already backfilled
SELECT COUNT(*) as already_backfilled
FROM videos
WHERE processing_finished_at IS NOT NULL;

-- Show sample backfilled videos
SELECT
    id,
    status,
    updated_at,
    processing_finished_at,
    processing_finished_at = updated_at as is_backfilled
FROM videos
WHERE processing_finished_at IS NOT NULL
LIMIT 10;

-- Verify no fabricated data (should be NULL)
SELECT
    COUNT(*) FILTER (WHERE processing_started_at IS NOT NULL) as has_started_at,
    COUNT(*) FILTER (WHERE processing_duration_ms IS NOT NULL) as has_duration_ms,
    COUNT(*) FILTER (WHERE queued_at IS NOT NULL) as has_queued_at
FROM videos
WHERE processing_finished_at IS NOT NULL;
-- All three counts should be 0 for backfilled videos
```

---

## Alternative: Running Without Helper Script

If you prefer not to use the helper script:

```bash
# Dry run
docker-compose exec api python3 -m src.scripts.backfill_video_timing --dry-run

# Execute
docker-compose exec api python3 -m src.scripts.backfill_video_timing
```

---

## After Backfill

Once backfill is complete:

1. **Test Phase 2 endpoints:**
   ```bash
   # Get your JWT token from the browser (after logging in as admin)
   TOKEN="your-jwt-token-here"

   # Test latency endpoint
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/v1/admin/performance/latency?range=7d

   # Test enhanced throughput (should now include historical data)
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/v1/admin/timeseries/throughput-v2?range=30d
   ```

2. **Verify metrics in admin dashboard:**
   - Navigate to http://localhost:3000/admin
   - Throughput chart should now show historical data
   - Latency/RTF metrics will populate as new videos process

3. **Monitor new videos:**
   Process a new video and verify it has complete timing data:
   ```sql
   SELECT
       id,
       status,
       queued_at,
       processing_started_at,
       processing_finished_at,
       processing_duration_ms,
       processing_stage
   FROM videos
   WHERE created_at > NOW() - INTERVAL '1 hour'
   ORDER BY created_at DESC
   LIMIT 5;
   ```

---

## Summary

✅ **Three ways to run backfill in Docker:**

1. **Helper script (easiest):**
   ```bash
   ./run-backfill.sh [--dry-run]
   ```

2. **Docker Compose exec:**
   ```bash
   docker-compose exec api python3 -m src.scripts.backfill_video_timing [--dry-run]
   ```

3. **Interactive shell:**
   ```bash
   docker-compose exec api bash
   python3 -m src.scripts.backfill_video_timing [--dry-run]
   ```

**Always run `--dry-run` first to preview changes!**

---

## Support

If you encounter issues not covered here, check:
- `ADMIN_METRICS_PHASE2_README.md` - Full Phase 2 documentation
- Docker logs: `docker-compose logs api`
- Database logs: `docker-compose logs db`
