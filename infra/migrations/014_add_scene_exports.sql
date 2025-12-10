-- Migration: Add scene_exports table for YouTube Shorts export feature
-- Created: 2025-12-10
-- Description: Tracks scene export requests with rate limiting and expiration

-- Create scene_exports table
CREATE TABLE IF NOT EXISTS scene_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID NOT NULL REFERENCES video_scenes(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Export configuration
    aspect_ratio_strategy TEXT NOT NULL CHECK (aspect_ratio_strategy IN ('center_crop', 'letterbox', 'smart_crop')),
    output_quality TEXT NOT NULL CHECK (output_quality IN ('high', 'medium')),

    -- Processing status
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,

    -- Output metadata
    storage_path TEXT,
    file_size_bytes BIGINT,
    duration_s FLOAT,
    resolution TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours')
);

-- Create indexes for efficient queries
CREATE INDEX idx_scene_exports_scene_id ON scene_exports(scene_id);
CREATE INDEX idx_scene_exports_user_id ON scene_exports(user_id);
CREATE INDEX idx_scene_exports_status ON scene_exports(status);
CREATE INDEX idx_scene_exports_expires_at ON scene_exports(expires_at);
CREATE INDEX idx_scene_exports_created_at ON scene_exports(created_at);

-- Composite index for rate limiting queries (user + created_at)
CREATE INDEX idx_scene_exports_user_created ON scene_exports(user_id, created_at);

-- Enable Row Level Security (RLS)
ALTER TABLE scene_exports ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own exports
CREATE POLICY scene_exports_select_own ON scene_exports
    FOR SELECT
    USING (auth.uid() = user_id);

-- RLS Policy: Users can only insert their own exports
CREATE POLICY scene_exports_insert_own ON scene_exports
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- RLS Policy: Users can only update their own exports
CREATE POLICY scene_exports_update_own ON scene_exports
    FOR UPDATE
    USING (auth.uid() = user_id);

-- RLS Policy: Users can only delete their own exports
CREATE POLICY scene_exports_delete_own ON scene_exports
    FOR DELETE
    USING (auth.uid() = user_id);

-- Add comment for documentation
COMMENT ON TABLE scene_exports IS 'Tracks video scene exports for YouTube Shorts feature with 24-hour expiration';
COMMENT ON COLUMN scene_exports.aspect_ratio_strategy IS 'How to handle aspect ratio conversion: center_crop, letterbox, or smart_crop';
COMMENT ON COLUMN scene_exports.output_quality IS 'Video quality preset: high (8-10 Mbps) or medium (4-6 Mbps)';
COMMENT ON COLUMN scene_exports.expires_at IS 'Expiration timestamp (created_at + 24 hours). Files deleted by cleanup job after this time.';
