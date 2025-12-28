-- Migration: Add search_metadata to search_queries
-- Date: 2025-12-28
-- Description: Add search_metadata JSONB column to track fusion configuration and performance

-- Add search_metadata column to search_queries
ALTER TABLE search_queries
ADD COLUMN IF NOT EXISTS search_metadata JSONB;

-- Create GIN index for efficient querying and analytics
CREATE INDEX IF NOT EXISTS idx_search_queries_metadata
ON search_queries USING GIN (search_metadata);

-- Add comment explaining the schema
COMMENT ON COLUMN search_queries.search_metadata IS 'Search execution metadata for analytics and debugging.
Example: {
  "fusion_method": "multi_dense_minmax_mean",
  "weights": {"transcript": 0.5, "visual": 0.3, "summary": 0.1, "lexical": 0.1},
  "weight_source": "request|saved|default",
  "visual_mode": "rerank",
  "channels_active": ["transcript", "visual", "lexical"],
  "channels_empty": ["summary"],
  "channels_flat": [],
  "timing": {
    "embedding_ms": 120,
    "transcript_ms": 45,
    "visual_ms": 62,
    "lexical_ms": 23,
    "fusion_ms": 5,
    "rerank_ms": 0
  }
}';

-- No migration for existing rows - NULL is acceptable for historical data
