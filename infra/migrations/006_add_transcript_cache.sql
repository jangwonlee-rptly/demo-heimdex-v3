-- Add transcript cache column to videos table
-- This stores the full transcript to avoid re-running expensive Whisper API calls on retry
-- The transcript is used as a checkpoint during video processing

ALTER TABLE videos
  ADD COLUMN full_transcript TEXT;

-- Add comment for documentation
COMMENT ON COLUMN videos.full_transcript IS 'Cached full video transcript from Whisper. Used as checkpoint during processing to avoid re-transcription on retry.';

-- Create index for potential queries
CREATE INDEX idx_videos_full_transcript ON videos(id) WHERE full_transcript IS NOT NULL;
