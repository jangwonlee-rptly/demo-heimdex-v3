# Bulk Video Reprocessing Guide

This guide walks you through reprocessing all existing videos with the new **Visual Semantics v2** features (tags + summaries).

## What This Does

Reprocessing will upgrade your existing videos with:
- **Richer scene descriptions**: 1-2 sentences instead of ultra-short summaries
- **Structured tags**: Extracted entities (people, objects, locations) and actions
- **Video-level summaries**: AI-generated 3-5 sentence summaries of the entire video
- **Queryable metadata**: Tags stored as PostgreSQL arrays for fast filtering

## Prerequisites

### 1. Apply Database Migration (REQUIRED)

The migration adds new columns to support Visual Semantics v2.

**Option A: Via Supabase Dashboard (Recommended)**

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor** (left sidebar)
3. Click **New Query**
4. Copy the contents of `infra/migrations/009_add_rich_semantics.sql`
5. Paste into the SQL editor
6. Click **Run** to execute the migration
7. Verify success: Check for confirmation message

**Option B: Via Supabase CLI**

```bash
# From project root
cd /home/ljin/Projects/demo-heimdex-v3

# Apply the migration
supabase migration up

# Verify migration was applied
supabase db status
```

**Verify Migration Success**

Run this query in Supabase SQL Editor to verify the new columns exist:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'video_scenes'
  AND column_name IN ('visual_description', 'visual_entities', 'visual_actions', 'tags');
```

You should see 4 rows returned.

### 2. Ensure Worker Service is Running

The worker service must be running to process the enqueued jobs.

```bash
# Check if worker is running
docker-compose ps worker

# Start worker if not running
docker-compose up -d worker

# Tail worker logs (recommended during reprocessing)
docker-compose logs -f worker
```

### 3. Check Redis Connection

```bash
# Verify Redis is running
docker-compose ps redis

# Test Redis connectivity
docker-compose exec redis redis-cli ping
# Should return: PONG
```

## Running the Reprocessing Script

### Dry Run (Preview Only)

Before actually reprocessing, do a dry run to see what will be reprocessed:

```bash
python scripts/reprocess_all_videos.py --dry-run
```

This will show:
- How many videos need reprocessing
- Filenames and IDs of videos to be reprocessed
- No actual jobs will be enqueued

### Reprocess All Videos

```bash
python scripts/reprocess_all_videos.py
```

This will:
- Query all videos with `status=READY` and `has_rich_semantics=false`
- Enqueue each video for reprocessing
- Log progress to the console

### Reprocess with Delay (Recommended for Many Videos)

Add a delay between enqueueing jobs to avoid overwhelming the worker:

```bash
# Add 2 second delay between jobs
python scripts/reprocess_all_videos.py --delay 2.0
```

### Reprocess Specific User's Videos Only

```bash
python scripts/reprocess_all_videos.py --owner-id <user-uuid>
```

## Monitoring Progress

### Watch Worker Logs

```bash
docker-compose logs -f worker
```

Look for:
- `Processing video <video_id>` - Video processing started
- `Step 8: Generating video summary` - Summary generation in progress
- `Video processing completed successfully` - Video done
- `Updated video metadata: video_summary=...` - Summary saved

### Check Redis Queue Depth

```bash
docker-compose exec redis redis-cli

# In Redis CLI:
LLEN video_processing
# Returns number of pending jobs in queue

# Exit Redis CLI
exit
```

### Check Database Status

Query to see how many videos have been upgraded:

```sql
-- Videos with rich semantics
SELECT COUNT(*) FROM videos WHERE has_rich_semantics = true;

-- Videos still needing reprocessing
SELECT COUNT(*) FROM videos WHERE status = 'READY' AND has_rich_semantics = false;

-- Recent video summaries
SELECT filename, video_summary, has_rich_semantics
FROM videos
WHERE has_rich_semantics = true
ORDER BY created_at DESC
LIMIT 5;
```

## Expected Processing Time

Processing time depends on video length and scene count:

- **Short video** (1-2 minutes, ~5 scenes): ~30-60 seconds
- **Medium video** (5-10 minutes, ~20 scenes): ~2-4 minutes
- **Long video** (20+ minutes, 50+ scenes): ~5-10 minutes

Factors affecting speed:
- OpenAI API latency (gpt-4o for scenes, gpt-4o-mini for summaries)
- Number of scenes per video
- Concurrent worker threads (default: 3 API calls at once)

## Cost Estimates

**Per Video:**
- Scene analysis: ~$0.01-0.05 per video (depending on scene count)
- Video summary: ~$0.0005 per video (gpt-4o-mini)
- Total: ~$0.01-0.05 per video

**Example:**
- 100 videos × $0.03 average = ~$3.00 total

## Troubleshooting

### Script Can't Connect to Redis

**Error**: `Connection refused to redis://redis:6379`

**Fix**: Make sure Redis is accessible. If running script from outside Docker:

```bash
# Update REDIS_URL in .env to use localhost
REDIS_URL=redis://localhost:6379/0
```

### Script Can't Connect to Supabase

**Error**: `supabase.exceptions.APIError: 401 Unauthorized`

**Fix**: Verify your `.env` file has correct Supabase credentials:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

### Worker Not Processing Jobs

**Error**: Jobs enqueued but worker not processing

**Fixes**:
1. Check worker logs: `docker-compose logs worker`
2. Restart worker: `docker-compose restart worker`
3. Verify worker is connected to Redis: Check logs for "Connected to Redis broker"

### Videos Stuck in PROCESSING Status

**Error**: Videos remain in PROCESSING status after long time

**Fixes**:
1. Check worker logs for errors
2. Manually reset video status:
   ```sql
   UPDATE videos
   SET status = 'READY', error_message = NULL
   WHERE id = '<video_id>';
   ```
3. Re-enqueue the video:
   ```bash
   python scripts/reprocess_all_videos.py --owner-id <owner_id>
   ```

### Migration Already Applied Error

**Error**: `ERROR: column "visual_description" already exists`

**Fix**: This is fine - the migration is already applied. The script uses `ADD COLUMN IF NOT EXISTS` so it's safe to run multiple times.

## Verifying Success

After reprocessing completes, verify in the frontend:

1. **Visit video details page**: Should see richer scene descriptions
2. **Check video summary**: Should appear on video details page (if video has scenes)
3. **Inspect scene tags**: Each scene should have `tags` array with entities and actions
4. **Old videos**: Should show "Reprocess hint" if they haven't been upgraded yet

## Rolling Back (If Needed)

If you want to revert the migration:

```sql
-- Remove new columns from video_scenes
ALTER TABLE video_scenes
DROP COLUMN IF EXISTS visual_description,
DROP COLUMN IF EXISTS visual_entities,
DROP COLUMN IF EXISTS visual_actions,
DROP COLUMN IF EXISTS tags;

-- Drop GIN index
DROP INDEX IF EXISTS idx_video_scenes_tags;

-- Remove new columns from videos
ALTER TABLE videos
DROP COLUMN IF EXISTS video_summary,
DROP COLUMN IF EXISTS has_rich_semantics;

-- Drop index
DROP INDEX IF EXISTS idx_videos_has_rich_semantics;
```

## Next Steps After Reprocessing

1. **Verify videos in UI**: Check a few videos to ensure summaries and tags are present
2. **Monitor costs**: Check OpenAI usage dashboard
3. **Implement tag filtering**: Add UI components to filter scenes by tags
4. **Add summary display**: Show video summaries on dashboard/search results
5. **Consider incremental reprocessing**: For failed videos or new features

## Support

If you encounter issues:
1. Check worker logs: `docker-compose logs worker`
2. Check API logs: `docker-compose logs api`
3. Verify migration was applied: Run verification SQL query
4. Review DEVLOG.txt for implementation details
