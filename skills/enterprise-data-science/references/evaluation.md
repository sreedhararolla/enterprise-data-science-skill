# Model evaluation

## Contents
1. Choosing the metric
2. Thresholds from cost or capacity
3. Calibration
4. Uncertainty on model metrics
5. Slice analysis and fairness
6. Explainability
7. Translating to business value

---

## 1. Choosing the metric

Pick the metric that matches how the output will be **used**, not the one that is easiest
to report.

| Use of the output | Primary metric | Why |
|---|---|---|
| Rank a list and act on the top K (outreach, review queue) | Precision@K / recall@K, lift@K | The team acts on the top of the list only |
| Scores used as probabilities (pricing, expected value, risk) | Log loss, Brier score, and calibration | Ranking alone isn't enough when the probability values themselves matter |
| Rare positives (fraud, default, failures) | PR-AUC (average precision), recall at a fixed precision | ROC-AUC looks good even when precision is terrible |
| Balanced classes, ranking quality in general | ROC-AUC | Threshold-free and interpretable as P(score_pos > score_neg) |
| Hard yes/no with known error costs | Expected cost (or profit) at the chosen threshold | Directly maps to money |
| Regression with outliers that matter less | MAE / median AE | Robust; the units are interpretable |
| Regression where big misses are very costly | RMSE | Squares penalize big misses |
| Forecasting across items of different scales | WAPE, MASE | Scale-free and stable near zero |
| Quantile or interval forecasts | Pinball loss, interval coverage | Evaluates the whole distribution |

Avoid **accuracy** when classes are imbalanced (99% accuracy by predicting "no fraud"),
avoid **MAPE** when actuals are near zero, and avoid **R²** as the only regression metric
(it depends on the variance of the target, not the business tolerance).

Always report the primary metric **with the baseline alongside it**.

---

## 2. Thresholds from cost or capacity

The default 0.5 threshold is almost never right. Choose the threshold using one of these:

- **Cost-based:** minimize `FP * cost_fp + FN * cost_fn`. If scores are calibrated, the
  optimal threshold is `cost_fp / (cost_fp + cost_fn)`.
- **Capacity-based:** the ops team can handle N cases per day, so the threshold is the
  score of the Nth-ranked case. Report the precision and recall at that point.
- **Constraint-based:** maximize recall subject to precision ≥ X (or a false-positive rate
  cap for customer-facing friction).

`scripts/eval_report.py --cost-fp 5 --cost-fn 200` (or `--capacity 500`) produces the
threshold table. Show stakeholders the trade-off curve rather than a single number;
choosing the threshold is a business decision that data science informs.

---

## 3. Calibration

A model is calibrated if, among cases scored 0.2, about 20% are positive. Tree ensembles,
SVMs, and anything trained on resampled data are usually miscalibrated.

- Check it with a reliability table (binned predicted versus observed), the Brier score,
  and expected calibration error (ECE).
- Fix it with `CalibratedClassifierCV(method="isotonic")` (for large data) or `"sigmoid"`
  (Platt scaling, for small data), fit on a **separate** calibration fold, not the
  training data.
- If you undersampled negatives by a factor of k, correct the probabilities:
  `p = p_s / (p_s + (1 - p_s) * k)`, where `p_s` is the score from the model trained on
  the sampled data.
- Recheck calibration after every retrain and in production monitoring, since prevalence
  shifts break it.

---

## 4. Uncertainty on model metrics

The metric on a test set is an estimate. Report a CI:

- **Bootstrap:** resample the test rows (or entities, if rows are grouped) 1,000 or more
  times and recompute the metric. Use the 2.5th and 97.5th percentiles.
  `eval_report.py` does this.
- **Comparing two models on the same test set:** bootstrap the **difference** using paired
  resamples, rather than checking whether the two individual CIs overlap. For AUC,
  DeLong's test is an alternative.
- **Across CV folds:** report the mean ± SD across folds. Note that fold scores are
  correlated, so this understates the true uncertainty.
- **Small positives count:** with 50 positives in the test set, a recall CI will span
  about ±14pp. Say so.

---

## 5. Slice analysis and fairness

Aggregate metrics hide failures in segments. Always slice by the dimensions the business
cares about (region, product, channel, tenure, customer size) and, where lawful and
relevant, by protected or sensitive groups.

- Flag slices with too little data (e.g., fewer than 30 positives) as "insufficient data"
  rather than drawing conclusions from them.
- Look for slices where performance falls sharply, or where calibration differs (the same
  score meaning different risk levels for different groups).

**Fairness metrics.** These are mutually incompatible in general, so choose the one that
fits the harm and document why:

| Metric | Equalizes across groups | Use when |
|---|---|---|
| Demographic parity | Selection rate | Access to opportunities (marketing offers), with no label bias concern |
| Equal opportunity | True positive rate | Missing a deserving case is the harm (credit approval for creditworthy applicants) |
| Equalized odds | TPR and FPR | Both kinds of errors harm people |
| Predictive parity / calibration within groups | Precision or calibration | Scores are used as risk estimates by humans |

Common rules of thumb: the **four-fifths rule** (the selection rate of any group is at
least 80% of the highest group's rate) is a screening heuristic from US employment
practice, not a safe harbor. Removing the protected attribute does **not** ensure
fairness, because proxies (zip code, name, device) carry the same information. Test
outcomes, not just inputs. Involve legal or compliance for any regulated decision.

---

## 6. Explainability

- **Global:** permutation importance on the validation set (model-agnostic, and more
  honest than impurity importance) and mean |SHAP| values. Report them with the caveat
  that correlated features split credit between them.
- **Local:** SHAP values for individual predictions. These are needed for adverse-action
  reasons in lending and are useful for reviewer trust.
- **Shape:** partial dependence or ALE plots for the top features. Check that the
  directions make domain sense.
- **Sanity check:** a surprising top driver is a leak until it is explained. Correct-looking
  explanations don't prove the model is causal. SHAP explains the *model*, not the world.

---

## 7. Translating to business value

Stakeholders care about money and outcomes, not AUC. Build a simple value model:

```
value per period = (TP × value_of_catching) − (FP × cost_of_false_alarm) − (fixed costs of running it)
```

Compute it for the current process (baseline) and for the model at the chosen threshold.
Then report the incremental value, with a range derived from the metric CI. Be explicit
about assumptions (e.g., "assumes a 30% save rate on contacted churners, based on the
2025 retention pilot"). Where the treatment effect is uncertain, recommend an experiment
to measure it rather than assuming it.
