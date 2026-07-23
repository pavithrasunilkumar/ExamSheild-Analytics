# Phase 4 — Fairness Audit

**1.** Max |correlation| between predicted risk probability and any single state dummy: 0.232 (state_Rajasthan). No single state dominates the risk signal — reasonable fairness result.

**2.** Chi-square (ensemble anomaly flag vs state): chi2=19.63, p=0.0203. Statistically significant geographic concentration in flags — requires mitigation before deployment.

**3.** Among NORMAL (non-anomalous) centers only: the XGBoost model assigns near-zero risk probability to virtually all of them (std < 1e-6), so a correlation with infrastructure quality is undefined (no variance to correlate against). This itself is informative: the model isn't spreading risk scores around within the normal population based on infrastructure quality — it draws a hard line at the injected anomaly boundary. In a real deployment with noisier, non-synthetic labels this separation would not be this clean, and this check should be re-run on real data before trusting it.

