-- ============================================================================
-- ExamShield Analytics — SQL Analytics Layer (Phase 2)
-- Window functions, CTEs, Views, Stored Procedures
-- ============================================================================
SET search_path TO examshield;

-- ============================================================================
-- 1. WINDOW FUNCTIONS — Center ranking, state-wise ranking, percentiles
-- ============================================================================

-- 1a. Rank centers by average score, nationally and within their state
--     RANK() within state lets a small rural center compete fairly against
--     peers of similar context, rather than against national metros.
SELECT
    c.center_id,
    c.center_name,
    c.state_name,
    ROUND(AVG(f.total_score), 1)                                          AS avg_score,
    RANK()       OVER (ORDER BY AVG(f.total_score) DESC)                  AS national_rank,
    RANK()       OVER (PARTITION BY c.state_name ORDER BY AVG(f.total_score) DESC) AS state_rank,
    PERCENT_RANK() OVER (ORDER BY AVG(f.total_score) DESC)                AS national_percentile
FROM fact_exam_performance f
JOIN dim_center c ON f.center_id = c.center_id
WHERE f.attendance_status = 'present'
GROUP BY c.center_id, c.center_name, c.state_name
ORDER BY national_rank
LIMIT 20;

-- 1b. Complaint-rate percentile per center — used directly in the risk score
SELECT
    c.center_id,
    c.center_name,
    COUNT(comp.complaint_id)                                              AS complaint_count,
    PERCENT_RANK() OVER (ORDER BY COUNT(comp.complaint_id))               AS complaint_percentile
FROM dim_center c
LEFT JOIN fact_complaint comp ON c.center_id = comp.center_id
GROUP BY c.center_id, c.center_name
ORDER BY complaint_percentile DESC
LIMIT 20;

-- ============================================================================
-- 2. CTEs — Multi-step composite risk calculation
--    Each CTE computes one normalized sub-score; final SELECT combines them
--    into the documented weighted Integrity Risk Index (see README weights:
--    30% score anomaly, 25% complaints, 15% attendance, 10% capacity,
--    10% infrastructure, 10% historical integrity).
-- ============================================================================

WITH center_score_stats AS (
    SELECT
        center_id,
        AVG(total_score)                    AS avg_score,
        STDDEV(total_score)                 AS score_stddev,
        AVG(response_time_variance)         AS avg_rt_variance,
        AVG(changed_answer_correct_rate)    AS avg_changed_correct_rate
    FROM fact_exam_performance
    WHERE attendance_status = 'present'
    GROUP BY center_id
),
score_anomaly AS (
    -- Low response-time variance + high changed-to-correct rate = anomalous.
    -- Normalized 0-100 via min-max scaling across all centers.
    SELECT
        center_id,
        100 * (1 - (avg_rt_variance - MIN(avg_rt_variance) OVER ()) /
               NULLIF(MAX(avg_rt_variance) OVER () - MIN(avg_rt_variance) OVER (), 0)) * 0.5
        +
        100 * (avg_changed_correct_rate - MIN(avg_changed_correct_rate) OVER ()) /
               NULLIF(MAX(avg_changed_correct_rate) OVER () - MIN(avg_changed_correct_rate) OVER (), 0) * 0.5
        AS score_anomaly_index
    FROM center_score_stats
),
complaint_freq AS (
    SELECT
        c.center_id,
        COUNT(comp.complaint_id) AS complaint_count,
        100 * PERCENT_RANK() OVER (ORDER BY COUNT(comp.complaint_id)) AS complaint_index
    FROM dim_center c
    LEFT JOIN fact_complaint comp ON c.center_id = comp.center_id
    GROUP BY c.center_id
),
attendance_anomaly AS (
    SELECT
        center_id,
        AVG(CASE WHEN attendance_status = 'present' THEN 1 ELSE 0 END) AS attendance_rate,
        100 * (1 - ABS(AVG(CASE WHEN attendance_status = 'present' THEN 1 ELSE 0 END) - 0.955)
               / 0.955) AS attendance_index   -- deviation from expected ~95.5% national attendance rate
    FROM fact_exam_performance
    GROUP BY center_id
),
capacity_util AS (
    SELECT
        center_id,
        100 * (1 - internet_reliability_score / 100.0) AS capacity_index  -- proxy: weak connectivity = capacity strain
    FROM dim_center
),
infra_index AS (
    SELECT
        center_id,
        100 * (1 - (
            (cctv_camera_count::NUMERIC + biometric_device_count + perimeter_security_rating)
            / NULLIF((SELECT MAX(cctv_camera_count + biometric_device_count + perimeter_security_rating) FROM dim_center), 0)
        )) AS infra_risk_index
    FROM dim_center
),
historical_integrity AS (
    SELECT
        center_id,
        COALESCE(100 * PERCENT_RANK() OVER (ORDER BY COUNT(*) DESC), 0) AS historical_risk_index
    FROM fact_audit_finding af
    JOIN fact_audit a ON af.audit_id = a.audit_id
    GROUP BY center_id
)
SELECT
    c.center_id,
    c.center_name,
    c.state_name,
    c.is_synthetic_anomalous_center,
    ROUND(COALESCE(sa.score_anomaly_index, 0)::numeric, 1)      AS score_anomaly_index,
    ROUND(COALESCE(cf.complaint_index, 0)::numeric, 1)          AS complaint_index,
    ROUND(COALESCE(aa.attendance_index, 0)::numeric, 1)         AS attendance_index,
    ROUND(COALESCE(cu.capacity_index, 0)::numeric, 1)           AS capacity_index,
    ROUND(COALESCE(ii.infra_risk_index, 0)::numeric, 1)         AS infra_risk_index,
    ROUND(COALESCE(hi.historical_risk_index, 0)::numeric, 1)    AS historical_risk_index,
    ROUND(
        (0.30 * COALESCE(sa.score_anomaly_index, 0) +
        0.25 * COALESCE(cf.complaint_index, 0) +
        0.15 * COALESCE(aa.attendance_index, 0) +
        0.10 * COALESCE(cu.capacity_index, 0) +
        0.10 * COALESCE(ii.infra_risk_index, 0) +
        0.10 * COALESCE(hi.historical_risk_index, 0))::numeric
    , 1) AS composite_integrity_risk_score
FROM dim_center c
LEFT JOIN score_anomaly sa       ON c.center_id = sa.center_id
LEFT JOIN complaint_freq cf      ON c.center_id = cf.center_id
LEFT JOIN attendance_anomaly aa  ON c.center_id = aa.center_id
LEFT JOIN capacity_util cu       ON c.center_id = cu.center_id
LEFT JOIN infra_index ii         ON c.center_id = ii.center_id
LEFT JOIN historical_integrity hi ON c.center_id = hi.center_id
ORDER BY composite_integrity_risk_score DESC
LIMIT 20;

-- ============================================================================
-- 3. VIEWS
-- ============================================================================

-- 3a. High-risk centers — reusable view wrapping the CTE logic above
CREATE OR REPLACE VIEW vw_high_risk_centers AS
WITH center_score_stats AS (
    SELECT center_id, AVG(total_score) AS avg_score, STDDEV(total_score) AS score_stddev,
           AVG(response_time_variance) AS avg_rt_variance,
           AVG(changed_answer_correct_rate) AS avg_changed_correct_rate
    FROM fact_exam_performance WHERE attendance_status = 'present' GROUP BY center_id
),
score_anomaly AS (
    SELECT center_id,
        100 * (1 - (avg_rt_variance - MIN(avg_rt_variance) OVER ()) /
               NULLIF(MAX(avg_rt_variance) OVER () - MIN(avg_rt_variance) OVER (), 0)) * 0.5
        +
        100 * (avg_changed_correct_rate - MIN(avg_changed_correct_rate) OVER ()) /
               NULLIF(MAX(avg_changed_correct_rate) OVER () - MIN(avg_changed_correct_rate) OVER (), 0) * 0.5
        AS score_anomaly_index
    FROM center_score_stats
),
complaint_freq AS (
    SELECT c.center_id, COUNT(comp.complaint_id) AS complaint_count,
           100 * PERCENT_RANK() OVER (ORDER BY COUNT(comp.complaint_id)) AS complaint_index
    FROM dim_center c LEFT JOIN fact_complaint comp ON c.center_id = comp.center_id
    GROUP BY c.center_id
)
SELECT
    c.center_id, c.center_name, c.state_name, c.is_synthetic_anomalous_center,
    ROUND(COALESCE(sa.score_anomaly_index, 0)::numeric, 1) AS score_anomaly_index,
    ROUND(COALESCE(cf.complaint_index, 0)::numeric, 1)     AS complaint_index,
    ROUND((0.55 * COALESCE(sa.score_anomaly_index, 0) + 0.45 * COALESCE(cf.complaint_index, 0))::numeric, 1) AS quick_risk_score
FROM dim_center c
LEFT JOIN score_anomaly sa  ON c.center_id = sa.center_id
LEFT JOIN complaint_freq cf ON c.center_id = cf.center_id
WHERE COALESCE(sa.score_anomaly_index, 0) > 60 OR COALESCE(cf.complaint_index, 0) > 80
ORDER BY quick_risk_score DESC;

-- 3b. Center performance summary — one-stop reference for the Center Analytics dashboard
CREATE OR REPLACE VIEW vw_center_performance_summary AS
SELECT
    c.center_id,
    c.center_name,
    c.state_name,
    c.district_name,
    COUNT(f.candidate_id)                                            AS candidates_allocated,
    SUM(CASE WHEN f.attendance_status = 'present' THEN 1 ELSE 0 END) AS candidates_present,
    ROUND(100.0 * SUM(CASE WHEN f.attendance_status = 'present' THEN 1 ELSE 0 END)
          / NULLIF(COUNT(f.candidate_id), 0), 1)                    AS attendance_rate_pct,
    ROUND(AVG(f.total_score), 1)                                     AS avg_total_score,
    ROUND(STDDEV(f.total_score), 1)                                  AS score_stddev,
    (SELECT COUNT(*) FROM fact_complaint comp WHERE comp.center_id = c.center_id) AS complaint_count,
    (SELECT COUNT(*) FROM fact_incident inc WHERE inc.center_id = c.center_id)    AS incident_count,
    c.is_synthetic_anomalous_center
FROM dim_center c
LEFT JOIN fact_exam_performance f ON c.center_id = f.center_id
GROUP BY c.center_id, c.center_name, c.state_name, c.district_name, c.is_synthetic_anomalous_center;

-- ============================================================================
-- 4. STORED PROCEDURE — Monthly Integrity Report
--    Re-runnable, auditable, versioned risk scoring (rather than ad hoc scripts)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fact_risk_score_history (
    risk_score_id       SERIAL PRIMARY KEY,
    center_id            INT REFERENCES dim_center(center_id),
    computed_at           TIMESTAMP DEFAULT NOW(),
    score_anomaly_index    NUMERIC(6,2),
    complaint_index         NUMERIC(6,2),
    attendance_index        NUMERIC(6,2),
    capacity_index           NUMERIC(6,2),
    infra_risk_index          NUMERIC(6,2),
    historical_risk_index     NUMERIC(6,2),
    composite_integrity_risk_score NUMERIC(6,2)
);

CREATE OR REPLACE PROCEDURE generate_monthly_integrity_report()
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO fact_risk_score_history (
        center_id, score_anomaly_index, complaint_index, attendance_index,
        capacity_index, infra_risk_index, historical_risk_index, composite_integrity_risk_score
    )
    WITH center_score_stats AS (
        SELECT center_id, AVG(response_time_variance) AS avg_rt_variance,
               AVG(changed_answer_correct_rate) AS avg_changed_correct_rate
        FROM fact_exam_performance WHERE attendance_status = 'present' GROUP BY center_id
    ),
    score_anomaly AS (
        SELECT center_id,
            100 * (1 - (avg_rt_variance - MIN(avg_rt_variance) OVER ()) /
                   NULLIF(MAX(avg_rt_variance) OVER () - MIN(avg_rt_variance) OVER (), 0)) * 0.5
            +
            100 * (avg_changed_correct_rate - MIN(avg_changed_correct_rate) OVER ()) /
                   NULLIF(MAX(avg_changed_correct_rate) OVER () - MIN(avg_changed_correct_rate) OVER (), 0) * 0.5
            AS score_anomaly_index
        FROM center_score_stats
    ),
    complaint_freq AS (
        SELECT c.center_id, 100 * PERCENT_RANK() OVER (ORDER BY COUNT(comp.complaint_id)) AS complaint_index
        FROM dim_center c LEFT JOIN fact_complaint comp ON c.center_id = comp.center_id
        GROUP BY c.center_id
    ),
    attendance_anomaly AS (
        SELECT center_id,
            100 * (1 - ABS(AVG(CASE WHEN attendance_status = 'present' THEN 1 ELSE 0 END) - 0.955) / 0.955) AS attendance_index
        FROM fact_exam_performance GROUP BY center_id
    ),
    capacity_util AS (
        SELECT center_id, 100 * (1 - internet_reliability_score / 100.0) AS capacity_index FROM dim_center
    ),
    infra_index AS (
        SELECT center_id,
            100 * (1 - ((cctv_camera_count::NUMERIC + biometric_device_count + perimeter_security_rating)
                / NULLIF((SELECT MAX(cctv_camera_count + biometric_device_count + perimeter_security_rating) FROM dim_center), 0)))
            AS infra_risk_index
        FROM dim_center
    ),
    historical_integrity AS (
        SELECT center_id, COALESCE(100 * PERCENT_RANK() OVER (ORDER BY COUNT(*) DESC), 0) AS historical_risk_index
        FROM fact_audit_finding af JOIN fact_audit a ON af.audit_id = a.audit_id GROUP BY center_id
    )
    SELECT
        c.center_id,
        ROUND(COALESCE(sa.score_anomaly_index, 0)::numeric, 1),
        ROUND(COALESCE(cf.complaint_index, 0)::numeric, 1),
        ROUND(COALESCE(aa.attendance_index, 0)::numeric, 1),
        ROUND(COALESCE(cu.capacity_index, 0)::numeric, 1),
        ROUND(COALESCE(ii.infra_risk_index, 0)::numeric, 1),
        ROUND(COALESCE(hi.historical_risk_index, 0)::numeric, 1),
        ROUND(
            (0.30 * COALESCE(sa.score_anomaly_index, 0) + 0.25 * COALESCE(cf.complaint_index, 0) +
            0.15 * COALESCE(aa.attendance_index, 0) + 0.10 * COALESCE(cu.capacity_index, 0) +
            0.10 * COALESCE(ii.infra_risk_index, 0) + 0.10 * COALESCE(hi.historical_risk_index, 0))::numeric
        , 1)
    FROM dim_center c
    LEFT JOIN score_anomaly sa ON c.center_id = sa.center_id
    LEFT JOIN complaint_freq cf ON c.center_id = cf.center_id
    LEFT JOIN attendance_anomaly aa ON c.center_id = aa.center_id
    LEFT JOIN capacity_util cu ON c.center_id = cu.center_id
    LEFT JOIN infra_index ii ON c.center_id = ii.center_id
    LEFT JOIN historical_integrity hi ON c.center_id = hi.center_id;

    RAISE NOTICE 'Monthly integrity report generated: % centers scored', (SELECT COUNT(*) FROM dim_center);
END;
$$;
