-- Initial schema for Heimdex

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- User profiles table
CREATE TABLE user_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    industry TEXT,
    job_title TEXT,
    marketing_consent BOOLEAN DEFAULT FALSE NOT NULL,
    marketing_consent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to user_profiles
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Video status enum
CREATE TYPE video_status AS ENUM ('PENDING', 'PROCESSING', 'READY', 'FAILED');

-- Videos table
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    status video_status DEFAULT 'PENDING' NOT NULL,
    duration_s FLOAT,
    frame_rate FLOAT,
    width INTEGER,
    height INTEGER,
    video_created_at TIMESTAMPTZ,
    thumbnail_url TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Apply updated_at trigger to videos
CREATE TRIGGER update_videos_updated_at
    BEFORE UPDATE ON videos
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Index on owner_id for fast user video queries
CREATE INDEX idx_videos_owner_id ON videos(owner_id);
CREATE INDEX idx_videos_status ON videos(status);

-- Video scenes table (will add embedding column after pgvector is enabled)
CREATE TABLE video_scenes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    index INTEGER NOT NULL,
    start_s FLOAT NOT NULL,
    end_s FLOAT NOT NULL,
    transcript_segment TEXT,
    visual_summary TEXT,
    combined_text TEXT,
    thumbnail_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    UNIQUE(video_id, index)
);

-- Index on video_id for fast scene queries
CREATE INDEX idx_video_scenes_video_id ON video_scenes(video_id);

-- Search queries table
CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    video_id UUID REFERENCES videos(id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'scene_search',
    results_count INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Index for analytics queries
CREATE INDEX idx_search_queries_user_id ON search_queries(user_id);
CREATE INDEX idx_search_queries_created_at ON search_queries(created_at DESC);
CREATE INDEX idx_search_queries_video_id ON search_queries(video_id);

-- Row Level Security (RLS) policies

-- User profiles: users can only see and modify their own profile
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
    ON user_profiles FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own profile"
    ON user_profiles FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own profile"
    ON user_profiles FOR UPDATE
    USING (auth.uid() = user_id);

-- Videos: users can only see and modify their own videos
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own videos"
    ON videos FOR SELECT
    USING (auth.uid() = owner_id);

CREATE POLICY "Users can insert own videos"
    ON videos FOR INSERT
    WITH CHECK (auth.uid() = owner_id);

CREATE POLICY "Users can update own videos"
    ON videos FOR UPDATE
    USING (auth.uid() = owner_id);

-- Video scenes: users can only see scenes from their own videos
ALTER TABLE video_scenes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view scenes from own videos"
    ON video_scenes FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM videos
            WHERE videos.id = video_scenes.video_id
            AND videos.owner_id = auth.uid()
        )
    );

-- Allow service role to insert/update scenes (worker service)
CREATE POLICY "Service role can manage scenes"
    ON video_scenes FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

-- Search queries: users can only see their own queries
ALTER TABLE search_queries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own search queries"
    ON search_queries FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert search queries"
    ON search_queries FOR INSERT
    WITH CHECK (auth.jwt()->>'role' = 'service_role' OR auth.uid() = user_id);
