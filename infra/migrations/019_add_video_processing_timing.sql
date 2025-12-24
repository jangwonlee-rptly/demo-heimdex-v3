-- Migration 019: Add Video Processing Timing Fields (Phase 2)
--
-- Purpose: Enable precise performance metrics, RTF calculation, and failure attribution
-- for the admin dashboard. This migration adds timing columns to track the full lifecycle
-- of video processing jobs.
--
-- Phase 2 Goals:
-- - Accurate processing duration (p50/p95/p99)
-- - RTF (Real-Time Factor) = processing_duration / video_duration
-- - Queue vs Run time separation
-- - Failure stage attribution
-- - Throughput calculation (videos/hour, hours/hour)
--
-- Constraints:
-- - Additive only (no breaking changes)
-- - Worker writes, API reads
-- - Coarse-grained stage tracking (not per-frame)

-- Add timing columns to videos table
ALTER TABLE videos
ADD COLUMN queued_at TIMESTAMPTZ,
ADD COLUMN processing_started_at TIMESTAMPTZ,
ADD COLUMN processing_finished_at TIMESTAMPTZ,
ADD COLUMN processing_duration_ms INTEGER,
ADD COLUMN processing_stage TEXT;

-- Column semantics:
--
-- queued_at:
--   Timestamp when the video processing job was enqueued (task sent to Dramatiq).
--   Set by: API service when enqueuing job
--   Used for: Queue time calculation (processing_started_at - queued_at)
--
-- processing_started_at:
--   Timestamp when worker began processing this video.
--   Set by: Worker at start of process_video()
--   Used for: Processing duration calculation, queue time
--
-- processing_finished_at:
--   Timestamp when processing completed (success or failure).
--   Set by: Worker at end of process_video()
--   Used for: Accurate throughput metrics, completion time (replaces updated_at proxy)
--   Note: More precise than updated_at because it's explicitly set at completion
--
-- processing_duration_ms:
--   Total processing time in milliseconds.
--   Calculated as: int((processing_finished_at - processing_started_at).total_seconds() * 1000)
--   Set by: Worker at completion
--   Used for: Performance percentiles (p50/p95/p99), RTF calculation
--   Note: NULL for videos that haven't finished processing
--
-- processing_stage:
--   Last active processing stage (coarse-grained).
--   Values: 'queued', 'downloading', 'metadata', 'scene_detection', 'transcription',
--           'scene_processing', 'indexing', 'finalizing', 'completed', 'failed'
--   Set by: Worker at major pipeline boundaries
--   Used for: Failure attribution (which stage failed)
--   Note: Only tracks last stage, not full history

-- Add indexes for performance queries
CREATE INDEX idx_videos_processing_finished_at
  ON videos(processing_finished_at)
  WHERE processing_finished_at IS NOT NULL;

COMMENT ON INDEX idx_videos_processing_finished_at IS
  'Optimizes throughput time-series queries (videos completed per hour/day)';

CREATE INDEX idx_videos_processing_duration_ms
  ON videos(processing_duration_ms)
  WHERE processing_duration_ms IS NOT NULL;

COMMENT ON INDEX idx_videos_processing_duration_ms IS
  'Optimizes percentile queries (p50/p95/p99 processing time)';

-- Add index for failure analysis
CREATE INDEX idx_videos_processing_stage
  ON videos(processing_stage)
  WHERE status = 'FAILED';

COMMENT ON INDEX idx_videos_processing_stage IS
  'Optimizes failure-by-stage queries for reliability metrics';

-- Add column comments
COMMENT ON COLUMN videos.queued_at IS
  'When job was enqueued (for queue time calculation)';

COMMENT ON COLUMN videos.processing_started_at IS
  'When worker started processing (for duration calculation)';

COMMENT ON COLUMN videos.processing_finished_at IS
  'When processing completed - more precise than updated_at';

COMMENT ON COLUMN videos.processing_duration_ms IS
  'Total processing time in milliseconds (finished - started)';

COMMENT ON COLUMN videos.processing_stage IS
  'Last active stage (queued|downloading|metadata|scene_detection|transcription|scene_processing|indexing|finalizing|completed|failed)';

-- Backfill strategy for existing videos:
--
-- For videos already processed (status = READY or FAILED), we can approximate
-- processing_finished_at from updated_at, but we CANNOT fabricate processing_started_at
-- or processing_duration_ms without introducing incorrect data.
--
-- Safe backfill (run manually after migration):
--
-- UPDATE videos
-- SET processing_finished_at = updated_at
-- WHERE processing_finished_at IS NULL
--   AND status IN ('READY', 'FAILED');
--
-- This provides approximate completion times for historical data while keeping
-- duration/start times NULL (indicating they're not measured).
--
-- Going forward, all new videos will have precise timing from worker instrumentation.
