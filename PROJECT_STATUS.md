# Project Status

| Phase | Status |
|---|---|
| 0 — Environment & Repo Setup | ✅ Done |
| 1 — Data Design & Synthetic Dataset Generation | ✅ Done |
| 2 — SQL Data Warehouse & ETL | ✅ Done |
| 3 — Exploratory Data Analysis & Statistics | ✅ Done |
| 4 — Machine Learning Suite | ✅ Done |
| 5 — Composite Risk Scoring Engine | ✅ Done |
| 6 — Power BI Dashboards | 🚧 In progress — being built manually in Power BI Desktop |
| 7 — SAP ERP Master Data Layer | ⏭️ Deferred until Phase 6 is complete |
| 8 — Reporting, Documentation, Polish | ⏭️ Not started |

## How to reproduce this repo end-to-end

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate the synthetic dataset (Phase 1)
python python/phase1_data_generation/generate_data.py

# 3. Create the PostgreSQL schema (Phase 2)
createdb examshield
psql -d examshield -f sql/schema.sql
psql -d examshield -c "ALTER DATABASE examshield SET search_path TO examshield, public;"

# 4. Load the data (Phase 2)
python python/phase2_etl/etl.py

# 5. Build the SQL analytics layer — views, window functions, stored procedure (Phase 2)
psql -d examshield -f sql/analytics.sql

# 6. Run the EDA & statistics suite (Phase 3)
python python/phase3_eda_statistics/eda_statistics.py

# 7. Run the ML suite — anomaly detection, risk model, SHAP, fairness audit (Phase 4)
python python/phase4_ml_models/ml_pipeline.py

# 8. Run the final risk engine integration (Phase 5)
python python/phase5_risk_engine/integrate_risk_engine.py
```

Every script above was run end-to-end against a real PostgreSQL 16 instance
during development — this isn't untested code. See `reports/` for the
validation results from each phase.

## Key validated result

The composite risk score (blending SQL statistical analysis with the ML
ensemble) correctly identifies all 10 deliberately injected anomalous centers
in the top 10 of 200 by risk score, with zero false positives — see
`reports/phase5/PHASE5_VALIDATION_SUMMARY.md` for the full validation writeup,
and `reports/phase4/fairness_audit.md` for the honest fairness findings
(including one unresolved issue flagged for future mitigation).
