-- Add user_id filter to search function so users only see their own videos
-- This fixes the issue where users were seeing other users' videos in search results

CREATE OR REPLACE FUNCTION search_scenes_by_embedding(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10,
    filter_video_id uuid DEFAULT NULL,
    filter_user_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    video_id uuid,
    index int,
    start_s float,
    end_s float,
    transcript_segment text,
    visual_summary text,
    combined_text text,
    thumbnail_url text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        vs.id,
        vs.video_id,
        vs.index,
        vs.start_s,
        vs.end_s,
        vs.transcript_segment,
        vs.visual_summary,
        vs.combined_text,
        vs.thumbnail_url,
        1 - (vs.embedding <=> query_embedding) as similarity
    FROM video_scenes vs
    INNER JOIN videos v ON vs.video_id = v.id
    WHERE
        (filter_video_id IS NULL OR vs.video_id = filter_video_id)
        AND (filter_user_id IS NULL OR v.owner_id = filter_user_id)
        AND vs.embedding IS NOT NULL
        AND 1 - (vs.embedding <=> query_embedding) > match_threshold
    ORDER BY vs.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
