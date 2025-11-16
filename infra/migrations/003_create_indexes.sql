-- Additional indexes for query optimization

-- Composite index for video scenes lookup with ordering
CREATE INDEX idx_video_scenes_video_id_index ON video_scenes(video_id, index);

-- Index for video lookup by status and owner (for dashboard queries)
CREATE INDEX idx_videos_owner_status ON videos(owner_id, status, created_at DESC);

-- Partial index for failed videos (useful for debugging/monitoring)
CREATE INDEX idx_videos_failed ON videos(owner_id, created_at DESC)
WHERE status = 'FAILED';

-- Index for recent search queries analytics
CREATE INDEX idx_search_queries_user_created ON search_queries(user_id, created_at DESC);

-- Add some useful view for statistics (optional, but helpful)
CREATE OR REPLACE VIEW video_processing_stats AS
SELECT
    v.owner_id,
    COUNT(*) as total_videos,
    COUNT(*) FILTER (WHERE v.status = 'READY') as ready_videos,
    COUNT(*) FILTER (WHERE v.status = 'PROCESSING') as processing_videos,
    COUNT(*) FILTER (WHERE v.status = 'FAILED') as failed_videos,
    COUNT(*) FILTER (WHERE v.status = 'PENDING') as pending_videos,
    SUM(v.duration_s) FILTER (WHERE v.status = 'READY') as total_duration_s,
    COUNT(DISTINCT vs.id) as total_scenes
FROM videos v
LEFT JOIN video_scenes vs ON v.id = vs.video_id
GROUP BY v.owner_id;

-- Grant access to authenticated users
GRANT SELECT ON video_processing_stats TO authenticated;
