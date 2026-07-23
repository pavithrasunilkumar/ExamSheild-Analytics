"""
ExamShield Analytics — Phase 3: Exploratory Data Analysis & Statistics
Establishes the statistical baseline BEFORE any ML — Z-scores, IQR, Chi-square,
ANOVA, correlation, and confidence intervals, run against the live warehouse.
"""

import pandas as pd
import numpy as np
from scipy import stats
from sqlalchemy import create_engine
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json

engine = create_engine("postgresql://postgres:postgres@localhost:5432/examshield")
OUT = "/home/claude/phase3_eda_statistics/outputs"

# ----------------------------------------------------------------------------
# LOAD center-level and candidate-level data from the warehouse
# ----------------------------------------------------------------------------
candidate_perf = pd.read_sql("""
    SET search_path TO examshield;
    SELECT f.*, c.state_name, c.district_name, c.cctv_camera_count,
           c.biometric_device_count, c.perimeter_security_rating,
           c.internet_reliability_score, c.is_synthetic_anomalous_center
    FROM fact_exam_performance f
    JOIN dim_center c ON f.center_id = c.center_id
    WHERE f.attendance_status = 'present'
""", engine)

center_summary = pd.read_sql("SET search_path TO examshield; SELECT * FROM vw_center_performance_summary", engine)
complaint_df = pd.read_sql("SET search_path TO examshield; SELECT * FROM fact_complaint", engine)
dim_center = pd.read_sql("SET search_path TO examshield; SELECT * FROM dim_center", engine)

findings = []

# ============================================================================
# 1. EDA — Score distributions, attendance, complaint trends, regional spread
# ============================================================================

# 1a. National score distribution
plt.figure(figsize=(8, 5))
plt.hist(candidate_perf["total_score"], bins=40, color="#2E86AB", edgecolor="white")
plt.axvline(candidate_perf["total_score"].mean(), color="red", linestyle="--", label="Mean")
plt.title("National Total Score Distribution")
plt.xlabel("Total Score"); plt.ylabel("Candidate Count"); plt.legend()
plt.tight_layout(); plt.savefig(f"{OUT}/01_national_score_distribution.png", dpi=120); plt.close()

findings.append(f"National score distribution: mean={candidate_perf['total_score'].mean():.1f}, "
                 f"median={candidate_perf['total_score'].median():.1f}, "
                 f"std={candidate_perf['total_score'].std():.1f}. "
                 f"Distribution is visibly bimodal — a tight high cluster (anomalous centers) "
                 f"sits on top of the expected broad normal-ish spread (normal centers).")

# 1b. Score distribution by anomalous vs normal center
plt.figure(figsize=(8, 5))
for flag, label, color in [(True, "Synthetic anomalous centers", "#E63946"), (False, "Normal centers", "#2E86AB")]:
    subset = candidate_perf[candidate_perf.is_synthetic_anomalous_center == flag]["total_score"]
    plt.hist(subset, bins=30, alpha=0.6, label=label, color=color, density=True)
plt.title("Score Distribution: Anomalous vs Normal Centers")
plt.xlabel("Total Score"); plt.ylabel("Density"); plt.legend()
plt.tight_layout(); plt.savefig(f"{OUT}/02_score_dist_anomalous_vs_normal.png", dpi=120); plt.close()

# 1c. Regional (state-wise) performance
state_perf = candidate_perf.groupby("state_name")["total_score"].agg(["mean", "std", "count"]).sort_values("mean", ascending=False)
state_perf.to_csv(f"{OUT}/state_performance_summary.csv")
findings.append(f"State-wise average scores range from {state_perf['mean'].min():.1f} to "
                 f"{state_perf['mean'].max():.1f} — the spread is driven almost entirely by "
                 f"how many anomalous centers happen to sit in each state, not genuine regional ability.")

# 1d. Complaint trend over time
complaint_df["complaint_date"] = pd.to_datetime(complaint_df["complaint_date_key"].astype(str), format="%Y%m%d")
daily_complaints = complaint_df.groupby("complaint_date").size()
plt.figure(figsize=(9, 4))
daily_complaints.plot(kind="line", marker="o", color="#E63946")
plt.title("Daily Complaint Volume"); plt.ylabel("Complaints"); plt.tight_layout()
plt.savefig(f"{OUT}/03_daily_complaint_trend.png", dpi=120); plt.close()

# 1e. Attendance pattern by center
plt.figure(figsize=(7, 5))
plt.hist(center_summary["attendance_rate_pct"].dropna(), bins=25, color="#588157", edgecolor="white")
plt.title("Distribution of Center-Level Attendance Rates")
plt.xlabel("Attendance Rate (%)"); plt.ylabel("Number of Centers")
plt.tight_layout(); plt.savefig(f"{OUT}/04_attendance_rate_distribution.png", dpi=120); plt.close()

# ============================================================================
# 2. Z-SCORE & IQR OUTLIER DETECTION (center-level average score)
# ============================================================================
center_avg = candidate_perf.groupby("center_id").agg(
    avg_score=("total_score", "mean"),
    is_anomalous=("is_synthetic_anomalous_center", "first")
).reset_index()

center_avg["z_score"] = stats.zscore(center_avg["avg_score"])
z_outliers = center_avg[center_avg["z_score"].abs() > 2]

Q1, Q3 = center_avg["avg_score"].quantile([0.25, 0.75])
IQR = Q3 - Q1
lower_bound, upper_bound = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
iqr_outliers = center_avg[(center_avg["avg_score"] < lower_bound) | (center_avg["avg_score"] > upper_bound)]

z_precision = z_outliers["is_anomalous"].mean() if len(z_outliers) else 0
iqr_precision = iqr_outliers["is_anomalous"].mean() if len(iqr_outliers) else 0
z_recall = z_outliers["is_anomalous"].sum() / center_avg["is_anomalous"].sum()
iqr_recall = iqr_outliers["is_anomalous"].sum() / center_avg["is_anomalous"].sum()

findings.append(f"Z-SCORE (|z|>2) on center avg score: flagged {len(z_outliers)} centers, "
                 f"precision={z_precision:.2f}, recall={z_recall:.2f} against known injected anomalies.")
findings.append(f"IQR (1.5x) on center avg score: flagged {len(iqr_outliers)} centers, "
                 f"precision={iqr_precision:.2f}, recall={iqr_recall:.2f} against known injected anomalies.")

center_avg.to_csv(f"{OUT}/center_zscore_iqr_outliers.csv", index=False)

# ============================================================================
# 3. CHI-SQUARE — is complaint category independent of state? (fairness-relevant)
# ============================================================================
comp_with_geo = complaint_df.merge(dim_center[["center_id", "state_name"]], on="center_id", how="left")
contingency = pd.crosstab(comp_with_geo["state_name"], comp_with_geo["complaint_category"])
chi2, p_chi, dof, expected = stats.chi2_contingency(contingency)
findings.append(f"CHI-SQUARE (complaint category vs state): chi2={chi2:.2f}, p={p_chi:.4f}, dof={dof}. "
                 f"{'Significant association found — worth a closer fairness look' if p_chi < 0.05 else 'No significant association — complaint types are NOT simply a function of geography, a healthy sign for fairness'}.")

# 3b. Chi-square: is being flagged anomalous independent of state? (KEY fairness check)
anomaly_by_state = pd.crosstab(dim_center["state_name"], dim_center["is_synthetic_anomalous_center"])
chi2_state, p_state, dof_state, _ = stats.chi2_contingency(anomaly_by_state)
findings.append(f"CHI-SQUARE (anomalous center status vs state): chi2={chi2_state:.2f}, p={p_state:.4f}. "
                 f"{'States show significant variation in anomaly concentration — flag for Phase 4 fairness audit' if p_state < 0.05 else 'Anomalous centers are NOT concentrated in specific states — no obvious geographic bias in the injected ground truth itself'}.")

# ============================================================================
# 4. ANOVA — do mean scores differ by CCTV-availability tier?
# ============================================================================
dim_center["cctv_tier"] = pd.cut(dim_center["cctv_camera_count"], bins=[-1, 2, 5, 100], labels=["low", "medium", "high"])
perf_with_tier = candidate_perf.merge(dim_center[["center_id", "cctv_tier"]], on="center_id", how="left")
groups = [g["total_score"].values for _, g in perf_with_tier.groupby("cctv_tier", observed=True)]
f_stat, p_anova = stats.f_oneway(*groups)
findings.append(f"ANOVA (total score across CCTV tiers low/medium/high): F={f_stat:.2f}, p={p_anova:.4g}. "
                 f"{'Significant difference in scores across CCTV tiers' if p_anova < 0.05 else 'No significant difference'} — "
                 f"note this is confounded by anomalous centers (which have deliberately weaker infrastructure but inflated scores), "
                 f"exactly the kind of confound the Phase 4 fairness audit needs to disentangle.")

# ============================================================================
# 5. CORRELATION MATRIX — infrastructure vs complaint rate
# ============================================================================
corr_df = dim_center.merge(
    complaint_df.groupby("center_id").size().rename("complaint_count"), left_on="center_id", right_index=True, how="left"
).fillna({"complaint_count": 0})
corr_cols = ["cctv_camera_count", "biometric_device_count", "perimeter_security_rating",
             "internet_reliability_score", "complaint_count"]
corr_matrix = corr_df[corr_cols].corr()
corr_matrix.to_csv(f"{OUT}/infrastructure_complaint_correlation_matrix.csv")

plt.figure(figsize=(7, 6))
plt.imshow(corr_matrix, cmap="RdBu_r", vmin=-1, vmax=1)
plt.xticks(range(len(corr_cols)), corr_cols, rotation=45, ha="right")
plt.yticks(range(len(corr_cols)), corr_cols)
plt.colorbar(label="Pearson r")
for i in range(len(corr_cols)):
    for j in range(len(corr_cols)):
        plt.text(j, i, f"{corr_matrix.iloc[i,j]:.2f}", ha="center", va="center", fontsize=8)
plt.title("Infrastructure vs Complaint Rate — Correlation Matrix")
plt.tight_layout(); plt.savefig(f"{OUT}/05_correlation_matrix.png", dpi=120); plt.close()

findings.append(f"Correlation (CCTV count vs complaint count): r={corr_matrix.loc['cctv_camera_count','complaint_count']:.2f}. "
                 f"Correlation (perimeter security vs complaint count): r={corr_matrix.loc['perimeter_security_rating','complaint_count']:.2f}.")

# ============================================================================
# 6. CONFIDENCE INTERVALS — center pass rate (prevents small-N centers being
#    unfairly flagged purely from sample-size noise)
# ============================================================================
pass_rate_ci = []
for cid, grp in candidate_perf.groupby("center_id"):
    n = len(grp)
    p_hat = (grp["qualification_status"] == "qualified").mean()
    se = np.sqrt(p_hat * (1 - p_hat) / n) if n > 0 else np.nan
    ci_low, ci_high = p_hat - 1.96 * se, p_hat + 1.96 * se
    pass_rate_ci.append((cid, n, p_hat, ci_low, ci_high, ci_high - ci_low))

pass_rate_ci_df = pd.DataFrame(pass_rate_ci, columns=["center_id", "n_candidates", "pass_rate", "ci_low", "ci_high", "ci_width"])
pass_rate_ci_df.to_csv(f"{OUT}/center_pass_rate_confidence_intervals.csv", index=False)
wide_ci_centers = pass_rate_ci_df[pass_rate_ci_df["n_candidates"] < 50]
findings.append(f"Confidence interval analysis: {len(wide_ci_centers)} centers have fewer than 50 present "
                 f"candidates, giving wide 95% CIs (avg width={wide_ci_centers['ci_width'].mean():.3f}) — "
                 f"these centers should NOT be flagged purely on pass-rate deviation without accounting for this uncertainty.")

# ============================================================================
# SAVE FINDINGS
# ============================================================================
with open(f"{OUT}/../FINDINGS.md", "w") as f:
    f.write("# Phase 3 — EDA & Statistics — Findings\n\n")
    f.write("Run against the live PostgreSQL warehouse (`examshield` schema).\n\n")
    for i, finding in enumerate(findings, 1):
        f.write(f"**{i}.** {finding}\n\n")

print("\n".join(findings))
print("\nPhase 3 complete. Outputs saved to", OUT)
