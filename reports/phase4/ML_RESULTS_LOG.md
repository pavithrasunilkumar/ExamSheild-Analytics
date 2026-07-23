# Phase 4 — ML Suite Results Log

```
Isolation Forest: precision=1.00, recall=1.00, F1=1.00, flagged=10

Local Outlier Factor: precision=1.00, recall=1.00, F1=1.00, flagged=10

DBSCAN: precision=0.77, recall=1.00, F1=0.87, flagged=13

Ensemble (>=2 of 3 methods agree): precision=1.00, recall=1.00, F1=1.00, flagged=10

XGBoost risk model (test set): AUC=1.000
              precision    recall  f1-score   support

           0       1.00      1.00      1.00        57
           1       1.00      1.00      1.00         3

    accuracy                           1.00        60
   macro avg       1.00      1.00      1.00        60
weighted avg       1.00      1.00      1.00        60


LIMITATION NOTE: AUC of 1.000 reflects that this synthetic dataset's anomalous centers are deliberately, cleanly separable by design (Phase 1 injection) — this is a validation exercise, not evidence of real-world model performance. On real data with noisier, weaker, and more ambiguous signals, expect substantially lower separability, which is exactly why the semi-supervised proxy-label approach (rather than a claim of solved fraud detection) is the honest framing here.

Prophet forecast: 61 days of history used, forecasted 30 days forward. Next-30-day predicted avg daily complaints: 4.3
```
