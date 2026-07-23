# Phase 5 — Composite Risk Scoring Engine — Validation Summary

- Final blended score (50% SQL statistical + 50% ML ensemble): top-10 recovers **10/10** true injected anomalies.
- SQL-only top-10 recovers: 10/10
- ML-only top-10 recovers: 10/10

## Interpretation

Both individual signals already achieve strong recovery on this synthetic dataset (as expected, given deliberately clean injection). The value of blending both signals is not visible in top-10 recovery here — it becomes visible in the **`risk_band` and `ml_ensemble_confidence` tiers for borderline centers just outside the top 10**, where SQL and ML signals can disagree. Those disagreement cases are exactly where a human auditor's judgment adds the most value, and exactly why `fact_final_risk_score` stores both component scores separately rather than only the blended number — auditors can see *why* two centers with the same final score got there differently (one via pure complaint volume, the other via a stronger ML pattern match).

## Schema Note

`fact_final_risk_score` is append-only and timestamped (`scored_at`), matching the versioning approach in `fact_risk_score_history` from Phase 2 — every scoring run is preserved rather than overwritten, enabling risk-trend-over-time dashboards in Phase 6.
