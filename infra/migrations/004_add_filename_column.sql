-- Add filename column to videos table
-- This stores the original uploaded filename for display purposes

ALTER TABLE videos ADD COLUMN filename TEXT;

-- Add comment
COMMENT ON COLUMN videos.filename IS 'Original filename of the uploaded video';
