-- Migration 015: Add Multi-Embedding Dense Retrieval Channels (Option B)
--
-- Adds per-channel embedding columns for transcript, visual, and summary channels
-- to enable multi-embedding dense retrieval with independent query vectors per channel.
--
-- Migration path: v2 → v3-multi
-- Backward compatibility: Maintains existing 'embedding' column for fallback

-- ============================================================================
-- 1. Add new embedding columns (1536 dims, same as existing embedding)
-- ============================================================================

ALTER TABLE video_scenes
    ADD COLUMN IF NOT EXISTS embedding_transcript vector(1536),
    ADD COLUMN IF NOT EXISTS embedding_visual vector(1536),
    ADD COLUMN IF NOT EXISTS embedding_summary vector(1536);

COMMENT ON COLUMN video_scenes.embedding_transcript IS
    'Embedding of transcript_segment only. NULL if transcript is empty/missing.';

COMMENT ON COLUMN video_scenes.embedding_visual IS
    'Embedding of visual_description + tags (space-joined). NULL if visual content is empty/missing.';

COMMENT ON COLUMN video_scenes.embedding_summary IS
    'Embedding of scene or video summary (optional). NULL if summary not available.';

-- ============================================================================
-- 2. Update embedding_version column to track multi-embedding schema
-- ============================================================================

-- Add embedding_version if it doesn't exist (should exist from migration 011)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'video_scenes' AND column_name = 'embedding_version'
    ) THEN
        ALTER TABLE video_scenes ADD COLUMN embedding_version TEXT;
    END IF;
END $$;

COMMENT ON COLUMN video_scenes.embedding_version IS
    'Embedding schema version: NULL/v1 (single embedding), v2 (optimized search_text), v3-multi (per-channel embeddings)';

-- ============================================================================
-- 3. Extend embedding_metadata to support per-channel metadata
-- ============================================================================

-- embedding_metadata structure (extended for v3-multi):
-- {
--   "channels": {
--     "transcript": {
--       "model": "text-embedding-3-small",
--       "dimensions": 1536,
--       "input_text_hash": "a3f2e9b...",
--       "input_text_length": 245,
--       "created_at": "2025-01-15T10:30:00Z",
--       "language": "en"
--     },
--     "visual": { ... },
--     "summary": { ... }
--   },
--   "legacy": {  // Old single-embedding metadata for backward compat
--     "model": "text-embedding-3-small",
--     "dimensions": 1536,
--     "input_text_hash": "...",
--     "input_text_length": 8000
--   }
-- }

COMMENT ON COLUMN video_scenes.embedding_metadata IS
    'Per-channel embedding metadata (v3-multi) with legacy single-embedding metadata for backward compatibility';

-- ============================================================================
-- 4. Create HNSW indexes for new embedding columns
-- ============================================================================

-- Index for transcript channel (highest recall priority)
CREATE INDEX IF NOT EXISTS idx_video_scenes_embedding_transcript
    ON video_scenes USING hnsw (embedding_transcript vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Index for visual channel (medium recall priority)
CREATE INDEX IF NOT EXISTS idx_video_scenes_embedding_visual
    ON video_scenes USING hnsw (embedding_visual vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Index for summary channel (lower recall priority, optional usage)
CREATE INDEX IF NOT EXISTS idx_video_scenes_embedding_summary
    ON video_scenes USING hnsw (embedding_summary vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- HNSW parameters rationale:
-- - m = 16: Balanced recall vs memory (same as existing index)
-- - ef_construction = 64: Build-time search depth (same as existing)
-- - vector_cosine_ops: Cosine distance (1 - <=> gives similarity in [0,1])

COMMENT ON INDEX idx_video_scenes_embedding_transcript IS
    'HNSW index for transcript-only embeddings (cosine similarity)';

COMMENT ON INDEX idx_video_scenes_embedding_visual IS
    'HNSW index for visual-description + tags embeddings (cosine similarity)';

COMMENT ON INDEX idx_video_scenes_embedding_summary IS
    'HNSW index for summary embeddings (cosine similarity)';

-- ============================================================================
-- 5. Add partial indexes to exclude NULL embeddings (query optimization)
-- ============================================================================

-- Partial indexes to skip NULL rows during search
CREATE INDEX IF NOT EXISTS idx_video_scenes_embedding_transcript_not_null
    ON video_scenes (id) WHERE embedding_transcript IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_video_scenes_embedding_visual_not_null
    ON video_scenes (id) WHERE embedding_visual IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_video_scenes_embedding_summary_not_null
    ON video_scenes (id) WHERE embedding_summary IS NOT NULL;

-- ============================================================================
-- 6. Create RPC functions for per-channel dense search
-- ============================================================================

-- -----------------------------------------------------------------------------
-- Function: search_scenes_by_transcript_embedding
-- Purpose: Search using transcript embeddings only
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION search_scenes_by_transcript_embedding(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 200,
    filter_video_id uuid DEFAULT NULL,
    filter_user_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    video_id uuid,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        vs.id,
        vs.video_id,
        (1 - (vs.embedding_transcript <=> query_embedding))::float AS similarity
    FROM video_scenes vs
    INNER JOIN videos v ON vs.video_id = v.id
    WHERE
        vs.embedding_transcript IS NOT NULL
        AND (1 - (vs.embedding_transcript <=> query_embedding)) > match_threshold
        AND (filter_video_id IS NULL OR vs.video_id = filter_video_id)
        AND (filter_user_id IS NULL OR v.owner_id = filter_user_id)
    ORDER BY vs.embedding_transcript <=> query_embedding ASC
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION search_scenes_by_transcript_embedding IS
    'Search scenes using transcript-only embeddings with user/video filtering. Returns (id, video_id, similarity).';

-- -----------------------------------------------------------------------------
-- Function: search_scenes_by_visual_embedding
-- Purpose: Search using visual embeddings only
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION search_scenes_by_visual_embedding(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 200,
    filter_video_id uuid DEFAULT NULL,
    filter_user_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    video_id uuid,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        vs.id,
        vs.video_id,
        (1 - (vs.embedding_visual <=> query_embedding))::float AS similarity
    FROM video_scenes vs
    INNER JOIN videos v ON vs.video_id = v.id
    WHERE
        vs.embedding_visual IS NOT NULL
        AND (1 - (vs.embedding_visual <=> query_embedding)) > match_threshold
        AND (filter_video_id IS NULL OR vs.video_id = filter_video_id)
        AND (filter_user_id IS NULL OR v.owner_id = filter_user_id)
    ORDER BY vs.embedding_visual <=> query_embedding ASC
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION search_scenes_by_visual_embedding IS
    'Search scenes using visual-only embeddings with user/video filtering. Returns (id, video_id, similarity).';

-- -----------------------------------------------------------------------------
-- Function: search_scenes_by_summary_embedding
-- Purpose: Search using summary embeddings only (optional channel)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION search_scenes_by_summary_embedding(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 200,
    filter_video_id uuid DEFAULT NULL,
    filter_user_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    video_id uuid,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        vs.id,
        vs.video_id,
        (1 - (vs.embedding_summary <=> query_embedding))::float AS similarity
    FROM video_scenes vs
    INNER JOIN videos v ON vs.video_id = v.id
    WHERE
        vs.embedding_summary IS NOT NULL
        AND (1 - (vs.embedding_summary <=> query_embedding)) > match_threshold
        AND (filter_video_id IS NULL OR vs.video_id = filter_video_id)
        AND (filter_user_id IS NULL OR v.owner_id = filter_user_id)
    ORDER BY vs.embedding_summary <=> query_embedding ASC
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION search_scenes_by_summary_embedding IS
    'Search scenes using summary embeddings with user/video filtering. Returns (id, video_id, similarity).';

-- ============================================================================
-- 7. Migration verification queries (for manual testing)
-- ============================================================================

-- Check column existence and types
-- SELECT
--     column_name,
--     data_type,
--     is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'video_scenes'
--     AND column_name LIKE '%embedding%'
-- ORDER BY ordinal_position;

-- Check index creation
-- SELECT
--     indexname,
--     indexdef
-- FROM pg_indexes
-- WHERE tablename = 'video_scenes'
--     AND indexname LIKE '%embedding%';

-- Check function creation
-- SELECT
--     routine_name,
--     routine_type,
--     data_type AS return_type
-- FROM information_schema.routines
-- WHERE routine_name LIKE '%embedding%'
--     AND routine_schema = 'public';

-- ============================================================================
-- Notes for backfill/reprocessing:
-- ============================================================================
--
-- After running this migration:
-- 1. All existing scenes will have NULL values for new embedding columns
-- 2. embedding_version remains at current value (v2 or NULL)
-- 3. Run backfill script: services/worker/src/scripts/backfill_scene_embeddings_v3.py
-- 4. Backfill will:
--    - Regenerate embeddings for each channel independently
--    - Set embedding_version = 'v3-multi'
--    - Preserve existing 'embedding' column for fallback
--    - Update embedding_metadata with per-channel metadata
--
-- Rollback safety:
-- - Old API code can still use 'embedding' column (unaffected)
-- - New columns are additive, no data loss
-- - Can drop new columns if needed: ALTER TABLE video_scenes DROP COLUMN embedding_transcript;
