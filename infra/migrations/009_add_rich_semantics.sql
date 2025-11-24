-- Add rich visual semantics to scenes and video-level summaries
-- This migration supports the visual semantics v2 upgrade

-- Add columns to video_scenes table for rich semantics
ALTER TABLE video_scenes
ADD COLUMN IF NOT EXISTS visual_description TEXT,
ADD COLUMN IF NOT EXISTS visual_entities text[],
ADD COLUMN IF NOT EXISTS visual_actions text[],
ADD COLUMN IF NOT EXISTS tags text[];

-- Create GIN index on tags array for efficient tag filtering
CREATE INDEX IF NOT EXISTS idx_video_scenes_tags ON video_scenes USING GIN(tags);

-- Add columns to videos table for video-level summaries
ALTER TABLE videos
ADD COLUMN IF NOT EXISTS video_summary TEXT,
ADD COLUMN IF NOT EXISTS has_rich_semantics BOOLEAN DEFAULT FALSE;

-- Create index on has_rich_semantics for filtering old vs new videos
CREATE INDEX IF NOT EXISTS idx_videos_has_rich_semantics ON videos(has_rich_semantics);

-- Comment the columns for documentation
COMMENT ON COLUMN video_scenes.visual_description IS 'Richer 1-2 sentence description of the scene visual content';
COMMENT ON COLUMN video_scenes.visual_entities IS 'Array of main entities (people, objects, locations) detected in the scene';
COMMENT ON COLUMN video_scenes.visual_actions IS 'Array of actions happening in the scene';
COMMENT ON COLUMN video_scenes.tags IS 'Normalized, deduplicated tags combining entities and actions for filtering';
COMMENT ON COLUMN videos.video_summary IS 'AI-generated summary of the entire video based on scene descriptions';
COMMENT ON COLUMN videos.has_rich_semantics IS 'Flag indicating whether this video was processed with rich semantics (v2)';
