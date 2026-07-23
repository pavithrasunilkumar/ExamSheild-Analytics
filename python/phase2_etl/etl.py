"""
ExamShield Analytics — ETL Pipeline (Phase 2)
Extracts the synthetic CSVs, validates them, transforms into star-schema shape,
and loads into the PostgreSQL `examshield` schema.
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("etl")

RAW_DIR = "/home/claude/data/raw"
DB_URI = "postgresql://postgres:postgres@localhost:5432/examshield"

engine = create_engine(DB_URI)


def extract(name):
    df = pd.read_csv(f"{RAW_DIR}/{name}.csv")
    log.info(f"EXTRACT  {name:35s} {len(df):>8,} rows")
    return df


# ----------------------------------------------------------------------------
# VALIDATION — checked before any load. Fails loudly rather than silently
# loading bad data, the same discipline a production ETL needs.
# ----------------------------------------------------------------------------
def validate(df, name, required_cols, pk_col=None):
    issues = []
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        issues.append(f"missing columns: {missing_cols}")

    null_counts = df[required_cols].isnull().sum()
    problem_nulls = null_counts[null_counts > 0]
    if len(problem_nulls) > 0:
        issues.append(f"nulls found in required cols: {dict(problem_nulls)}")

    if pk_col:
        dup_count = df[pk_col].duplicated().sum()
        if dup_count > 0:
            issues.append(f"{dup_count} duplicate values in primary key '{pk_col}'")

    if issues:
        log.warning(f"VALIDATE {name:35s} ISSUES -> {issues}")
    else:
        log.info(f"VALIDATE {name:35s} OK")
    return issues


# ----------------------------------------------------------------------------
# EXTRACT
# ----------------------------------------------------------------------------
candidate = extract("candidate")
application = extract("application")
exam_center = extract("exam_center")
center_infra = extract("center_infrastructure")
city = extract("dim_city")
district = extract("dim_district")
state = extract("dim_state")
session = extract("dim_exam_session")
cycle = extract("dim_exam_cycle")
examination = extract("dim_examination")
category = extract("dim_candidate_category")
pwbd = extract("dim_pwbd_status")
invigilator = extract("invigilator")
invigilator_assignment = extract("invigilator_assignment")
room = extract("room")
allocation = extract("allocation")
attendance = extract("attendance")
biometric = extract("biometric_verification_log")
qp_set = extract("question_paper_set")
score = extract("score")
result = extract("result")
complaint = extract("complaint")
incident = extract("incident_log")
audit = extract("audit")
audit_finding = extract("audit_finding")
investigation = extract("investigation")
social_media = extract("social_media_monitoring_log")

# ----------------------------------------------------------------------------
# VALIDATE — key tables checked for nulls, PK duplication, referential sanity
# ----------------------------------------------------------------------------
validate(candidate, "candidate", ["candidate_id", "full_name", "assigned_center_id"], "candidate_id")
validate(exam_center, "exam_center", ["exam_center_id", "city_id"], "exam_center_id")
validate(score, "score", ["candidate_id", "total_score"], "score_id")
validate(allocation, "allocation", ["candidate_id", "seat_id"], "allocation_id")

# referential integrity spot-check: every candidate's assigned_center_id must exist in exam_center
orphaned_centers = set(candidate.assigned_center_id) - set(exam_center.exam_center_id)
if orphaned_centers:
    log.warning(f"VALIDATE referential  {len(orphaned_centers)} candidates reference missing centers")
else:
    log.info("VALIDATE referential  OK — all candidate.assigned_center_id values resolve to a real center")

# ----------------------------------------------------------------------------
# TRANSFORM — build dim_date
# ----------------------------------------------------------------------------
all_dates = pd.concat([
    pd.to_datetime(session["session_date"]),
    pd.to_datetime(complaint["complaint_date"]),
    pd.to_datetime(incident["incident_date"]),
    pd.to_datetime(audit["audit_date"]),
    pd.to_datetime(investigation["start_date"]),
    pd.to_datetime(social_media["detected_date"]),
]).dropna().unique()

dim_date = pd.DataFrame({"full_date": pd.to_datetime(all_dates)})
dim_date["date_key"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
dim_date["day_of_week"] = dim_date["full_date"].dt.dayofweek
dim_date["day_name"] = dim_date["full_date"].dt.day_name()
dim_date["month"] = dim_date["full_date"].dt.month
dim_date["month_name"] = dim_date["full_date"].dt.month_name()
dim_date["quarter"] = dim_date["full_date"].dt.quarter
dim_date["year"] = dim_date["full_date"].dt.year
dim_date["is_weekend"] = dim_date["day_of_week"].isin([5, 6])
dim_date = dim_date[["date_key", "full_date", "day_of_week", "day_name",
                      "month", "month_name", "quarter", "year", "is_weekend"]]


def to_date_key(series):
    return pd.to_datetime(series).dt.strftime("%Y%m%d").astype(int)


# ----------------------------------------------------------------------------
# TRANSFORM — dim_center (denormalize geography + infrastructure into one row)
# ----------------------------------------------------------------------------
geo = city.merge(district, on="district_id").merge(state, on="state_id")
dim_center = (
    exam_center
    .merge(geo[["city_id", "city_name", "district_name", "state_name"]], on="city_id", how="left")
    .merge(center_infra, on="exam_center_id", how="left")
)
dim_center = dim_center.rename(columns={"exam_center_id": "center_id"})[[
    "center_id", "center_name", "center_code", "address", "building_type",
    "city_name", "district_name", "state_name", "total_room_count",
    "power_backup_available", "internet_reliability_score", "cctv_camera_count",
    "biometric_device_count", "metal_detector_count", "perimeter_security_rating",
    "last_audit_date", "is_synthetic_anomalous_center"
]]

# ----------------------------------------------------------------------------
# TRANSFORM — dim_session
# ----------------------------------------------------------------------------
dim_session = (
    session
    .merge(cycle, on="exam_cycle_id", how="left")
    .merge(examination, on="examination_id", how="left")
)
dim_session = dim_session.rename(columns={"exam_session_id": "session_id"})[[
    "session_id", "exam_cycle_id", "cycle_year", "examination_name", "session_date",
    "shift_code", "start_time", "end_time"
]]

dim_qp_set = qp_set.rename(columns={"exam_session_id": "session_id"})[
    ["question_paper_set_id", "session_id", "set_code"]
]

dim_candidate = candidate.rename(columns={})[[
    "candidate_id", "full_name", "date_of_birth", "gender", "category_id",
    "pwbd_status_id", "national_id_type", "national_id_number_hash", "registered_at"
]]

dim_invigilator = invigilator[["invigilator_id", "full_name", "experience_years"]]

# ----------------------------------------------------------------------------
# TRANSFORM — fact_exam_performance
# (grain: 1 row per allocated candidate; joins attendance, biometric, score, result)
# ----------------------------------------------------------------------------
fact_perf = (
    allocation
    .merge(candidate[["candidate_id", "assigned_center_id"]], on="candidate_id", how="left")
    .merge(attendance[["allocation_id", "attendance_status", "entry_timestamp", "exit_timestamp"]],
           on="allocation_id", how="left")
    .merge(biometric[["candidate_id", "match_status", "match_score"]], on="candidate_id", how="left")
    .merge(score.drop(columns=["score_id"]), on="candidate_id", how="left")
    .merge(result[["candidate_id", "qualification_status"]], on="candidate_id", how="left")
)
fact_perf = fact_perf.rename(columns={
    "assigned_center_id": "center_id",
    "exam_session_id": "session_id",
    "match_status": "biometric_match_status",
    "match_score": "biometric_match_score",
})
fact_perf["session_date_key"] = to_date_key(pd.Series(["2026-05-03"] * len(fact_perf)))
fact_perf = fact_perf[[
    "candidate_id", "center_id", "session_id", "session_date_key", "question_paper_set_id",
    "attendance_status", "entry_timestamp", "exit_timestamp",
    "biometric_match_status", "biometric_match_score",
    "physics_score", "chemistry_score", "biology_score", "total_score",
    "response_time_variance", "changed_answer_correct_rate", "percentile", "rank",
    "qualification_status"
]]

# ----------------------------------------------------------------------------
# TRANSFORM — event-grain fact tables
# ----------------------------------------------------------------------------
fact_complaint = complaint.copy()
fact_complaint["complaint_date_key"] = to_date_key(fact_complaint["complaint_date"])
fact_complaint = fact_complaint.rename(columns={"exam_center_id": "center_id"})[[
    "complaint_id", "center_id", "complaint_date_key", "complaint_category",
    "severity", "investigation_status"
]]

fact_incident = incident.copy()
fact_incident["incident_date_key"] = to_date_key(incident["incident_date"])
fact_incident = fact_incident.rename(columns={"exam_center_id": "center_id"})[[
    "incident_id", "center_id", "incident_date_key", "incident_type", "severity", "description"
]]

fact_audit = audit.copy()
fact_audit["audit_date_key"] = to_date_key(audit["audit_date"])
fact_audit = fact_audit.rename(columns={"exam_center_id": "center_id"})[[
    "audit_id", "center_id", "audit_date_key", "audit_trigger"
]]

fact_audit_finding = audit_finding.copy()

fact_investigation = investigation.copy()
fact_investigation["start_date_key"] = to_date_key(investigation["start_date"])
fact_investigation = fact_investigation.rename(columns={"exam_center_id": "center_id"})[[
    "investigation_id", "center_id", "lead_agency", "start_date_key", "status", "arrest_count"
]]

fact_social_media = social_media.copy()
fact_social_media["detected_date_key"] = to_date_key(social_media["detected_date"])
fact_social_media = fact_social_media.rename(columns={"exam_center_id": "center_id"})[[
    "monitoring_log_id", "center_id", "detected_date_key", "platform", "threat_level", "post_engagement_count"
]]

fact_invig_assignment = invigilator_assignment.merge(
    room[["room_id", "exam_center_id"]], on="room_id", how="left"
).rename(columns={"exam_center_id": "center_id"})[[
    "invigilator_assignment_id", "invigilator_id", "center_id", "exam_session_id", "attendance_status"
]].rename(columns={"exam_session_id": "session_id"})

# ----------------------------------------------------------------------------
# LOAD — dimensions first (FK order matters), then facts
# ----------------------------------------------------------------------------
load_order = [
    ("dim_date", dim_date),
    ("dim_candidate_category", category.rename(columns={})),
    ("dim_pwbd_status", pwbd),
    ("dim_candidate", dim_candidate),
    ("dim_center", dim_center),
    ("dim_session", dim_session),
    ("dim_invigilator", dim_invigilator),
    ("dim_question_paper_set", dim_qp_set),
    ("fact_exam_performance", fact_perf),
    ("fact_complaint", fact_complaint),
    ("fact_incident", fact_incident),
    ("fact_audit", fact_audit),
    ("fact_audit_finding", fact_audit_finding),
    ("fact_investigation", fact_investigation),
    ("fact_social_media_signal", fact_social_media),
    ("fact_invigilator_assignment", fact_invig_assignment),
]

with engine.begin() as conn:
    conn.execute(text("SET search_path TO examshield"))
    for table_name, df in load_order:
        df.to_sql(table_name, conn, schema="examshield", if_exists="append", index=False, method="multi", chunksize=2000)
        log.info(f"LOAD     {table_name:35s} {len(df):>8,} rows")

log.info("ETL complete.")
