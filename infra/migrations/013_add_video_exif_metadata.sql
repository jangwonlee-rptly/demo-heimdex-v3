-- Add EXIF metadata support for videos
-- This allows storing rich metadata like GPS location, camera info, etc.
-- Enables searches like "vlog from last year at Paris"

-- EXIF metadata is stored as JSONB for flexibility
-- Not all videos have all fields, and new fields can be added without schema changes
-- Format: {
--   "gps": {
--     "latitude": 48.8566,
--     "longitude": 2.3522,
--     "altitude": 35.0,
--     "location_name": "Paris, France"
--   },
--   "camera": {
--     "make": "Apple",
--     "model": "iPhone 15 Pro",
--     "software": "17.1.1"
--   },
--   "recording": {
--     "iso": 100,
--     "focal_length": 6.86,
--     "aperture": 1.78,
--     "white_balance": "auto"
--   },
--   "other": {
--     "artist": "John Doe",
--     "copyright": "2024 John Doe",
--     "orientation": 1,
--     "content_identifier": "uuid-or-hash"
--   }
-- }

ALTER TABLE videos
  ADD COLUMN exif_metadata JSONB DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN videos.exif_metadata IS 'Video EXIF metadata including GPS coordinates, camera info, recording settings. Extracted from video file metadata using ffprobe/exiftool. NULL if no metadata available.';

-- Create GIN index for JSONB queries (enables queries on nested fields)
CREATE INDEX idx_videos_exif_metadata ON videos USING GIN (exif_metadata);

-- Add separate columns for commonly-queried location fields for efficient filtering
-- These are denormalized from exif_metadata for better query performance
ALTER TABLE videos
  ADD COLUMN location_latitude DOUBLE PRECISION DEFAULT NULL,
  ADD COLUMN location_longitude DOUBLE PRECISION DEFAULT NULL,
  ADD COLUMN location_name TEXT DEFAULT NULL,
  ADD COLUMN camera_make TEXT DEFAULT NULL,
  ADD COLUMN camera_model TEXT DEFAULT NULL;

-- Comments for documentation
COMMENT ON COLUMN videos.location_latitude IS 'GPS latitude extracted from EXIF. Denormalized for query performance.';
COMMENT ON COLUMN videos.location_longitude IS 'GPS longitude extracted from EXIF. Denormalized for query performance.';
COMMENT ON COLUMN videos.location_name IS 'Reverse-geocoded location name (city, country). Denormalized for query performance.';
COMMENT ON COLUMN videos.camera_make IS 'Camera manufacturer (Apple, Samsung, Sony, etc.). Denormalized for query performance.';
COMMENT ON COLUMN videos.camera_model IS 'Camera model (iPhone 15 Pro, Galaxy S24, etc.). Denormalized for query performance.';

-- Create indexes for location-based queries
CREATE INDEX idx_videos_location ON videos(location_latitude, location_longitude) WHERE location_latitude IS NOT NULL;
CREATE INDEX idx_videos_location_name ON videos(location_name) WHERE location_name IS NOT NULL;
CREATE INDEX idx_videos_camera ON videos(camera_make, camera_model) WHERE camera_make IS NOT NULL;
