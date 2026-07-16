<div align="center">

# 🛡️ ExamShield Analytics
### AI-Powered Examination Risk & Integrity Intelligence System

*Turning raw examination data into proactive, explainable audit intelligence.*

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Power BI](https://img.shields.io/badge/Power%20BI-Dashboards-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)](https://powerbi.microsoft.com/)
[![SAP](https://img.shields.io/badge/SAP-Master%20Data%20Modeled-0FAAFF?style=for-the-badge&logo=sap&logoColor=white)](https://www.sap.com/)
[![scikit--learn](https://img.shields.io/badge/scikit--learn-ML-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![XGBoost](https://img.shields.io/badge/XGBoost-Risk%20Model-EB6C1F?style=for-the-badge)](https://xgboost.readthedocs.io/)
[![SHAP](https://img.shields.io/badge/SHAP-Explainable%20AI-8A2BE2?style=for-the-badge)](https://shap.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active%20Development-yellow?style=for-the-badge)]()

[Overview](#-overview) • [Problem](#-the-problem) • [Architecture](#-architecture) • [Tech Stack](#-tech-stack) • [Features](#-key-features) • [Screenshots](#-dashboards) • [FAQ](#-frequently-asked-questions) • [Setup](#-getting-started)

</div>

---

## 📌 Overview

**ExamShield Analytics** is an end-to-end data analytics platform that helps examination authorities move from **reactive investigation** (acting only after complaints or media reports) to **proactive, evidence-based risk monitoring** of examination centers, candidates, and operations.

It combines **SQL analytics, statistical hypothesis testing, machine learning, explainable AI, and enterprise-style master data governance** into a single decision-support system — culminating in a composite **Integrity Risk Index** and executive/audit dashboards built in Power BI.

> **Important framing:** This system does **not** accuse individuals of misconduct. It is a **triage tool** — the same way fraud-detection systems flag transactions for review rather than declaring guilt. It tells auditors *where to look first*, using transparent, explainable scoring.

---

## 🎯 The Problem

Large-scale examinations (NEET, JEE, SSC, State PSCs, banking recruitment, university entrance exams) involve **millions of candidates** and **thousands of centers**. At this scale:

- Manual monitoring cannot catch suspicious score distributions, abnormal attendance, or unusual response behavior.
- Investigations are typically triggered only **after** a complaint or media report — by which point damage (re-exams, legal challenges, lost public trust) is already done.
- Re-conducting a large-scale exam costs crores of rupees and months of delay — dramatically more expensive than proactive, targeted audits.

**ExamShield Analytics solves this by continuously screening every center statistically and via ML, so authorities can prioritize the ~2–5% that warrant a closer look — instead of guessing or waiting for a complaint.**

---

## 🌍 Why This Matters Right Now

This isn't a hypothetical problem invented for a portfolio project — it's actively unfolding.

- **NEET-UG 2026 (India):** The national medical entrance exam, taken by over 2.2 million aspirants on May 3, 2026, was cancelled just nine days later after investigators found a leaked "guess paper" overlapped with the actual question paper. A multi-state investigation (Rajasthan, Maharashtra, and beyond) led to dozens of arrests, a CBI takeover of the case, Supreme Court petitions, and nationwide protests — with tragic real-world consequences reported in the aftermath, including student suicides linked to the exam's cancellation. The Education Ministry has since announced plans to move NEET to a computer-based format from 2027, citing a breakdown in its "command chain."
- **NEET-UG 2024 (India):** The same exam drew scrutiny after more than 80 candidates scored a perfect 720/720 — a number educators called statistically implausible, since only seven students had ever achieved a perfect score in the exam's history before that year. Investigations led to arrests and cancelled results, but the exam itself wasn't scrapped, and similar concerns resurfaced two years later in 2026.

**What both incidents have in common is exactly the gap ExamShield Analytics is built to close:** in both cases, the irregularity was only caught *after* the exam had already been conducted — through a whistleblower tip-off and post-hoc statistical suspicion (an implausible spike in perfect scores), not through continuous, systematic monitoring. A center-level and candidate-level statistical/ML screening layer — of the kind this project builds — is exactly the sort of proactive check that could have flagged the 2024 score anomaly *before* it became a national controversy, and could plausibly have surfaced the 2026 leak's downstream effects (unusual score clustering, timing anomalies) faster than a chemistry teacher independently comparing papers by hand.

*(Sources: [NEET 2026 Paper Leak — Wikipedia](https://en.wikipedia.org/wiki/NEET_2026_Paper_leak), [Al Jazeera, May 2026](https://www.aljazeera.com/news/2026/5/26/come-back-my-son-indian-exam-leak-leaves-trail-of-death-despair-anger))*

---

## 🏗️ Architecture

```
SAP ERP (Master Data)              Other Raw Sources
Center / Invigilator /             Candidate Registration,
Asset Master, Complaints    ──┐    Attendance, Sessions,
                               │    Response Logs, Results
                               ▼
                    PostgreSQL Data Warehouse (star schema)
                               │
                    Python ETL — clean, validate, merge
                               │
                    Exploratory Data Analysis
                               │
                    Statistical Testing (Z-score, IQR, Chi-square, ANOVA)
                               │
                    Machine Learning
                    (Isolation Forest · LOF · DBSCAN · XGBoost · Prophet · K-Means)
                               │
                    SHAP Explainability + Fairness Audit
                               │
                    Composite Integrity Risk Scoring Engine
                               │
                    Power BI Dashboards (Executive / Center / Candidate / Risk)
                               │
                    Auto-Generated Audit Priority Report
```

---

## 🧰 Tech Stack

| Layer | Tools | Purpose |
|---|---|---|
| **Master Data** | SAP ERP (modeled) | Source-of-truth for Centers, Invigilators, Infrastructure assets, Complaint notifications |
| **Data Warehouse** | PostgreSQL | Star-schema warehouse; window functions, CTEs, views, stored procedures, indexing |
| **ETL & Analytics** | Python (Pandas, NumPy, SciPy) | Extraction, cleaning, validation, statistical testing |
| **Machine Learning** | Scikit-learn, XGBoost, Prophet | Anomaly detection, risk prediction, forecasting, segmentation |
| **Explainability** | SHAP | Transparent, per-center reasoning for every risk flag |
| **Visualization** | Power BI, Plotly | Executive, operational, and risk dashboards |
| **Version Control** | Git / GitHub | Reproducibility and project history |

---

## ✨ Key Features

-  **Multi-layer anomaly detection** — Isolation Forest (global outliers), Local Outlier Factor (peer-relative outliers), DBSCAN (coordinated candidate clusters)
-  **Advanced SQL analytics** — center/state ranking via window functions, multi-step risk CTEs, reusable views, stored procedures for monthly reports
-  **Rigorous statistics** — Z-score & IQR outlier detection, Chi-square independence tests, ANOVA, confidence intervals (so small centers aren't unfairly flagged from sample-size noise)
-  **Composite Integrity Risk Index** — documented, weighted, auditable scoring formula (score anomaly, complaint frequency, attendance anomaly, capacity, infrastructure, historical integrity)
-  **Explainable AI** — every flagged center comes with a SHAP-based "top 3 contributing factors" explanation
-  **Fairness audit** — explicit statistical check that risk scores aren't proxying for state, category, or school type
-  **Enterprise-style master data modeling** — Center/Invigilator/Asset data structured the way a real SAP-based government IT estate would store it
-  **Forecasting** — Prophet/ARIMA models for future complaint load, supporting staffing and audit-calendar planning
-  **Center segmentation** — K-Means/Hierarchical clustering into interpretable operational profiles
-  **Auto-generated audit report** — ranked list of high-priority centers with reasons and recommended actions

---

## 📊 Dashboards

| Dashboard | Audience | Contents |
|---|---|---|
| **Executive** | Leadership | Total candidates, attendance rate, complaint rate, high-risk center count, integrity index |
| **Center Analytics** | Operations | Center ranking, capacity utilization, complaint heatmap, attendance trends |
| **Candidate Analytics** | Analysts | Demographics, regional performance, score distributions |
| **Risk Dashboard** | Auditors | Risk heatmap, high-risk center list with SHAP tooltips, investigation queue, risk trend |

*(Screenshots to be added as dashboards are built — see `/powerbi` folder.)*

---

## ❓ Frequently Asked Questions

<details>
<summary><strong>What exactly does this system do?</strong></summary>

It ingests examination operational data (attendance, scores, complaints, center infrastructure), runs statistical and ML-based anomaly detection, and produces a composite, explainable **Integrity Risk Index** per center — surfaced through Power BI dashboards to help authorities prioritize audits.
</details>

<details>
<summary><strong>Is this accusing centers or candidates of cheating?</strong></summary>

No. It is a **risk-prioritization/triage system**, not a verdict engine. A high score means "this center statistically deserves a closer look," not "this center cheated." This distinction is core to the system's design and is enforced by requiring an explainable reason (via SHAP) behind every flag.
</details>

<details>
<summary><strong>How do you validate the model without real fraud labels?</strong></summary>

Ground-truth fraud labels don't exist in public data (rightly so). The synthetic dataset has **deliberately injected anomalies** (e.g., abnormally low response-time variance, suspicious answer-change patterns) used to validate that the detection models actually recover known ground truth. Where real historical complaint/investigation outcomes exist, they're used as weak, semi-supervised labels — with that limitation explicitly documented rather than hidden.
</details>

<details>
<summary><strong>Why three different anomaly detection algorithms (Isolation Forest, LOF, DBSCAN)?</strong></summary>

They catch different anomaly types:
- **Isolation Forest** → global structural outliers across all centers
- **Local Outlier Factor** → outliers relative to a center's local peer group (so a rural center isn't unfairly compared to a metro center)
- **DBSCAN** → density-based clustering, useful for detecting *groups* of coordinated anomalous candidates, not just single outliers
</details>

<details>
<summary><strong>How do you prevent the model from just flagging poor/rural centers?</strong></summary>

A dedicated **fairness audit** module checks for correlation between risk scores and demographic/regional variables (state, category, school type) after controlling for genuine operational features. Any suspicious correlation is documented and mitigated (e.g., feature reweighting or removal).
</details>

<details>
<summary><strong>Is the SAP ERP integration real?</strong></summary>

The master data (Center, Invigilator, Infrastructure Asset) is **modeled using SAP-style structures and conventions** (Plant/Personnel/Asset Master patterns), with extracts simulated the way a real SAP BAPI/RFC/CDS-view pull would look. This is documented transparently in `/sap_extracts/sap_integration_notes.md` — the project does not overstate a live SAP connection where one doesn't exist.
</details>

<details>
<summary><strong>Why SQL for the heavy lifting instead of doing everything in Python/Pandas?</strong></summary>

The warehouse uses a star schema so ranking, percentile, and trend queries (window functions, CTEs) run efficiently at scale via indexed SQL, and are reusable as **views** and **stored procedures** for repeatable monthly reporting — rather than re-running ad hoc Python scripts each cycle.
</details>

<details>
<summary><strong>What's the business impact?</strong></summary>

Re-conducting a single large-scale exam due to a discovered integrity failure costs crores of rupees and months of delay. A proactive, data-driven audit process is dramatically cheaper and more defensible than reactive investigation triggered by complaints or media pressure.
</details>

<details>
<summary><strong>How would this scale to real, national-level data (millions of candidates)?</strong></summary>

The Postgres schema is indexed on join keys (`center_id`, `candidate_id`, `session_id`); ETL is batch-scheduled; and the anomaly detection algorithms used (Isolation Forest in particular) scale near-linearly with data size. The architecture is designed to be horizontally extendable (e.g., partitioned tables) as volume grows.
</details>

<details>
<summary><strong>What would you improve with more time or real data?</strong></summary>

Access to verified historical investigation outcomes for proper supervised validation; a feedback loop where auditors confirm or reject flags to retrain the model over time; and a live SAP integration if institutional access were available.
</details>

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Power BI Desktop (Windows)
- Git

### Installation
```bash
git clone https://github.com/<your-username>/examshield-analytics.git
cd examshield-analytics

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Database Setup
```bash
createdb examshield
psql -d examshield -f sql/schema.sql
```

### Run the ETL Pipeline
```bash
python python/etl.py
```

### Open Dashboards
Open `powerbi/ExamShield_Dashboards.pbix` in Power BI Desktop and refresh the data source connection.

---

## 📁 Project Structure

```
examshield-analytics/
├── sql/                # DDL, views, stored procedures, window function queries
├── python/             # ETL scripts, ML models, statistical analysis
├── data/
│   ├── raw/            # Synthetic source data
│   └── processed/      # Cleaned, warehouse-ready data
├── sap_extracts/        # SAP-modeled master data + integration notes
├── powerbi/             # .pbix dashboard files
├── notebooks/           # EDA, statistics, and ML notebooks
├── reports/             # Auto-generated audit priority reports
├── requirements.txt
└── README.md
```

---

## 🗺️ Roadmap

- [x] Problem definition & architecture design
- [x] Synthetic dataset with injected anomalies
- [ ] SQL warehouse & ETL pipeline
- [ ] Statistical analysis module
- [ ] ML anomaly detection & risk scoring suite
- [ ] SHAP explainability integration
- [ ] Fairness audit module
- [ ] Power BI dashboard suite
- [ ] SAP-modeled master data layer
- [ ] Auto-generated audit report

---
##  Author

### Pavithra Sunilkumar

- LinkedIn: https://linkedin.com/in/pavithra-sunilkumar68
- GitHub: https://github.com/pavithrasunilkumar
- Portfolio: https://vermillion-panda-a08876.netlify.app/

---

## Support

If you found this project useful, consider giving it a ⭐ on GitHub.

---

## License

This project is for **educational and personal use only**.
Commercial usage is strictly prohibited.

---


<div align="center">

**Built to show that data analytics can make public examination systems more transparent, fair, and trustworthy.**

</div>
