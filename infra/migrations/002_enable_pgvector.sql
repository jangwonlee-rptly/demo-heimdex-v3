-- Enable pgvector extension and add embedding column

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to video_scenes
-- Using 1536 dimensions for OpenAI text-embedding-3-small/large
ALTER TABLE video_scenes
ADD COLUMN embedding vector(1536);

-- Create vector similarity search index using HNSW
-- HNSW is better for larger datasets, but IVFFlat can also be used
-- For demo scale, HNSW with reasonable parameters
CREATE INDEX idx_video_scenes_embedding ON video_scenes
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Alternative: IVFFlat index (uncomment if preferred for very small datasets)
-- CREATE INDEX idx_video_scenes_embedding ON video_scenes
-- USING ivfflat (embedding vector_cosine_ops)
-- WITH (lists = 100);

-- Helper function for similarity search
-- Returns scenes similar to query embedding, ordered by cosine similarity
CREATE OR REPLACE FUNCTION search_scenes_by_embedding(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10,
    filter_video_id uuid DEFAULT NULL
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
    WHERE
        (filter_video_id IS NULL OR vs.video_id = filter_video_id)
        AND vs.embedding IS NOT NULL
        AND 1 - (vs.embedding <=> query_embedding) > match_threshold
    ORDER BY vs.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
