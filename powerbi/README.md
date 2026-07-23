# Power BI Dashboards — In Progress

This folder is intentionally empty for now.

The Power BI dashboards (Executive, Center Analytics, Candidate Analytics, and
Risk Dashboard) are being built manually, learning Power BI Desktop from
scratch, connected live to the PostgreSQL warehouse and the
`fact_final_risk_score` table produced in Phase 5.

**Data sources ready for connection:**
- `vw_center_performance_summary` (view)
- `vw_high_risk_centers` (view)
- `fact_final_risk_score` (table)
- `fact_exam_performance`, `dim_center`, `dim_candidate`, `dim_session` (star schema)

Once complete, this folder will contain:
- `ExamShield_Dashboards.pbix`
- Dashboard screenshots (PNG) for the README
