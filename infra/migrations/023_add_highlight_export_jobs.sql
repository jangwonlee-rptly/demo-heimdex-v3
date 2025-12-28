-- Migration: Add highlight_export_jobs table for Highlight Reel Builder feature
-- Created: 2025-12-28
-- Description: Tracks highlight reel export jobs that combine multiple scenes into a single video

-- Create highlight_export_jobs table
CREATE TABLE IF NOT EXISTS highlight_export_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Job status
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'done', 'error')),

    -- Request configuration (stores ordered scenes + options)
    request JSONB NOT NULL,

    -- Processing progress
    progress JSONB,  -- {stage: "cutting|concat|upload", done: N, total: M}

    -- Output metadata (populated on completion)
    output JSONB,  -- {storage_path, mp4_url, file_size_bytes, duration_s, resolution}

    -- Error information (populated on failure)
    error JSONB,  -- {message, detail, ffmpeg_stderr_tail}

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for efficient queries
CREATE INDEX idx_highlight_export_jobs_user_id ON highlight_export_jobs(user_id);
CREATE INDEX idx_highlight_export_jobs_status ON highlight_export_jobs(status);
CREATE INDEX idx_highlight_export_jobs_user_created ON highlight_export_jobs(user_id, created_at DESC);

-- GIN index for request JSONB (optional, for advanced queries)
CREATE INDEX idx_highlight_export_jobs_request ON highlight_export_jobs USING GIN (request);

-- Enable Row Level Security (RLS)
ALTER TABLE highlight_export_jobs ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own jobs
CREATE POLICY highlight_export_jobs_select_own ON highlight_export_jobs
    FOR SELECT
    USING (auth.uid() = user_id);

-- RLS Policy: Users can only insert their own jobs
CREATE POLICY highlight_export_jobs_insert_own ON highlight_export_jobs
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- RLS Policy: Users can only update their own jobs
CREATE POLICY highlight_export_jobs_update_own ON highlight_export_jobs
    FOR UPDATE
    USING (auth.uid() = user_id);

-- RLS Policy: Users can only delete their own jobs
CREATE POLICY highlight_export_jobs_delete_own ON highlight_export_jobs
    FOR DELETE
    USING (auth.uid() = user_id);

-- Create or replace function for auto-updating updated_at
CREATE OR REPLACE FUNCTION update_highlight_export_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto-updating updated_at
DROP TRIGGER IF EXISTS trigger_update_highlight_export_jobs_updated_at ON highlight_export_jobs;
CREATE TRIGGER trigger_update_highlight_export_jobs_updated_at
    BEFORE UPDATE ON highlight_export_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_highlight_export_jobs_updated_at();

-- Add comments for documentation
COMMENT ON TABLE highlight_export_jobs IS 'Tracks highlight reel export jobs that combine multiple video scenes into a single MP4 output';
COMMENT ON COLUMN highlight_export_jobs.request IS 'JSONB containing ordered scenes array, total_duration_s, scene_count, and optional title/options';
COMMENT ON COLUMN highlight_export_jobs.progress IS 'JSONB tracking processing progress: {stage, done, total}';
COMMENT ON COLUMN highlight_export_jobs.output IS 'JSONB containing output metadata: {storage_path, file_size_bytes, duration_s, resolution}';
COMMENT ON COLUMN highlight_export_jobs.error IS 'JSONB containing error details if job failed: {message, detail, ffmpeg_stderr_tail}';
