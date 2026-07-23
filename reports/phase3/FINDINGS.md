# Phase 3 — EDA & Statistics — Findings

Run against the live PostgreSQL warehouse (`examshield` schema).

**1.** National score distribution: mean=267.1, median=262.4, std=69.7. Distribution is visibly bimodal — a tight high cluster (anomalous centers) sits on top of the expected broad normal-ish spread (normal centers).

**2.** State-wise average scores range from 259.2 to 294.1 — the spread is driven almost entirely by how many anomalous centers happen to sit in each state, not genuine regional ability.

**3.** Z-SCORE (|z|>2) on center avg score: flagged 10 centers, precision=1.00, recall=1.00 against known injected anomalies.

**4.** IQR (1.5x) on center avg score: flagged 11 centers, precision=0.91, recall=1.00 against known injected anomalies.

**5.** CHI-SQUARE (complaint category vs state): chi2=44.39, p=0.8213, dof=54. No significant association — complaint types are NOT simply a function of geography, a healthy sign for fairness.

**6.** CHI-SQUARE (anomalous center status vs state): chi2=19.63, p=0.0203. States show significant variation in anomaly concentration — flag for Phase 4 fairness audit.

**7.** ANOVA (total score across CCTV tiers low/medium/high): F=444.60, p=2.279e-189. Significant difference in scores across CCTV tiers — note this is confounded by anomalous centers (which have deliberately weaker infrastructure but inflated scores), exactly the kind of confound the Phase 4 fairness audit needs to disentangle.

**8.** Correlation (CCTV count vs complaint count): r=-0.34. Correlation (perimeter security vs complaint count): r=-0.24.

**9.** Confidence interval analysis: 0 centers have fewer than 50 present candidates, giving wide 95% CIs (avg width=nan) — these centers should NOT be flagged purely on pass-rate deviation without accounting for this uncertainty.

