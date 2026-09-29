# Model Card: [Model name] v[x.y]

**Owner:** [team / person] · **Risk tier:** Low / Medium / High · **Status:** Dev / Shadow / Production / Retired
**Registry ID:** [link] · **Code commit:** [sha] · **Last validated:** [date] · **Next review:** [date]

## 1. Intended use
- **Decision supported:** [what action uses the score, by whom]
- **Population:** [who gets scored]
- **Out-of-scope uses:** [where this must NOT be used, e.g., "not for credit decisions", "not for customers < 30 days tenure"]

## 2. Model
- **Type:** [e.g., LightGBM binary classifier, calibrated with isotonic]
- **Output:** [probability of X within Y days; score range; threshold(s) in use]
- **Scoring:** [batch daily / real-time; latency p99]
- **Fallback:** [behavior when model unavailable or inputs invalid]

## 3. Training data
- **Sources & window:** [tables, date range, snapshot date]
- **Label definition:** [exact logic, window]
- **Exclusions:** [rows removed and why, with counts]
- **Size / prevalence:** [n rows, positive rate]
- **Sensitive data handling:** [PII minimized/pseudonymized; protected attributes used for testing only / not used]

## 4. Features
| Feature group | Examples | Source | Point-in-time rule |
|---|---|---|---|

## 5. Evaluation
- **Validation scheme:** [temporal split, gap, holdout period]
- **Results (holdout):**

| Metric | Baseline (rule / naive) | Model | 95% CI |
|---|---|---|---|

- **Calibration:** [Brier, ECE, reliability summary]
- **Operating point:** [threshold, precision/recall at it, expected volume]
- **Stability over time:** [metric by month/fold]

## 6. Slices & fairness
| Slice | n | Metric | vs. overall | Notes |
|---|---|---|---|---|

- **Fairness metric chosen & rationale:** [...]
- **Findings & mitigations:** [...]

## 7. Explainability
- **Top drivers (global):** [...]
- **Per-decision explanations available?** [yes/no; method]

## 8. Limitations & known risks
- [e.g., "Under-performs for accounts < 90 days tenure (AUC 0.61)"]
- [feedback loop risks, dependency on upstream tables, etc.]

## 9. Monitoring
| Layer | Metric | Threshold | Frequency | Alert owner |
|---|---|---|---|---|
| Data quality | | | | |
| Input drift | PSI per top-10 feature | > 0.2 | weekly | |
| Prediction drift | | | | |
| Performance | | | on label maturity | |

- **Holdout / control group:** [size, purpose]

## 10. Retraining & rollback
- **Trigger:** [schedule / alert]
- **Promotion gate:** [challenger must beat champion on …]
- **Rollback:** [procedure, tested on date]

## 11. Approvals
| Role | Name | Date |
|---|---|---|
| Model owner | | |
| Independent validator (if tier ≥ Medium) | | |
| Business owner | | |
| Compliance / legal (if applicable) | | |

## Change log
| Version | Date | Change |
|---|---|---|
