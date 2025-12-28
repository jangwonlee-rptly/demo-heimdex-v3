-- Migration 018: Add batch CLIP scoring RPC for rerank mode
-- Version: 018
-- Description: Add RPC function to efficiently score a batch of candidate scenes
--              with CLIP similarity in a single query (avoids N+1 problem in rerank mode)

-- RPC function: Batch score scenes by CLIP visual embedding
-- Purpose: Given a list of candidate scene IDs, compute CLIP similarity for each
-- Returns only scenes that have CLIP embeddings and pass tenant filtering
CREATE OR REPLACE FUNCTION batch_score_scenes_clip(
  query_embedding vector(512),
  scene_ids uuid[],
  filter_user_id uuid DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    vs.id,
    (1 - (vs.embedding_visual_clip <=> query_embedding))::float AS similarity
  FROM video_scenes vs
  INNER JOIN videos v ON vs.video_id = v.id
  WHERE
    vs.id = ANY(scene_ids)
    AND vs.embedding_visual_clip IS NOT NULL
    AND (filter_user_id IS NULL OR v.owner_id = filter_user_id);
END;
$$;

COMMENT ON FUNCTION batch_score_scenes_clip IS
  'Batch compute CLIP visual similarity for a set of candidate scenes.
   Used in rerank mode to avoid N+1 queries.
   Returns (id, similarity) for scenes with CLIP embeddings that pass tenant filter.
   Missing scenes (no CLIP embedding or access denied) are omitted from results.';
