-- ============================================================================
-- ExamShield Analytics — Data Warehouse Schema (Star Schema)
-- ============================================================================
-- Design notes:
--   - Fact table grain: fact_exam_performance = 1 row per candidate per session
--   - Center + Infrastructure are denormalized into one dimension (legitimate
--     1:1 relationship — avoids an unnecessary join on every center query)
--   - Complaints/Incidents/Audits are separate, lower-grain fact tables
--     (center-level events, not candidate-level) — kept apart from the
--     performance fact table rather than forced into it
--   - is_synthetic_anomalous_center is carried through ONLY for model
--     validation later — never to be used as a training feature
-- ============================================================================

DROP SCHEMA IF EXISTS examshield CASCADE;
CREATE SCHEMA examshield;
SET search_path TO examshield;

-- ----------------------------------------------------------------------------
-- DIMENSION TABLES
-- ----------------------------------------------------------------------------

CREATE TABLE dim_date (
    date_key        INT PRIMARY KEY,          -- YYYYMMDD
    full_date       DATE NOT NULL,
    day_of_week     SMALLINT NOT NULL,
    day_name        VARCHAR(10) NOT NULL,
    month           SMALLINT NOT NULL,
    month_name      VARCHAR(10) NOT NULL,
    quarter         SMALLINT NOT NULL,
    year            SMALLINT NOT NULL,
    is_weekend      BOOLEAN NOT NULL
);

CREATE TABLE dim_candidate_category (
    category_id     INT PRIMARY KEY,
    category_code   VARCHAR(10) NOT NULL,
    category_name   VARCHAR(50) NOT NULL
);

CREATE TABLE dim_pwbd_status (
    pwbd_status_id      INT PRIMARY KEY,
    disability_type      VARCHAR(50),
    accommodation_required VARCHAR(100),
    certificate_reference VARCHAR(20)
);

CREATE TABLE dim_candidate (
    candidate_id        INT PRIMARY KEY,
    full_name           VARCHAR(150),
    date_of_birth       DATE,
    gender              VARCHAR(10),
    category_id         INT REFERENCES dim_candidate_category(category_id),
    pwbd_status_id      INT REFERENCES dim_pwbd_status(pwbd_status_id),
    national_id_type    VARCHAR(20),
    national_id_number_hash VARCHAR(64),
    registered_at       TIMESTAMP
);

CREATE TABLE dim_center (
    center_id                   INT PRIMARY KEY,
    center_name                 VARCHAR(200),
    center_code                 VARCHAR(20),
    address                     VARCHAR(250),
    building_type               VARCHAR(30),
    city_name                   VARCHAR(100),
    district_name               VARCHAR(100),
    state_name                  VARCHAR(100),
    total_room_count            SMALLINT,
    power_backup_available      BOOLEAN,
    internet_reliability_score  SMALLINT,
    cctv_camera_count           SMALLINT,
    biometric_device_count      SMALLINT,
    metal_detector_count        SMALLINT,
    perimeter_security_rating   SMALLINT,
    last_audit_date             DATE,
    is_synthetic_anomalous_center BOOLEAN  -- ground truth flag; validation only, never a model feature
);

CREATE TABLE dim_session (
    session_id      INT PRIMARY KEY,
    exam_cycle_id   INT,
    cycle_year      SMALLINT,
    examination_name VARCHAR(100),
    session_date    DATE,
    shift_code      VARCHAR(20),
    start_time      VARCHAR(10),
    end_time        VARCHAR(10)
);

CREATE TABLE dim_invigilator (
    invigilator_id      INT PRIMARY KEY,
    full_name           VARCHAR(150),
    experience_years    SMALLINT
);

CREATE TABLE dim_question_paper_set (
    question_paper_set_id  INT PRIMARY KEY,
    session_id              INT REFERENCES dim_session(session_id),
    set_code                VARCHAR(10)
);

-- ----------------------------------------------------------------------------
-- FACT TABLES
-- ----------------------------------------------------------------------------

-- Grain: one row per candidate per exam session (candidates who were allocated)
CREATE TABLE fact_exam_performance (
    performance_id              SERIAL PRIMARY KEY,
    candidate_id                INT REFERENCES dim_candidate(candidate_id),
    center_id                   INT REFERENCES dim_center(center_id),
    session_id                  INT REFERENCES dim_session(session_id),
    session_date_key            INT REFERENCES dim_date(date_key),
    question_paper_set_id       INT REFERENCES dim_question_paper_set(question_paper_set_id),
    attendance_status           VARCHAR(10),          -- present / absent
    entry_timestamp              TIMESTAMP,
    exit_timestamp               TIMESTAMP,
    biometric_match_status       VARCHAR(10),
    biometric_match_score        SMALLINT,
    physics_score                NUMERIC(6,2),
    chemistry_score               NUMERIC(6,2),
    biology_score                 NUMERIC(6,2),
    total_score                   NUMERIC(6,2),
    response_time_variance        NUMERIC(6,2),
    changed_answer_correct_rate   NUMERIC(5,3),
    percentile                    NUMERIC(6,3),
    rank                          INT,
    qualification_status          VARCHAR(20)
);

-- Grain: one row per complaint
CREATE TABLE fact_complaint (
    complaint_id        INT PRIMARY KEY,
    center_id            INT REFERENCES dim_center(center_id),
    complaint_date_key   INT REFERENCES dim_date(date_key),
    complaint_category   VARCHAR(50),
    severity             VARCHAR(10),
    investigation_status VARCHAR(30)
);

-- Grain: one row per incident
CREATE TABLE fact_incident (
    incident_id     INT PRIMARY KEY,
    center_id        INT REFERENCES dim_center(center_id),
    incident_date_key INT REFERENCES dim_date(date_key),
    incident_type     VARCHAR(50),
    severity          VARCHAR(10),
    description       TEXT
);

-- Grain: one row per audit
CREATE TABLE fact_audit (
    audit_id        INT PRIMARY KEY,
    center_id        INT REFERENCES dim_center(center_id),
    audit_date_key    INT REFERENCES dim_date(date_key),
    audit_trigger     VARCHAR(30)
);

CREATE TABLE fact_audit_finding (
    audit_finding_id    INT PRIMARY KEY,
    audit_id             INT REFERENCES fact_audit(audit_id),
    finding_type          VARCHAR(50),
    severity              VARCHAR(10)
);

CREATE TABLE fact_investigation (
    investigation_id    INT PRIMARY KEY,
    center_id            INT REFERENCES dim_center(center_id),
    lead_agency           VARCHAR(50),
    start_date_key        INT REFERENCES dim_date(date_key),
    status                VARCHAR(20),
    arrest_count          SMALLINT
);

CREATE TABLE fact_social_media_signal (
    monitoring_log_id       INT PRIMARY KEY,
    center_id                INT REFERENCES dim_center(center_id),
    detected_date_key         INT REFERENCES dim_date(date_key),
    platform                  VARCHAR(20),
    threat_level               VARCHAR(10),
    post_engagement_count      INT
);

CREATE TABLE fact_invigilator_assignment (
    invigilator_assignment_id  INT PRIMARY KEY,
    invigilator_id              INT REFERENCES dim_invigilator(invigilator_id),
    center_id                    INT REFERENCES dim_center(center_id),
    session_id                   INT REFERENCES dim_session(session_id),
    attendance_status             VARCHAR(10)
);

-- ----------------------------------------------------------------------------
-- INDEXES — optimized for the join/filter patterns analytics will actually use
-- ----------------------------------------------------------------------------

CREATE INDEX idx_perf_center       ON fact_exam_performance(center_id);
CREATE INDEX idx_perf_candidate    ON fact_exam_performance(candidate_id);
CREATE INDEX idx_perf_session      ON fact_exam_performance(session_id);
CREATE INDEX idx_perf_total_score  ON fact_exam_performance(total_score);
CREATE INDEX idx_perf_center_score ON fact_exam_performance(center_id, total_score);

CREATE INDEX idx_complaint_center  ON fact_complaint(center_id);
CREATE INDEX idx_incident_center   ON fact_incident(center_id);
CREATE INDEX idx_audit_center      ON fact_audit(center_id);
CREATE INDEX idx_smsignal_center   ON fact_social_media_signal(center_id);

CREATE INDEX idx_center_state      ON dim_center(state_name);
CREATE INDEX idx_center_anomalous  ON dim_center(is_synthetic_anomalous_center);
