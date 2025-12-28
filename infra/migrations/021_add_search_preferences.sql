-- Migration: Add search preferences to user_profiles
-- Date: 2025-12-28
-- Description: Add search_preferences JSONB column to store user's customized search weights

-- Add search_preferences column to user_profiles
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS search_preferences JSONB;

-- Create GIN index for efficient querying of JSONB fields
CREATE INDEX IF NOT EXISTS idx_user_profiles_search_prefs
ON user_profiles USING GIN (search_preferences);

-- Add comment explaining the schema
COMMENT ON COLUMN user_profiles.search_preferences IS 'User''s saved search preferences including channel weights, fusion method, and visual mode.
Example: {
  "weights": {"transcript": 0.5, "visual": 0.3, "summary": 0.1, "lexical": 0.1},
  "fusion_method": "minmax_mean",
  "visual_mode": "auto",
  "version": 1
}';

-- No migration for existing rows - NULL is acceptable default
-- Users will only have preferences when they explicitly save them
