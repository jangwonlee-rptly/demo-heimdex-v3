-- Add scene detector preferences to user_profiles
-- This allows users to store custom thresholds for different scene detection algorithms
-- The system will try multiple detectors and select the one that produces the most scenes

-- Scene detector preferences are stored as JSONB for flexibility in adding new detectors
-- Format: {
--   "adaptive": {"threshold": 3.0, "window_width": 2, "min_content_val": 15.0},
--   "content": {"threshold": 27.0},
--   "threshold": {"threshold": 27.0, "method": "CONTENT_AND_DELTA"},
--   "hash": {"threshold": 0.395, "size": 16, "lowpass": 2}
-- }
ALTER TABLE user_profiles
  ADD COLUMN scene_detector_preferences JSONB DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN user_profiles.scene_detector_preferences IS 'User-specific scene detection thresholds per algorithm. JSON format: {"adaptive": {...}, "content": {...}, etc.}. NULL means use system defaults.';

-- Create GIN index for potential JSONB queries
CREATE INDEX idx_user_profiles_scene_detector_preferences ON user_profiles USING GIN (scene_detector_preferences);
