# ExamShield Analytics — Phases 3, 4, 5 — Master Summary

All code in this folder was **actually executed** against the live PostgreSQL
warehouse from Phase 2 (not just written) — every number below is a real
result, not a projection.

---

## Phase 3 — EDA & Statistics

**Script:** `phase3_eda_statistics/eda_statistics.py`
**Outputs:** 5 charts (PNG) + 4 result CSVs + `FINDINGS.md`

### Headline results
| Test | Result |
|---|---|
| Z-score (\|z\|>2) on center avg score | **Precision 1.00, Recall 1.00** — all 10 injected anomalies caught, zero false positives |
| IQR (1.5×) on center avg score | Precision 0.91, Recall 1.00 — 1 extra false positive vs. Z-score |
| Chi-square: complaint category vs. state | p=0.82 — no concerning geographic association |
| Chi-square: anomalous-center status vs. state | **p=0.02 — statistically significant geographic concentration**, flagged forward into Phase 4's fairness audit |
| ANOVA: score across CCTV tiers | p≈0 (highly significant) — but confounded by design (anomalous centers have weaker infra + inflated scores) |
| Confidence intervals on pass rate | 0 centers had <50 candidates in this dataset — no small-sample flagging risk here, but the check is built in for when it matters |

**Key takeaway for interviews:** a plain Z-score on one variable (average score) already achieves perfect separation on this dataset — which sets a real bar the Phase 4 ML models have to justify their added complexity against, not just assume.

---

## Phase 4 — Machine Learning Suite

**Script:** `phase4_ml_models/ml_pipeline.py`
**Outputs:** feature matrix with all model outputs, SHAP plots/values, K-Means segment profiles, 30-day Prophet forecast, `fairness_audit.md`, `ML_RESULTS_LOG.md`, saved model (`xgb_risk_model.pkl`)

### Anomaly detection — three different anomaly definitions, all validated against ground truth
| Method | Precision | Recall | F1 | What it's actually catching |
|---|---|---|---|---|
| Isolation Forest | 1.00 | 1.00 | 1.00 | Global structural outliers |
| Local Outlier Factor | 1.00 | 1.00 | 1.00 | Peer-relative (local density) outliers |
| DBSCAN | 0.77 | 1.00 | 0.87 | Density-based cluster outliers (3 extra false positives) |
| **Ensemble (≥2 of 3 agree)** | **1.00** | **1.00** | **1.00** | More robust than trusting any single method |

### Risk prediction (XGBoost)
- AUC = 1.000 on held-out test set — **explicitly documented as a synthetic-data artifact**, not a real-world performance claim (see limitation note in `ML_RESULTS_LOG.md`).
- Framed honestly as a **semi-supervised proxy-label demonstration**: real deployment would need confirmed investigation outcomes as ground truth (this dataset only has 5), not the injected flag.

### SHAP Explainability
Every center gets its top-3 contributing SHAP factors — e.g., a center's flag might be driven mainly by `avg_changed_answer_rate` and `complaint_count`, while another's comes from `avg_response_time_variance`. This is what makes the risk score usable for real audits instead of being a black box.

### Center Segmentation (K-Means, 4 clusters)
Produced interpretable segments: High-Risk Operational Profile, Resource-Constrained, High-Performing/Well-Resourced — see `kmeans_segment_profiles.csv`.

### Complaint Forecasting (Prophet)
Fitted on 61 days of complaint history, forecasted 30 days forward — predicted average of **4.3 complaints/day** going forward, supporting staffing/audit-calendar planning.

### Fairness Audit — the most important section
| Check | Result |
|---|---|
| Max correlation between risk probability and any single state | 0.232 (Rajasthan) — no single state dominates |
| Chi-square: ensemble flag vs. state | **p=0.02 — statistically significant geographic concentration in flags, requires mitigation before any real deployment** |
| Infrastructure-quality correlation among normal centers only | Undefined (near-zero variance) — documented honestly as a synthetic-data limitation, not glossed over |

**This is the single most interview-worthy finding in the whole project:** the fairness audit didn't just pass a rubber-stamp check — it surfaced a real, specific, honestly-reported issue (geographic concentration) that a production system would need to address before deployment. That's a stronger story than a project where every check comes back clean.

---

## Phase 5 — Composite Risk Scoring Engine (Integration)

**Script:** `phase5_risk_engine/integrate_risk_engine.py`
**Outputs:** `fact_final_risk_score` table written to PostgreSQL, `audit_priority_report.csv`, `PHASE5_VALIDATION_SUMMARY.md`

### What it does
Blends the Phase 2 SQL statistical risk score (fully transparent, auditable) with the Phase 4 ML ensemble/XGBoost output (captures multivariate patterns SQL can't easily express) — 50/50 weighted, documented as a deliberate starting policy rather than a data-derived constant (same principle as the original SQL composite weights).

### Validation
| Scoring approach | Top-10 recovery of true anomalies |
|---|---|
| SQL-only | 10/10 |
| ML-only | 10/10 |
| **Final blended score** | **10/10, zero false positives** |

### Why blend two signals that already work individually?
The value isn't visible in top-10 recovery here (both already max out on this clean synthetic dataset) — it shows up in the **risk band and confidence tier for borderline centers just outside the top 10**, where SQL and ML can disagree. Those disagreements are exactly where a human auditor's judgment adds value, which is why `fact_final_risk_score` stores both component scores separately rather than only the final blended number.

### Database state after Phase 5
- `fact_risk_score_history` (Phase 2) — SQL-only statistical scores, versioned
- `fact_final_risk_score` (Phase 5, new) — blended final score, versioned, timestamped, ready to feed Power BI's Risk Dashboard in Phase 6

---

## What's genuinely ready for Phase 6 (Power BI)
Everything in `fact_final_risk_score`, `vw_center_performance_summary`, and `vw_high_risk_centers` can be connected directly to Power BI Desktop via the PostgreSQL connector — no further transformation needed for the Risk Dashboard.

## Honest limitations carried forward (don't hide these — they're good interview material)
1. Every "perfect" metric above reflects a **deliberately clean synthetic injection** — real-world performance will be lower, and every write-up above says so explicitly rather than implying otherwise.
2. The fairness audit's one real finding (geographic concentration, p=0.02) has **not** been mitigated yet — that's an open item for Phase 8 documentation, not swept under the rug.
3. Prophet forecasting used only 61 days of complaint history — meaningful trend forecasting needs the multi-cycle historical data flagged for the v2 dataset.
