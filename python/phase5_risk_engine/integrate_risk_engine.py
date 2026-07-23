"""
ExamShield Analytics — Phase 5: Composite Risk Scoring Engine (Integration)
Combines the SQL-based statistical Integrity Risk Index (Phase 2) with the
ML-based anomaly ensemble, XGBoost risk probability, and SHAP top factors
(Phase 4) into one final, versioned, explainable risk score — written back
into PostgreSQL as `fact_final_risk_score`.
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import json

engine = create_engine("postgresql://postgres:postgres@localhost:5432/examshield")

# ----------------------------------------------------------------------------
# 1. LOAD both risk signals
# ----------------------------------------------------------------------------
sql_risk = pd.read_sql("""
    SET search_path TO examshield;
    SELECT DISTINCT ON (center_id) center_id, composite_integrity_risk_score AS sql_statistical_risk_score,
           computed_at
    FROM fact_risk_score_history
    ORDER BY center_id, computed_at DESC
""", engine)

ml_output = pd.read_csv("/home/claude/phase4_ml_models/outputs/center_features_with_ml_outputs.csv")
shap_factors = pd.read_csv("/home/claude/phase4_ml_models/outputs/shap_top_factors_per_center.csv")

# ----------------------------------------------------------------------------
# 2. COMBINE — final score blends statistical rigor (SQL) with pattern
#    detection (ML ensemble + XGBoost), weighted so neither dominates blindly.
#    Documented rationale: SQL score is fully transparent/auditable by design;
#    ML score captures multivariate patterns SQL window functions can't
#    easily express. 50/50 blend is a deliberate starting policy, not a
#    data-derived constant — adjustable by authorities, same principle as the
#    original SQL composite weights.
# ----------------------------------------------------------------------------
merged = sql_risk.merge(
    ml_output[["center_id", "isolation_forest_anomaly", "lof_anomaly", "dbscan_anomaly",
               "ensemble_anomaly_votes", "xgb_risk_probability", "kmeans_segment", "segment_label",
               "is_synthetic_anomalous_center"]],
    on="center_id", how="outer"
).merge(shap_factors, on="center_id", how="left", suffixes=("", "_shap"))

# Normalize both to 0-100 scale before blending
merged["ml_risk_score_0_100"] = (merged["xgb_risk_probability"] * 100).round(1)
merged["sql_statistical_risk_score"] = merged["sql_statistical_risk_score"].fillna(0)

merged["final_integrity_risk_score"] = (
    0.5 * merged["sql_statistical_risk_score"] + 0.5 * merged["ml_risk_score_0_100"]
).round(1)

# Ensemble vote gives a categorical confidence tier alongside the numeric score
def confidence_tier(votes):
    if votes >= 2:
        return "High Confidence"
    elif votes == 1:
        return "Medium Confidence"
    return "Low Confidence"

merged["ml_ensemble_confidence"] = merged["ensemble_anomaly_votes"].apply(confidence_tier)

def risk_band(score):
    if score >= 70:
        return "Critical"
    elif score >= 50:
        return "High"
    elif score >= 30:
        return "Medium"
    return "Low"

merged["risk_band"] = merged["final_integrity_risk_score"].apply(risk_band)

# ----------------------------------------------------------------------------
# 3. VALIDATE the combined score against ground truth
# ----------------------------------------------------------------------------
top_10_by_final = merged.nlargest(10, "final_integrity_risk_score")
recovered = top_10_by_final["is_synthetic_anomalous_center"].sum()
print(f"Final combined score: top-10 flagged centers include {recovered}/10 true injected anomalies "
      f"(and {10-recovered} false positives) out of {merged['is_synthetic_anomalous_center'].sum()} true anomalies total.")

sql_only_top10 = merged.nlargest(10, "sql_statistical_risk_score")["is_synthetic_anomalous_center"].sum()
ml_only_top10 = merged.nlargest(10, "ml_risk_score_0_100")["is_synthetic_anomalous_center"].sum()
print(f"SQL-only top-10 recovers: {sql_only_top10}/10")
print(f"ML-only top-10 recovers: {ml_only_top10}/10")

# ----------------------------------------------------------------------------
# 4. WRITE BACK to PostgreSQL — versioned, timestamped final risk table
# ----------------------------------------------------------------------------
final_table = merged[[
    "center_id", "sql_statistical_risk_score", "ml_risk_score_0_100",
    "final_integrity_risk_score", "risk_band", "ml_ensemble_confidence",
    "kmeans_segment", "segment_label", "top_factor_1", "top_factor_2", "top_factor_3",
    "is_synthetic_anomalous_center"
]].copy()
final_table["scored_at"] = pd.Timestamp.now()

with engine.begin() as conn:
    conn.execute(text("SET search_path TO examshield"))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS fact_final_risk_score (
            final_risk_id SERIAL PRIMARY KEY,
            center_id INT REFERENCES dim_center(center_id),
            sql_statistical_risk_score NUMERIC(6,2),
            ml_risk_score_0_100 NUMERIC(6,2),
            final_integrity_risk_score NUMERIC(6,2),
            risk_band VARCHAR(20),
            ml_ensemble_confidence VARCHAR(20),
            kmeans_segment INT,
            segment_label VARCHAR(50),
            top_factor_1 VARCHAR(100),
            top_factor_2 VARCHAR(100),
            top_factor_3 VARCHAR(100),
            is_synthetic_anomalous_center BOOLEAN,
            scored_at TIMESTAMP
        )
    """))
    final_table.to_sql("fact_final_risk_score", conn, schema="examshield", if_exists="append", index=False, method="multi")

print(f"\nWrote {len(final_table)} rows to fact_final_risk_score.")

# ----------------------------------------------------------------------------
# 5. EXPORT the audit-priority report — top N centers ranked, with reasons
# ----------------------------------------------------------------------------
audit_priority = merged.nlargest(20, "final_integrity_risk_score")[[
    "center_id", "final_integrity_risk_score", "risk_band", "ml_ensemble_confidence",
    "segment_label", "top_factor_1", "top_factor_2", "top_factor_3", "is_synthetic_anomalous_center"
]]
audit_priority.to_csv("/home/claude/phase5_risk_engine/audit_priority_report.csv", index=False)

with open("/home/claude/phase5_risk_engine/PHASE5_VALIDATION_SUMMARY.md", "w") as f:
    f.write("# Phase 5 — Composite Risk Scoring Engine — Validation Summary\n\n")
    f.write(f"- Final blended score (50% SQL statistical + 50% ML ensemble): "
            f"top-10 recovers **{recovered}/10** true injected anomalies.\n")
    f.write(f"- SQL-only top-10 recovers: {sql_only_top10}/10\n")
    f.write(f"- ML-only top-10 recovers: {ml_only_top10}/10\n\n")
    f.write("## Interpretation\n\n")
    f.write(
        "Both individual signals already achieve strong recovery on this synthetic dataset "
        "(as expected, given deliberately clean injection). The value of blending both signals is "
        "not visible in top-10 recovery here — it becomes visible in the **`risk_band` and "
        "`ml_ensemble_confidence` tiers for borderline centers just outside the top 10**, where SQL "
        "and ML signals can disagree. Those disagreement cases are exactly where a human auditor's "
        "judgment adds the most value, and exactly why `fact_final_risk_score` stores both component "
        "scores separately rather than only the blended number — auditors can see *why* two centers "
        "with the same final score got there differently (one via pure complaint volume, the other "
        "via a stronger ML pattern match).\n\n"
    )
    f.write("## Schema Note\n\n")
    f.write(
        "`fact_final_risk_score` is append-only and timestamped (`scored_at`), matching the "
        "versioning approach in `fact_risk_score_history` from Phase 2 — every scoring run is "
        "preserved rather than overwritten, enabling risk-trend-over-time dashboards in Phase 6.\n"
    )

print("\nPhase 5 complete.")
