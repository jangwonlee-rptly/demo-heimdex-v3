-- Add sidecar v2 metadata fields for better tracking and future migrations
-- These fields support versioning, search optimization, and processing analytics

-- Add columns to video_scenes table for sidecar v2 metadata
ALTER TABLE video_scenes
ADD COLUMN IF NOT EXISTS sidecar_version TEXT DEFAULT 'v1',
ADD COLUMN IF NOT EXISTS search_text TEXT,
ADD COLUMN IF NOT EXISTS embedding_metadata JSONB,
ADD COLUMN IF NOT EXISTS needs_reprocess BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS processing_stats JSONB;

-- Create index on sidecar_version for filtering scenes that need reprocessing
CREATE INDEX IF NOT EXISTS idx_video_scenes_sidecar_version ON video_scenes(sidecar_version);

-- Create index on needs_reprocess for finding scenes that need attention
CREATE INDEX IF NOT EXISTS idx_video_scenes_needs_reprocess ON video_scenes(needs_reprocess) WHERE needs_reprocess = TRUE;

-- Comment the columns for documentation
COMMENT ON COLUMN video_scenes.sidecar_version IS 'Schema version of the sidecar (e.g., v1, v2) for migration tracking';
COMMENT ON COLUMN video_scenes.search_text IS 'Optimized text specifically for embedding generation (transcript-first)';
COMMENT ON COLUMN video_scenes.embedding_metadata IS 'JSON metadata about embedding: model, dimensions, input_text_hash, input_text_length';
COMMENT ON COLUMN video_scenes.needs_reprocess IS 'Flag indicating this scene may benefit from reprocessing with newer logic';
COMMENT ON COLUMN video_scenes.processing_stats IS 'JSON stats about sidecar generation: duration, transcript_length, visual_analysis_called, etc.';
