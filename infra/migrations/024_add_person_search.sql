-- Migration 024: Add person search with reference photos and scene embeddings
-- Version: 024
-- Description: Enable person-aware search using CLIP embeddings from reference photos
--              Supports multiple embeddings per scene (keyframes) via (kind, ordinal) columns

-- ============================================================================
-- PERSONS TABLE
-- ============================================================================

-- Persons table (owner-scoped)
CREATE TABLE persons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    query_embedding vector(512),  -- Aggregate CLIP embedding from reference photos
    status TEXT DEFAULT 'active' NOT NULL,  -- 'active' | 'archived'
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE persons IS
  'Enrolled persons for person-aware search.
   Each person can have multiple reference photos whose embeddings are aggregated.';

COMMENT ON COLUMN persons.query_embedding IS
  'Aggregate CLIP embedding (512d) computed as normalized mean of all READY reference photo embeddings.
   NULL if no READY photos yet. Used for person retrieval queries.';

-- ============================================================================
-- PERSON REFERENCE PHOTOS TABLE
-- ============================================================================

-- Person reference photos
CREATE TABLE person_reference_photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    state TEXT DEFAULT 'UPLOADED' NOT NULL,  -- 'UPLOADED' | 'PROCESSING' | 'READY' | 'FAILED'
    embedding vector(512),  -- CLIP embedding from photo
    quality_score FLOAT,
    face_bbox JSONB,  -- Nullable for v1: {x, y, w, h, confidence}
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE person_reference_photos IS
  'Reference photos used to enroll a person for face/person matching.
   Each photo is processed to extract a CLIP visual embedding.';

COMMENT ON COLUMN person_reference_photos.state IS
  'Processing state:
   - UPLOADED: Photo uploaded, queued for processing
   - PROCESSING: Worker is extracting embedding
   - READY: Embedding extracted successfully
   - FAILED: Processing failed (see error_message)';

COMMENT ON COLUMN person_reference_photos.embedding IS
  'CLIP visual embedding (512d) extracted from reference photo.
   NULL until processing completes successfully.';

COMMENT ON COLUMN person_reference_photos.face_bbox IS
  'Optional face bounding box for v2 face detection.
   Structure: {"x": 100, "y": 50, "w": 200, "h": 200, "confidence": 0.95}
   NULL in v1 (whole image embedding).';

-- ============================================================================
-- SCENE PERSON EMBEDDINGS TABLE
-- ============================================================================

-- Scene person embeddings (supports multiple per scene via kind + ordinal)
CREATE TABLE scene_person_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    scene_id UUID NOT NULL REFERENCES video_scenes(id) ON DELETE CASCADE,
    kind TEXT DEFAULT 'thumbnail' NOT NULL,  -- 'thumbnail' | 'keyframe' (future)
    ordinal INT DEFAULT 0 NOT NULL,  -- 0-indexed position within kind
    embedding vector(512) NOT NULL,  -- CLIP embedding from scene image
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    UNIQUE(scene_id, kind, ordinal)  -- Multiple embeddings per scene allowed
);

COMMENT ON TABLE scene_person_embeddings IS
  'CLIP visual embeddings from scene images for person retrieval.
   Multiple embeddings per scene supported via (kind, ordinal):
   - kind=thumbnail, ordinal=0: primary scene thumbnail
   - kind=keyframe, ordinal=0..N: future support for multiple keyframes per scene';

COMMENT ON COLUMN scene_person_embeddings.kind IS
  'Type of image source:
   - thumbnail: scene thumbnail (default)
   - keyframe: extracted keyframe (future)';

COMMENT ON COLUMN scene_person_embeddings.ordinal IS
  '0-indexed position within kind.
   Example: scene with 3 keyframes would have ordinal 0, 1, 2 with kind=keyframe.';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Person indexes
CREATE INDEX idx_persons_owner_id ON persons(owner_id);
CREATE INDEX idx_persons_status ON persons(status);

-- Person reference photo indexes
CREATE INDEX idx_person_reference_photos_owner_id ON person_reference_photos(owner_id);
CREATE INDEX idx_person_reference_photos_person_id ON person_reference_photos(person_id);
CREATE INDEX idx_person_reference_photos_state ON person_reference_photos(state);

-- Scene person embedding indexes
CREATE INDEX idx_scene_person_embeddings_owner_id ON scene_person_embeddings(owner_id);
CREATE INDEX idx_scene_person_embeddings_video_id ON scene_person_embeddings(video_id);
CREATE INDEX idx_scene_person_embeddings_scene_id ON scene_person_embeddings(scene_id);

-- HNSW index for person search (cosine similarity)
CREATE INDEX idx_scene_person_embeddings_embedding
    ON scene_person_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- RPC FUNCTION: PERSON SEARCH
-- ============================================================================

-- RPC: Search scenes by person embedding
-- Tenant-safe: filters by owner_id directly on scene_person_embeddings
-- Returns scenes ordered by best cosine similarity across all embeddings for that scene
CREATE OR REPLACE FUNCTION search_scenes_by_person_clip_embedding(
    query_embedding vector(512),
    match_threshold float DEFAULT 0.3,
    match_count int DEFAULT 200,
    filter_video_id uuid DEFAULT NULL,
    filter_user_id uuid DEFAULT NULL
)
RETURNS TABLE (
    scene_id uuid,
    video_id uuid,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH scene_best_similarity AS (
        -- For each scene, get the best similarity across all embeddings
        SELECT
            spe.scene_id,
            spe.video_id,
            MAX(1 - (spe.embedding <=> query_embedding)) AS best_similarity
        FROM scene_person_embeddings spe
        WHERE
            (filter_user_id IS NULL OR spe.owner_id = filter_user_id)
            AND (filter_video_id IS NULL OR spe.video_id = filter_video_id)
        GROUP BY spe.scene_id, spe.video_id
        HAVING MAX(1 - (spe.embedding <=> query_embedding)) >= match_threshold
    )
    SELECT
        sbs.scene_id,
        sbs.video_id,
        sbs.best_similarity AS similarity
    FROM scene_best_similarity sbs
    ORDER BY sbs.best_similarity DESC
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION search_scenes_by_person_clip_embedding IS
  'Search video scenes by person CLIP embedding similarity.
   Uses cosine similarity (1 - cosine_distance) for ranking.
   Returns best match per scene when multiple embeddings exist (kind/ordinal).
   Tenant-safe: filters directly by owner_id on scene_person_embeddings table.';

-- ============================================================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================================================

-- Persons table RLS
ALTER TABLE persons ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own persons"
    ON persons FOR SELECT
    USING (auth.uid() = owner_id);

CREATE POLICY "Users can insert own persons"
    ON persons FOR INSERT
    WITH CHECK (auth.uid() = owner_id);

CREATE POLICY "Users can update own persons"
    ON persons FOR UPDATE
    USING (auth.uid() = owner_id);

CREATE POLICY "Users can delete own persons"
    ON persons FOR DELETE
    USING (auth.uid() = owner_id);

-- Person reference photos RLS
ALTER TABLE person_reference_photos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own person photos"
    ON person_reference_photos FOR SELECT
    USING (auth.uid() = owner_id);

-- Allow service role to manage person photos (worker service)
CREATE POLICY "Service role can manage person photos"
    ON person_reference_photos FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

-- Scene person embeddings RLS
ALTER TABLE scene_person_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own scene embeddings"
    ON scene_person_embeddings FOR SELECT
    USING (auth.uid() = owner_id);

-- Allow service role to manage scene embeddings (worker service)
CREATE POLICY "Service role can manage scene embeddings"
    ON scene_person_embeddings FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Apply updated_at trigger to persons
CREATE TRIGGER update_persons_updated_at
    BEFORE UPDATE ON persons
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply updated_at trigger to person_reference_photos
CREATE TRIGGER update_person_reference_photos_updated_at
    BEFORE UPDATE ON person_reference_photos
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
