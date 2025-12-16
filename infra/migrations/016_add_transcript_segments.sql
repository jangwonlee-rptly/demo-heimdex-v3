-- Migration 016: Add transcript segments storage
-- Purpose: Store Whisper segment-level timestamps for accurate transcript-to-scene alignment
-- This enables timestamp-based transcript slicing instead of proportional character-based slicing

-- Add column to store Whisper segments with timestamps
ALTER TABLE videos
  ADD COLUMN transcript_segments JSONB;

-- Comment explaining the structure
COMMENT ON COLUMN videos.transcript_segments IS
  'Whisper segment-level transcription data with timestamps.
   Structure: [{"start": 0.0, "end": 3.5, "text": "Hello world"}, ...]
   Used for accurate time-aligned transcript extraction per scene.';

-- Index for efficient queries (GIN index for JSONB)
CREATE INDEX idx_videos_transcript_segments ON videos
  USING GIN (transcript_segments);

-- Partial index for videos that have segments
CREATE INDEX idx_videos_has_transcript_segments ON videos(id)
  WHERE transcript_segments IS NOT NULL;
