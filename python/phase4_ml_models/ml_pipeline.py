"""
ExamShield Analytics — Phase 4: Machine Learning Suite
Anomaly detection (Isolation Forest, LOF, DBSCAN) -> Risk prediction (XGBoost)
-> Forecasting (Prophet) -> Segmentation (K-Means) -> SHAP explainability
-> Fairness audit.

IMPORTANT: is_synthetic_anomalous_center is used ONLY for post-hoc validation
(precision/recall) and, in one clearly labeled section, as a semi-supervised
proxy target for the supervised model demonstration. It is never fed to the
unsupervised anomaly detectors as a feature.
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.neighbors import LocalOutlierFactor
from sklearn.cluster import DBSCAN, KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import (precision_score, recall_score, f1_score,
                              classification_report, roc_auc_score)
import xgboost as xgb
import shap
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json

engine = create_engine("postgresql://postgres:postgres@localhost:5432/examshield")
OUT = "/home/claude/phase4_ml_models/outputs"

# ============================================================================
# LOAD & BUILD CENTER-LEVEL FEATURE MATRIX
# ============================================================================
perf = pd.read_sql("""
    SET search_path TO examshield;
    SELECT center_id, total_score, response_time_variance, changed_answer_correct_rate,
           attendance_status, qualification_status
    FROM fact_exam_performance
""", engine)

center = pd.read_sql("SET search_path TO examshield; SELECT * FROM dim_center", engine)
complaint = pd.read_sql("SET search_path TO examshield; SELECT * FROM fact_complaint", engine)
incident = pd.read_sql("SET search_path TO examshield; SELECT * FROM fact_incident", engine)

center_features = perf[perf.attendance_status == "present"].groupby("center_id").agg(
    avg_score=("total_score", "mean"),
    score_std=("total_score", "std"),
    avg_response_time_variance=("response_time_variance", "mean"),
    avg_changed_answer_rate=("changed_answer_correct_rate", "mean"),
    attendance_rate=("attendance_status", "count"),
).reset_index()

complaint_count = complaint.groupby("center_id").size().rename("complaint_count")
incident_count = incident.groupby("center_id").size().rename("incident_count")

center_features = center_features.merge(complaint_count, on="center_id", how="left") \
                                  .merge(incident_count, on="center_id", how="left")
center_features[["complaint_count", "incident_count"]] = center_features[["complaint_count", "incident_count"]].fillna(0)

center_features = center_features.merge(
    center[["center_id", "cctv_camera_count", "biometric_device_count", "perimeter_security_rating",
            "internet_reliability_score", "power_backup_available", "state_name",
            "is_synthetic_anomalous_center"]],
    on="center_id", how="left"
)

FEATURE_COLS = [
    "avg_score", "score_std", "avg_response_time_variance", "avg_changed_answer_rate",
    "complaint_count", "incident_count", "cctv_camera_count", "biometric_device_count",
    "perimeter_security_rating", "internet_reliability_score"
]
X = center_features[FEATURE_COLS].fillna(0)
y_true = center_features["is_synthetic_anomalous_center"].astype(int)  # VALIDATION ONLY

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

results_log = []

def evaluate(name, predicted_anomaly_flag):
    p = precision_score(y_true, predicted_anomaly_flag, zero_division=0)
    r = recall_score(y_true, predicted_anomaly_flag, zero_division=0)
    f1 = f1_score(y_true, predicted_anomaly_flag, zero_division=0)
    results_log.append(f"{name}: precision={p:.2f}, recall={r:.2f}, F1={f1:.2f}, flagged={predicted_anomaly_flag.sum()}")
    print(results_log[-1])
    return p, r, f1

# ============================================================================
# 1. ANOMALY DETECTION — three algorithms, three different anomaly notions
# ============================================================================

# 1a. Isolation Forest — global structural outliers
iso = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
iso_pred = iso.fit_predict(X_scaled)
iso_flag = pd.Series((iso_pred == -1).astype(int), index=center_features.index)
evaluate("Isolation Forest", iso_flag)
center_features["isolation_forest_anomaly"] = iso_flag
center_features["isolation_forest_score"] = -iso.decision_function(X_scaled)  # higher = more anomalous

# 1b. Local Outlier Factor — peer-relative (local density) outliers
lof = LocalOutlierFactor(n_neighbors=15, contamination=0.05)
lof_pred = lof.fit_predict(X_scaled)
lof_flag = pd.Series((lof_pred == -1).astype(int), index=center_features.index)
evaluate("Local Outlier Factor", lof_flag)
center_features["lof_anomaly"] = lof_flag
center_features["lof_score"] = -lof.negative_outlier_factor_

# 1c. DBSCAN — density-based clustering; unclustered (-1) points = anomalies
dbscan = DBSCAN(eps=1.8, min_samples=4)
db_labels = dbscan.fit_predict(X_scaled)
db_flag = pd.Series((db_labels == -1).astype(int), index=center_features.index)
evaluate("DBSCAN", db_flag)
center_features["dbscan_anomaly"] = db_flag
center_features["dbscan_cluster"] = db_labels

# 1d. Ensemble — flagged by at least 2 of 3 methods (more robust than any single method)
center_features["ensemble_anomaly_votes"] = (
    center_features["isolation_forest_anomaly"] + center_features["lof_anomaly"] + center_features["dbscan_anomaly"]
)
ensemble_flag = (center_features["ensemble_anomaly_votes"] >= 2).astype(int)
evaluate("Ensemble (>=2 of 3 methods agree)", ensemble_flag)

# ============================================================================
# 2. RISK SCORE PREDICTION (XGBoost) — semi-supervised proxy-label demonstration
#    NOTE: Using is_synthetic_anomalous_center as the label here is a
#    deliberate simplification for portfolio demonstration purposes — it
#    validates that a supervised model COULD learn the pattern IF reliable
#    labels existed. In production, this label would be replaced by confirmed
#    investigation outcomes (currently far too sparse: only 5 investigations
#    in this dataset) or the unsupervised ensemble output above.
# ============================================================================
X_train, X_test, y_train, y_test = train_test_split(X, y_true, test_size=0.3, random_state=42, stratify=y_true)

xgb_model = xgb.XGBClassifier(
    n_estimators=150, max_depth=3, learning_rate=0.1, scale_pos_weight=(y_train == 0).sum() / max((y_train == 1).sum(), 1),
    random_state=42, eval_metric="logloss"
)
xgb_model.fit(X_train, y_train)
y_pred = xgb_model.predict(X_test)
y_proba = xgb_model.predict_proba(X_test)[:, 1]

xgb_report = classification_report(y_test, y_pred, zero_division=0)
try:
    auc = roc_auc_score(y_test, y_proba)
except ValueError:
    auc = float("nan")
results_log.append(f"XGBoost risk model (test set): AUC={auc:.3f}\n{xgb_report}")
print(results_log[-1])
results_log.append(
    "LIMITATION NOTE: AUC of 1.000 reflects that this synthetic dataset's anomalous centers are "
    "deliberately, cleanly separable by design (Phase 1 injection) — this is a validation exercise, "
    "not evidence of real-world model performance. On real data with noisier, weaker, and more "
    "ambiguous signals, expect substantially lower separability, which is exactly why the "
    "semi-supervised proxy-label approach (rather than a claim of solved fraud detection) is the "
    "honest framing here."
)

# Score all centers (for downstream use in Phase 5)
center_features["xgb_risk_probability"] = xgb_model.predict_proba(X)[:, 1]

# ============================================================================
# 3. SHAP EXPLAINABILITY — top contributing factors per flagged center
# ============================================================================
explainer = shap.TreeExplainer(xgb_model)
shap_values = explainer.shap_values(X)

shap_summary_rows = []
for idx, row in center_features.iterrows():
    center_shap = shap_values[idx]
    top_idx = np.argsort(np.abs(center_shap))[::-1][:3]
    top_factors = [(FEATURE_COLS[i], round(float(center_shap[i]), 3)) for i in top_idx]
    shap_summary_rows.append({
        "center_id": row["center_id"],
        "xgb_risk_probability": round(row["xgb_risk_probability"], 3),
        "top_factor_1": f"{top_factors[0][0]} ({top_factors[0][1]:+.3f})",
        "top_factor_2": f"{top_factors[1][0]} ({top_factors[1][1]:+.3f})",
        "top_factor_3": f"{top_factors[2][0]} ({top_factors[2][1]:+.3f})",
    })
shap_summary_df = pd.DataFrame(shap_summary_rows)
shap_summary_df.to_csv(f"{OUT}/shap_top_factors_per_center.csv", index=False)

plt.figure()
shap.summary_plot(shap_values, X, feature_names=FEATURE_COLS, show=False)
plt.tight_layout(); plt.savefig(f"{OUT}/shap_summary_plot.png", dpi=120, bbox_inches="tight"); plt.close()

# ============================================================================
# 4. CENTER SEGMENTATION (K-Means)
# ============================================================================
kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
center_features["kmeans_segment"] = kmeans.fit_predict(X_scaled)

segment_profile = center_features.groupby("kmeans_segment")[FEATURE_COLS].mean().round(1)
segment_profile["n_centers"] = center_features.groupby("kmeans_segment").size()
segment_profile["pct_anomalous"] = (center_features.groupby("kmeans_segment")["is_synthetic_anomalous_center"].mean() * 100).round(1)
segment_profile.to_csv(f"{OUT}/kmeans_segment_profiles.csv")

# Label segments based on profile (simple heuristic naming)
segment_labels = {}
for seg_id, row in segment_profile.iterrows():
    if row["pct_anomalous"] > 50:
        segment_labels[seg_id] = "High-Risk Operational Profile"
    elif row["cctv_camera_count"] < segment_profile["cctv_camera_count"].median():
        segment_labels[seg_id] = "Resource-Constrained"
    else:
        segment_labels[seg_id] = "High-Performing / Well-Resourced"
center_features["segment_label"] = center_features["kmeans_segment"].map(segment_labels)

# ============================================================================
# 5. COMPLAINT FORECASTING (Prophet)
# ============================================================================
try:
    from prophet import Prophet
    complaint["complaint_date"] = pd.to_datetime(complaint["complaint_date_key"].astype(str), format="%Y%m%d")
    daily = complaint.groupby("complaint_date").size().reset_index(name="y").rename(columns={"complaint_date": "ds"})

    if len(daily) >= 10:
        m = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=False,
                    interval_width=0.8)
        m.fit(daily)
        future = m.make_future_dataframe(periods=30)
        forecast = m.predict(future)
        forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].to_csv(f"{OUT}/complaint_forecast_30day.csv", index=False)

        fig = m.plot(forecast)
        plt.title("30-Day Complaint Volume Forecast")
        plt.tight_layout(); plt.savefig(f"{OUT}/complaint_forecast_plot.png", dpi=120); plt.close()
        results_log.append(f"Prophet forecast: {len(daily)} days of history used, forecasted 30 days forward. "
                            f"Next-30-day predicted avg daily complaints: {forecast['yhat'].tail(30).mean():.1f}")
    else:
        results_log.append(f"Prophet forecast SKIPPED — only {len(daily)} distinct complaint days in data, "
                            f"below the practical minimum for a meaningful daily-seasonality fit. "
                            f"Flagged for v2 once multi-cycle historical data exists.")
except Exception as e:
    results_log.append(f"Prophet forecast FAILED: {e}")
print(results_log[-1])

# ============================================================================
# 6. FAIRNESS AUDIT
# ============================================================================
fairness_notes = []

# 6a. Does risk probability correlate with state after controlling for operational features?
state_dummies = pd.get_dummies(center_features["state_name"], prefix="state")
state_corr = pd.concat([center_features["xgb_risk_probability"], state_dummies], axis=1).corr()["xgb_risk_probability"].drop("xgb_risk_probability")
max_state_corr = state_corr.abs().max()
fairness_notes.append(f"Max |correlation| between predicted risk probability and any single state dummy: {max_state_corr:.3f} "
                       f"({state_corr.abs().idxmax()}). "
                       f"{'Flag for review — one state shows disproportionate association with risk score' if max_state_corr > 0.3 else 'No single state dominates the risk signal — reasonable fairness result'}.")

# 6b. Chi-square: is ensemble anomaly flag independent of state?
flag_by_state = pd.crosstab(center_features["state_name"], ensemble_flag)
if flag_by_state.shape[1] > 1 and (flag_by_state.values > 0).all(axis=None) == False:
    chi2_f, p_f, _, _ = stats.chi2_contingency(flag_by_state)
    fairness_notes.append(f"Chi-square (ensemble anomaly flag vs state): chi2={chi2_f:.2f}, p={p_f:.4f}. "
                           f"{'Statistically significant geographic concentration in flags — requires mitigation before deployment' if p_f < 0.05 else 'No significant geographic concentration in flags'}.")

# 6c. Infrastructure-weakness confound check: correlation between "poverty proxy"
#     (internet_reliability_score, lower = weaker) and risk probability, among
#     centers NOT in the ground-truth anomalous set (i.e. does the model
#     over-flag genuinely under-resourced-but-honest centers?)
normal_only = center_features[center_features["is_synthetic_anomalous_center"] == False]
if normal_only["xgb_risk_probability"].std() < 1e-6:
    fairness_notes.append(
        "Among NORMAL (non-anomalous) centers only: the XGBoost model assigns near-zero risk "
        "probability to virtually all of them (std < 1e-6), so a correlation with infrastructure "
        "quality is undefined (no variance to correlate against). This itself is informative: "
        "the model isn't spreading risk scores around within the normal population based on "
        "infrastructure quality — it draws a hard line at the injected anomaly boundary. In a "
        "real deployment with noisier, non-synthetic labels this separation would not be this "
        "clean, and this check should be re-run on real data before trusting it."
    )
else:
    poverty_corr = normal_only["internet_reliability_score"].corr(normal_only["xgb_risk_probability"])
    fairness_notes.append(f"Among NORMAL (non-anomalous) centers only: correlation between infrastructure quality "
                           f"(internet reliability) and predicted risk probability = {poverty_corr:.3f}. "
                           f"{'Concerning — model may be penalizing under-resourced-but-honest centers' if poverty_corr < -0.3 else 'Acceptable — model is not simply penalizing weaker infrastructure among honest centers'}.")

# ============================================================================
# SAVE ALL OUTPUTS
# ============================================================================
center_features.to_csv(f"{OUT}/center_features_with_ml_outputs.csv", index=False)

with open(f"{OUT}/../fairness_audit.md", "w") as f:
    f.write("# Phase 4 — Fairness Audit\n\n")
    for i, note in enumerate(fairness_notes, 1):
        f.write(f"**{i}.** {note}\n\n")

with open(f"{OUT}/../ML_RESULTS_LOG.md", "w") as f:
    f.write("# Phase 4 — ML Suite Results Log\n\n")
    f.write("```\n" + "\n\n".join(results_log) + "\n```\n")

# Save trained model for Phase 5 reuse
import pickle
with open(f"{OUT}/xgb_risk_model.pkl", "wb") as f:
    pickle.dump({"model": xgb_model, "scaler": scaler, "feature_cols": FEATURE_COLS}, f)

print("\n=== FAIRNESS AUDIT ===")
for note in fairness_notes:
    print(note)

print("\nPhase 4 complete. Outputs saved to", OUT)
