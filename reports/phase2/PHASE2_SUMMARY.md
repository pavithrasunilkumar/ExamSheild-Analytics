# Phase 2 — PostgreSQL Data Warehouse & ETL — Summary

## What was built

### 1. Star Schema (`sql/schema.sql`)
- **Fact table:** `fact_exam_performance` (grain: 1 row per allocated candidate) — scores, attendance, biometric match, qualification status
- **Event-grain facts:** `fact_complaint`, `fact_incident`, `fact_audit`, `fact_audit_finding`, `fact_investigation`, `fact_social_media_signal`, `fact_invigilator_assignment`
- **Dimensions:** `dim_candidate`, `dim_center` (denormalized with infrastructure — legitimate 1:1), `dim_session`, `dim_date`, `dim_invigilator`, `dim_candidate_category`, `dim_pwbd_status`, `dim_question_paper_set`
- **Indexes** on all FK join columns plus a composite `(center_id, total_score)` index for the ranking queries that drive the dashboards

### 2. ETL Pipeline (`python/etl.py`)
- Extracts all 22 relevant CSVs from the v1 synthetic dataset
- **Validates before loading:** required-column checks, null checks, primary-key duplication checks, and a referential-integrity spot-check (every candidate's center assignment resolves to a real center)
- Transforms into star-schema shape (builds `dim_date` from every date column across the dataset; denormalizes center + infrastructure; joins allocation → attendance → biometric → score → result into one performance fact row)
- Loads in FK-safe order (dimensions before facts) via SQLAlchemy

**Result:** 20,000 candidates / 19,570 allocations / 18,734 scored performances loaded with zero validation failures.

### 3. Advanced SQL Analytics (`sql/analytics.sql`)
- **Window functions:** `RANK()` and `PERCENT_RANK()` for national and state-partitioned center ranking, complaint-rate percentiles
- **CTEs:** the full 6-component Integrity Risk Index (score anomaly, complaint frequency, attendance anomaly, capacity, infrastructure, historical integrity) computed as chained, readable CTEs rather than one unreadable nested query
- **Views:** `vw_high_risk_centers`, `vw_center_performance_summary`
- **Stored procedure:** `generate_monthly_integrity_report()` — re-runnable, writes a timestamped, versioned snapshot into `fact_risk_score_history`

## Validation — the model recovers the injected ground truth

Running the composite risk query against real SQL (not just Python) confirms the pipeline works end-to-end:

| Rank | Center | Anomalous (ground truth)? | Composite Risk Score |
|---|---|---|---|
| 1–10 | (all 10 injected centers) | ✅ true | 81.8 – 87.2 |
| 11+ | (first normal center) | false | 53.2 |

**All 10 synthetically anomalous centers rank #1–10 out of 200 by composite risk score, with a clean 28-point gap to the next center.** This is the exact validation story to use in interviews: "I didn't just build a scoring formula — I proved in SQL that it recovers known-injected anomalies with perfect separation before ever touching ML."

## Known items for later phases
- The capacity/infrastructure sub-scores currently use simple proxies (internet reliability, device counts) — Phase 4's fairness audit should test whether these proxies correlate with state/category in ways that need correcting.
- `fact_risk_score_history` currently holds one snapshot; re-running the procedure across multiple exam cycles (once v2 multi-cycle data exists) will make the "moving average of risk over time" queries meaningful.
