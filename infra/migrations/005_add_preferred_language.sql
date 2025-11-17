-- Add preferred_language field to user_profiles
-- This allows users to choose their preferred language for embeddings and summaries
-- Supported languages: 'ko' (Korean), 'en' (English)
-- Default: 'ko' (Korean)

ALTER TABLE user_profiles
  ADD COLUMN preferred_language TEXT NOT NULL DEFAULT 'ko'
  CHECK (preferred_language IN ('ko', 'en'));

-- Create index for potential language-based queries
CREATE INDEX idx_user_profiles_preferred_language ON user_profiles(preferred_language);

-- Add comment for documentation
COMMENT ON COLUMN user_profiles.preferred_language IS 'User''s preferred language for video embeddings and summaries. Supported: ko (Korean), en (English). Default: ko';
