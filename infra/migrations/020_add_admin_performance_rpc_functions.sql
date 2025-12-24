-- Migration 020: Add Admin Performance RPC Functions (Phase 2)
--
-- Purpose: Enable precise performance metrics for admin dashboard:
-- - Processing latency percentiles (p50/p95/p99)
-- - RTF (Real-Time Factor) distribution
-- - Queue vs Run time analysis
-- - Failure attribution by stage
--
-- These functions read from the timing columns added in migration 019.

-- ============================================
-- 1. Processing Latency Percentiles
-- ============================================
-- Returns p50, p95, p99 processing time and average queue time

CREATE OR REPLACE FUNCTION get_admin_processing_latency(
    p_days_back INT DEFAULT 30
)
RETURNS TABLE (
    videos_measured BIGINT,
    avg_processing_ms FLOAT,
    p50_processing_ms FLOAT,
    p95_processing_ms FLOAT,
    p99_processing_ms FLOAT,
    avg_queue_ms FLOAT,
    avg_total_ms FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH timing_data AS (
        SELECT
            processing_duration_ms,
            EXTRACT(EPOCH FROM (processing_started_at - queued_at)) * 1000 AS queue_ms,
            EXTRACT(EPOCH FROM (processing_finished_at - queued_at)) * 1000 AS total_ms
        FROM videos
        WHERE
            processing_finished_at >= NOW() - (p_days_back || ' days')::INTERVAL
            AND processing_duration_ms IS NOT NULL
            AND status IN ('READY', 'FAILED')
            AND processing_started_at IS NOT NULL
            AND queued_at IS NOT NULL
    ),
    percentiles AS (
        SELECT
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY processing_duration_ms) AS p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY processing_duration_ms) AS p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY processing_duration_ms) AS p99
        FROM timing_data
    )
    SELECT
        COUNT(*)::BIGINT AS videos_measured,
        AVG(processing_duration_ms)::FLOAT AS avg_processing_ms,
        p.p50::FLOAT AS p50_processing_ms,
        p.p95::FLOAT AS p95_processing_ms,
        p.p99::FLOAT AS p99_processing_ms,
        AVG(queue_ms)::FLOAT AS avg_queue_ms,
        AVG(total_ms)::FLOAT AS avg_total_ms
    FROM timing_data, percentiles p;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_admin_processing_latency IS
  'Returns processing time percentiles and average queue time for performance monitoring';

-- ============================================
-- 2. RTF (Real-Time Factor) Distribution
-- ============================================
-- RTF = processing_duration / video_duration
-- Shows how many seconds of processing per second of video

CREATE OR REPLACE FUNCTION get_admin_rtf_distribution(
    p_days_back INT DEFAULT 30
)
RETURNS TABLE (
    videos_measured BIGINT,
    avg_rtf FLOAT,
    p50_rtf FLOAT,
    p95_rtf FLOAT,
    p99_rtf FLOAT,
    avg_video_duration_s FLOAT,
    avg_processing_duration_s FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH rtf_data AS (
        SELECT
            duration_s,
            processing_duration_ms,
            (processing_duration_ms / 1000.0) / NULLIF(duration_s, 0) AS rtf
        FROM videos
        WHERE
            processing_finished_at >= NOW() - (p_days_back || ' days')::INTERVAL
            AND processing_duration_ms IS NOT NULL
            AND duration_s IS NOT NULL
            AND duration_s > 0
            AND status = 'READY'  -- Only successful processing for RTF
    ),
    percentiles AS (
        SELECT
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY rtf) AS p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY rtf) AS p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY rtf) AS p99
        FROM rtf_data
    )
    SELECT
        COUNT(*)::BIGINT AS videos_measured,
        AVG(rtf)::FLOAT AS avg_rtf,
        p.p50::FLOAT AS p50_rtf,
        p.p95::FLOAT AS p95_rtf,
        p.p99::FLOAT AS p99_rtf,
        AVG(duration_s)::FLOAT AS avg_video_duration_s,
        AVG(processing_duration_ms / 1000.0)::FLOAT AS avg_processing_duration_s
    FROM rtf_data, percentiles p;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_admin_rtf_distribution IS
  'Returns RTF (Real-Time Factor) distribution showing processing efficiency';

-- ============================================
-- 3. Queue vs Run Time Analysis
-- ============================================
-- Separates time waiting in queue from actual processing time

CREATE OR REPLACE FUNCTION get_admin_queue_analysis(
    p_days_back INT DEFAULT 30
)
RETURNS TABLE (
    videos_measured BIGINT,
    avg_queue_time_s FLOAT,
    avg_processing_time_s FLOAT,
    avg_total_time_s FLOAT,
    queue_time_pct FLOAT,
    processing_time_pct FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH timing_breakdown AS (
        SELECT
            EXTRACT(EPOCH FROM (processing_started_at - queued_at)) AS queue_s,
            EXTRACT(EPOCH FROM (processing_finished_at - processing_started_at)) AS processing_s,
            EXTRACT(EPOCH FROM (processing_finished_at - queued_at)) AS total_s
        FROM videos
        WHERE
            processing_finished_at >= NOW() - (p_days_back || ' days')::INTERVAL
            AND queued_at IS NOT NULL
            AND processing_started_at IS NOT NULL
            AND processing_finished_at IS NOT NULL
            AND status IN ('READY', 'FAILED')
    )
    SELECT
        COUNT(*)::BIGINT AS videos_measured,
        AVG(queue_s)::FLOAT AS avg_queue_time_s,
        AVG(processing_s)::FLOAT AS avg_processing_time_s,
        AVG(total_s)::FLOAT AS avg_total_time_s,
        (AVG(queue_s) / NULLIF(AVG(total_s), 0) * 100)::FLOAT AS queue_time_pct,
        (AVG(processing_s) / NULLIF(AVG(total_s), 0) * 100)::FLOAT AS processing_time_pct
    FROM timing_breakdown;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_admin_queue_analysis IS
  'Returns queue vs processing time breakdown for capacity planning';

-- ============================================
-- 4. Failures by Processing Stage
-- ============================================
-- Shows which stage failures occur at most frequently

CREATE OR REPLACE FUNCTION get_admin_failures_by_stage(
    p_days_back INT DEFAULT 30
)
RETURNS TABLE (
    processing_stage TEXT,
    failure_count BIGINT,
    failure_pct FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH failed_videos AS (
        SELECT
            COALESCE(processing_stage, 'unknown') AS stage
        FROM videos
        WHERE
            processing_finished_at >= NOW() - (p_days_back || ' days')::INTERVAL
            AND status = 'FAILED'
    ),
    stage_counts AS (
        SELECT
            stage,
            COUNT(*) AS count
        FROM failed_videos
        GROUP BY stage
    ),
    total_failures AS (
        SELECT SUM(count) AS total FROM stage_counts
    )
    SELECT
        sc.stage,
        sc.count,
        (sc.count::FLOAT / NULLIF(tf.total, 0) * 100)::FLOAT AS failure_pct
    FROM stage_counts sc, total_failures tf
    ORDER BY sc.count DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_admin_failures_by_stage IS
  'Returns failure attribution by processing stage for reliability analysis';

-- ============================================
-- 5. Throughput Time Series (Enhanced)
-- ============================================
-- Enhanced version using processing_finished_at for precision

CREATE OR REPLACE FUNCTION get_admin_throughput_timeseries_v2(
    p_days_back INT DEFAULT 30
)
RETURNS TABLE (
    day DATE,
    videos_ready BIGINT,
    videos_failed BIGINT,
    hours_ready FLOAT,
    avg_processing_s FLOAT,
    avg_rtf FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        DATE(COALESCE(processing_finished_at, updated_at)) AS day,
        COUNT(*) FILTER (WHERE status = 'READY')::BIGINT AS videos_ready,
        COUNT(*) FILTER (WHERE status = 'FAILED')::BIGINT AS videos_failed,
        COALESCE(SUM(duration_s) FILTER (WHERE status = 'READY'), 0)::FLOAT / 3600.0 AS hours_ready,
        AVG(processing_duration_ms / 1000.0) FILTER (WHERE processing_duration_ms IS NOT NULL)::FLOAT AS avg_processing_s,
        AVG((processing_duration_ms / 1000.0) / NULLIF(duration_s, 0))
            FILTER (WHERE processing_duration_ms IS NOT NULL AND duration_s > 0)::FLOAT AS avg_rtf
    FROM videos
    WHERE
        COALESCE(processing_finished_at, updated_at) >= NOW() - (p_days_back || ' days')::INTERVAL
        AND status IN ('READY', 'FAILED')
    GROUP BY day
    ORDER BY day DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_admin_throughput_timeseries_v2 IS
  'Returns daily throughput with precise timing (Phase 2 enhanced version)';

-- ============================================
-- Test Queries (Comment out after verification)
-- ============================================

-- Test latency percentiles:
-- SELECT * FROM get_admin_processing_latency(7);

-- Test RTF distribution:
-- SELECT * FROM get_admin_rtf_distribution(7);

-- Test queue analysis:
-- SELECT * FROM get_admin_queue_analysis(7);

-- Test failures by stage:
-- SELECT * FROM get_admin_failures_by_stage(30);

-- Test enhanced throughput:
-- SELECT * FROM get_admin_throughput_timeseries_v2(14);
