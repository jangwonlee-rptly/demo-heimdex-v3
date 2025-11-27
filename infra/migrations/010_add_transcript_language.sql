-- Add transcript language override column for reprocessing with explicit language
-- This allows users to specify the correct language when Whisper auto-detection fails

-- Add transcript_language column to videos table
-- NULL means auto-detect (default Whisper behavior)
-- A value like 'ko', 'en', 'ja' forces that language for transcription
ALTER TABLE videos
ADD COLUMN IF NOT EXISTS transcript_language VARCHAR(10) DEFAULT NULL;

-- Comment the column for documentation
COMMENT ON COLUMN videos.transcript_language IS 'ISO-639-1 language code for forced transcription language (NULL = auto-detect)';
