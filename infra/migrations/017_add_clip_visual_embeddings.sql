-- Migration: Add CLIP visual embeddings to video_scenes
-- Version: 017
-- Description: Add CPU-friendly CLIP image embeddings for true visual similarity search
--              using OpenCLIP ViT-B-32 model (512-dim embeddings)

-- Add CLIP embedding column (512 dimensions for ViT-B-32)
ALTER TABLE video_scenes
  ADD COLUMN embedding_visual_clip vector(512);

COMMENT ON COLUMN video_scenes.embedding_visual_clip IS
  'CLIP visual embedding from scene keyframe using OpenCLIP ViT-B-32 model.
   Dimension: 512 (model-dependent, fixed for ViT-B-32).
   Generated from best-quality keyframe per scene for true visual similarity.
   NULL if CLIP disabled or embedding failed.';

-- Add CLIP metadata column
ALTER TABLE video_scenes
  ADD COLUMN visual_clip_metadata JSONB;

COMMENT ON COLUMN video_scenes.visual_clip_metadata IS
  'Metadata for CLIP visual embedding generation.
   Structure:
   {
     "model_name": "ViT-B-32",
     "pretrained": "openai",
     "embed_dim": 512,
     "normalized": true,
     "device": "cpu",
     "frame_path": "scene_12_frame_0.jpg",
     "frame_quality": {"brightness": 0.85, "blur": 120.5, "quality_score": 0.82},
     "inference_time_ms": 145.2,
     "created_at": "2025-01-15T12:34:56Z",
     "error": null | "timeout after 2.0s"
   }';

-- Create HNSW index for CLIP embedding cosine similarity search
-- Using same HNSW parameters as other embedding channels (m=16, ef_construction=64)
CREATE INDEX idx_video_scenes_embedding_visual_clip
  ON video_scenes
  USING hnsw (embedding_visual_clip vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Create partial index for non-NULL CLIP embeddings (query optimization)
CREATE INDEX idx_video_scenes_has_clip_embedding
  ON video_scenes(id)
  WHERE embedding_visual_clip IS NOT NULL;

-- Create GIN index for CLIP metadata queries (optional, for debugging)
CREATE INDEX idx_video_scenes_visual_clip_metadata
  ON video_scenes
  USING GIN (visual_clip_metadata);

-- RPC function: Search scenes by CLIP visual embedding
-- Tenant-safe: filters by owner_id via videos join
-- Returns scenes ordered by cosine similarity (1 - cosine distance)
CREATE OR REPLACE FUNCTION search_scenes_by_visual_clip_embedding(
  query_embedding vector(512),
  match_threshold float DEFAULT 0.5,
  match_count int DEFAULT 20,
  filter_video_id uuid DEFAULT NULL,
  filter_user_id uuid DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  video_id uuid,
  index int,
  start_s float,
  end_s float,
  thumbnail_url text,
  transcript_segment text,
  visual_summary text,
  visual_description text,
  visual_entities text[],
  visual_actions text[],
  tags text[],
  embedding_visual_clip vector(512),
  visual_clip_metadata jsonb,
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
    vs.thumbnail_url,
    vs.transcript_segment,
    vs.visual_summary,
    vs.visual_description,
    vs.visual_entities,
    vs.visual_actions,
    vs.tags,
    vs.embedding_visual_clip,
    vs.visual_clip_metadata,
    1 - (vs.embedding_visual_clip <=> query_embedding) AS similarity
  FROM video_scenes vs
  INNER JOIN videos v ON vs.video_id = v.id
  WHERE
    vs.embedding_visual_clip IS NOT NULL
    AND (1 - (vs.embedding_visual_clip <=> query_embedding)) >= match_threshold
    AND (filter_video_id IS NULL OR vs.video_id = filter_video_id)
    AND (filter_user_id IS NULL OR v.owner_id = filter_user_id)
  ORDER BY vs.embedding_visual_clip <=> query_embedding
  LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION search_scenes_by_visual_clip_embedding IS
  'Search video scenes by CLIP visual embedding similarity.
   Uses cosine similarity (1 - cosine_distance) for ranking.
   Tenant-safe: filters by owner_id via videos table join.
   Requires embedding_visual_clip to be non-NULL.';
