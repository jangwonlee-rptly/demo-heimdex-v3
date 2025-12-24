-- Migration: Add RPC functions for admin metrics
-- Created: 2025-12-23
-- Description: PostgreSQL functions to compute admin dashboard metrics efficiently

-- Function 1: Get admin overview metrics
CREATE OR REPLACE FUNCTION get_admin_overview_metrics()
RETURNS TABLE (
    videos_ready_total BIGINT,
    videos_failed_total BIGINT,
    videos_total BIGINT,
    failure_rate_pct FLOAT,
    hours_ready_total FLOAT,
    searches_7d BIGINT,
    avg_search_latency_ms_7d FLOAT,
    searches_30d BIGINT,
    avg_search_latency_ms_30d FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH video_stats AS (
        SELECT
            COUNT(*) FILTER (WHERE status = 'READY') AS ready_count,
            COUNT(*) FILTER (WHERE status = 'FAILED') AS failed_count,
            COUNT(*) AS total_count,
            COALESCE(SUM(duration_s) FILTER (WHERE status = 'READY'), 0) / 3600.0 AS hours_ready
        FROM videos
    ),
    search_stats_7d AS (
        SELECT
            COUNT(*) AS search_count,
            AVG(latency_ms)::FLOAT AS avg_latency
        FROM search_queries
        WHERE created_at >= NOW() - INTERVAL '7 days'
    ),
    search_stats_30d AS (
        SELECT
            COUNT(*) AS search_count,
            AVG(latency_ms)::FLOAT AS avg_latency
        FROM search_queries
        WHERE created_at >= NOW() - INTERVAL '30 days'
    )
    SELECT
        v.ready_count,
        v.failed_count,
        v.total_count,
        CASE
            WHEN v.total_count > 0 THEN (v.failed_count::FLOAT / NULLIF(v.total_count, 0)) * 100
            ELSE 0
        END AS failure_pct,
        v.hours_ready,
        s7.search_count,
        s7.avg_latency,
        s30.search_count,
        s30.avg_latency
    FROM video_stats v, search_stats_7d s7, search_stats_30d s30;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function 2: Get throughput time series
CREATE OR REPLACE FUNCTION get_throughput_timeseries(days_back INT DEFAULT 30)
RETURNS TABLE (
    day TEXT,
    videos_ready BIGINT,
    hours_ready FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        TO_CHAR(DATE(updated_at), 'YYYY-MM-DD') AS day,
        COUNT(*) AS videos_ready,
        COALESCE(SUM(duration_s), 0) / 3600.0 AS hours_ready
    FROM videos
    WHERE status = 'READY'
      AND updated_at >= NOW() - (days_back || ' days')::INTERVAL
    GROUP BY DATE(updated_at)
    ORDER BY DATE(updated_at) ASC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function 3: Get search time series
CREATE OR REPLACE FUNCTION get_search_timeseries(days_back INT DEFAULT 30)
RETURNS TABLE (
    day TEXT,
    searches BIGINT,
    avg_latency_ms FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        TO_CHAR(DATE(created_at), 'YYYY-MM-DD') AS day,
        COUNT(*) AS searches,
        AVG(latency_ms)::FLOAT AS avg_latency_ms
    FROM search_queries
    WHERE created_at >= NOW() - (days_back || ' days')::INTERVAL
    GROUP BY DATE(created_at)
    ORDER BY DATE(created_at) ASC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function 4: Get admin users list
CREATE OR REPLACE FUNCTION get_admin_users_list(
    days_back INT DEFAULT 7,
    limit_count INT DEFAULT 50,
    offset_count INT DEFAULT 0,
    sort_column TEXT DEFAULT 'last_activity'
)
RETURNS TABLE (
    user_id TEXT,
    full_name TEXT,
    videos_total BIGINT,
    videos_ready BIGINT,
    hours_ready FLOAT,
    last_activity TIMESTAMPTZ,
    searches_7d BIGINT,
    avg_latency_ms_7d FLOAT
) AS $$
DECLARE
    sort_clause TEXT;
BEGIN
    -- Build sort clause based on sort_column parameter
    sort_clause := CASE sort_column
        WHEN 'hours_ready' THEN 'hours_ready DESC NULLS LAST'
        WHEN 'videos_ready' THEN 'videos_ready DESC'
        WHEN 'searches_7d' THEN 'searches_7d DESC'
        ELSE 'last_activity DESC NULLS LAST'
    END;

    RETURN QUERY EXECUTE format('
        WITH user_metrics AS (
            SELECT
                up.user_id::TEXT,
                up.full_name,
                COUNT(v.id) AS videos_total,
                COUNT(v.id) FILTER (WHERE v.status = ''READY'') AS videos_ready,
                COALESCE(SUM(v.duration_s) FILTER (WHERE v.status = ''READY''), 0) / 3600.0 AS hours_ready,
                GREATEST(
                    MAX(v.updated_at),
                    MAX(sq.created_at)
                ) AS last_activity,
                COUNT(sq.id) FILTER (WHERE sq.created_at >= NOW() - INTERVAL ''%s days'') AS searches_7d,
                AVG(sq.latency_ms) FILTER (WHERE sq.created_at >= NOW() - INTERVAL ''%s days'')::FLOAT AS avg_latency_ms_7d
            FROM user_profiles up
            LEFT JOIN videos v ON v.owner_id = up.user_id
            LEFT JOIN search_queries sq ON sq.user_id = up.user_id
            GROUP BY up.user_id, up.full_name
        )
        SELECT * FROM user_metrics
        ORDER BY %s
        LIMIT %s OFFSET %s
    ', days_back, days_back, sort_clause, limit_count, offset_count);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function 5: Get admin user detail
CREATE OR REPLACE FUNCTION get_admin_user_detail(
    target_user_id TEXT,
    days_back INT DEFAULT 7
)
RETURNS TABLE (
    user_id TEXT,
    full_name TEXT,
    videos_total BIGINT,
    videos_ready BIGINT,
    hours_ready FLOAT,
    last_activity TIMESTAMPTZ,
    searches_7d BIGINT,
    avg_latency_ms_7d FLOAT,
    recent_videos JSONB,
    recent_searches JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH user_summary AS (
        SELECT
            up.user_id::TEXT,
            up.full_name,
            COUNT(v.id) AS videos_total,
            COUNT(v.id) FILTER (WHERE v.status = 'READY') AS videos_ready,
            COALESCE(SUM(v.duration_s) FILTER (WHERE v.status = 'READY'), 0) / 3600.0 AS hours_ready,
            GREATEST(
                MAX(v.updated_at),
                MAX(sq.created_at)
            ) AS last_activity,
            COUNT(sq.id) FILTER (WHERE sq.created_at >= NOW() - (days_back || ' days')::INTERVAL) AS searches_7d,
            AVG(sq.latency_ms) FILTER (WHERE sq.created_at >= NOW() - (days_back || ' days')::INTERVAL)::FLOAT AS avg_latency_ms_7d
        FROM user_profiles up
        LEFT JOIN videos v ON v.owner_id = up.user_id
        LEFT JOIN search_queries sq ON sq.user_id = up.user_id
        WHERE up.user_id::TEXT = target_user_id
        GROUP BY up.user_id, up.full_name
    ),
    recent_vids AS (
        SELECT JSONB_AGG(
            JSONB_BUILD_OBJECT(
                'id', v.id::TEXT,
                'filename', v.filename,
                'status', v.status,
                'duration_s', v.duration_s,
                'updated_at', v.updated_at,
                'error_message', v.error_message
            ) ORDER BY v.updated_at DESC
        ) AS videos
        FROM (
            SELECT * FROM videos
            WHERE owner_id::TEXT = target_user_id
            ORDER BY updated_at DESC
            LIMIT 20
        ) v
    ),
    recent_srch AS (
        SELECT JSONB_AGG(
            JSONB_BUILD_OBJECT(
                'query_text', sq.query_text,
                'created_at', sq.created_at,
                'latency_ms', sq.latency_ms,
                'results_count', sq.results_count,
                'video_id', sq.video_id::TEXT
            ) ORDER BY sq.created_at DESC
        ) AS searches
        FROM (
            SELECT * FROM search_queries
            WHERE user_id::TEXT = target_user_id
            ORDER BY created_at DESC
            LIMIT 50
        ) sq
    )
    SELECT
        us.user_id,
        us.full_name,
        us.videos_total,
        us.videos_ready,
        us.hours_ready,
        us.last_activity,
        us.searches_7d,
        us.avg_latency_ms_7d,
        COALESCE(rv.videos, '[]'::JSONB) AS recent_videos,
        COALESCE(rs.searches, '[]'::JSONB) AS recent_searches
    FROM user_summary us, recent_vids rv, recent_srch rs;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Add comments for documentation
COMMENT ON FUNCTION get_admin_overview_metrics() IS 'Returns top-level KPI metrics for admin dashboard';
COMMENT ON FUNCTION get_throughput_timeseries(INT) IS 'Returns daily video processing throughput time series';
COMMENT ON FUNCTION get_search_timeseries(INT) IS 'Returns daily search volume and latency time series';
COMMENT ON FUNCTION get_admin_users_list(INT, INT, INT, TEXT) IS 'Returns paginated list of users with metrics';
COMMENT ON FUNCTION get_admin_user_detail(TEXT, INT) IS 'Returns detailed user information with recent videos and searches';
