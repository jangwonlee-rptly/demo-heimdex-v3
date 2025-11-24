-- Enable Realtime for videos table
-- This allows clients to subscribe to database changes via Supabase Realtime

-- Enable realtime publication for the videos table
ALTER PUBLICATION supabase_realtime ADD TABLE videos;

-- Add comment for documentation
COMMENT ON TABLE videos IS 'Video metadata with realtime enabled for status updates';
