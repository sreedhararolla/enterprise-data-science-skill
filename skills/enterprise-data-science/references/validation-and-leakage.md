# Validation design and leakage

Validation estimates how the model will perform on data it will actually see in
production. Any difference between how you split the data and how the future arrives
turns into optimism that disappears after launch.

## Contents
1. Choosing a split scheme
2. Time series and forecasting backtests
3. Nested CV and hyperparameter tuning
4. Leakage taxonomy
5. Point-in-time feature rules
6. Leakage audit procedure

---

## 1. Choosing a split scheme

Ask two questions. **When** is a prediction made, relative to the data used for
training? And **who** gets scored: entities that were in the training data, or new ones?

| Deployment reality | Split | Notes |
|---|---|---|
| Score future periods (most business models) | **Temporal**: train on data before T, test on data after T | Add a **gap** at least as long as the label window (for a 30-day churn label, leave 30 days between the end of train and the start of test) |
| Score new entities (new customers, new stores) | **Grouped** (`GroupKFold` on entity id) | Otherwise the model memorizes entity-level quirks |
| Both (the usual case) | Temporal, plus entities that are new in the test period tracked as a separate slice | Report performance for seen and unseen entities separately |
| Truly i.i.d. snapshot (rare) | Stratified K-fold | Justify why the data is i.i.d. |
| Repeated measures per entity (multiple rows per patient or user) | Grouped | Random splits put the same person in both train and test |
| Few positives | Stratified + grouped (`StratifiedGroupKFold`) | Report CIs; they will be wide |

Always keep a **final holdout** (ideally the most recent period) that you evaluate
exactly once, after all modeling choices are frozen. If you use it more than once, it has
become a validation set.

### sklearn snippets

```python
from sklearn.model_selection import TimeSeriesSplit, GroupKFold, StratifiedGroupKFold

# Temporal with gap (sklearn >= 0.24)
tscv = TimeSeriesSplit(n_splits=5, gap=30)          # gap in rows, so sort by time first

# Grouped
gkf = GroupKFold(n_splits=5)
for tr, te in gkf.split(X, y, groups=df["customer_id"]): ...
```

For temporal splits with irregular timestamps, split on actual dates rather than row
counts:

```python
cutoffs = pd.date_range("2025-01-01", "2025-12-01", freq="MS")
for c in cutoffs:
    train = df[df.event_time < c - pd.Timedelta(days=label_window)]
    test  = df[(df.event_time >= c) & (df.event_time < c + pd.offsets.MonthBegin(1))]
```

---

## 2. Time series and forecasting backtests

- Use **rolling-origin evaluation** (also called walk-forward): re-fit or re-score at each
  origin, forecast h steps ahead, and compare. Report error by horizon, since a model
  that is good one week out can be poor at eight weeks out.
- **Baselines are mandatory:** naive (last value), seasonal naive (the same period last
  season), and a moving average. Many sophisticated forecasters fail to beat seasonal naive.
- **Scale-free metrics:** use MASE (error relative to seasonal naive) or WAPE (sum |e| /
  sum |y|) rather than MAPE, which explodes near zero and penalizes over-forecasts and
  under-forecasts asymmetrically.
- **Hierarchies:** if forecasts roll up (SKU to category to total), check that they are
  coherent at every level, or reconcile them (bottom-up, or MinT).
- **Prediction intervals:** check their empirical coverage (does the 80% interval contain
  the actual value about 80% of the time?). Decisions like inventory depend on the
  intervals, not the point forecast.
- **Calendar effects:** holidays, promotions, price changes, and outages. Put them in as
  features or exclude them, but know which periods in your backtest were anomalous.

---

## 3. Nested CV and hyperparameter tuning

If the same data is used both to select hyperparameters and to report performance, the
reported performance is optimistic. Options, from most to least rigorous:

1. **Nested CV:** an inner loop tunes, an outer loop estimates. Use it for small data.
2. **Train / validation / test split in time:** tune on the validation window, then report on test.
3. **Tune by CV on train, report on an untouched holdout.** This is fine for large data.

Every data-dependent transform belongs **inside** the pipeline, so it is re-fit on each
training fold: imputation, scaling, target and frequency encoding, feature selection,
SMOTE or undersampling, PCA, and text vectorizers.

```python
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
pipe = Pipeline([("prep", ColumnTransformer([...])), ("model", clf)])
cross_val_score(pipe, X, y, cv=cv, groups=groups)  # prep re-fit per fold
```

---

## 4. Leakage taxonomy

| Type | Example | How to catch it |
|---|---|---|
| **Target leakage** (a feature encodes the outcome) | `cancellation_reason` in a churn model; `chargeback_flag` in a fraud model; `total_claims_paid` predicting claim approval | Single-feature power is too high; the domain question "when does this field get filled?" |
| **Temporal leakage** (future information) | Customer aggregates computed over the full history, including after the prediction date; a snapshot table showing the current status | Rebuild features "as of" the prediction timestamp; check features for update timestamps |
| **Train/test contamination** | The same customer, device, or near-duplicate text in both train and test | Grouped splits; dedupe; hash near-duplicates |
| **Preprocessing leakage** | Scaler, imputer, or target encoder fit on all the data; feature selection on the full dataset | Pipelines; review code for `fit` on the full X |
| **Label-definition leakage** | The label is derived from a feature (e.g., "high value" = revenue > X, with revenue as a feature) | Trace the lineage of the label |
| **Proxy leakage via process** | Missingness pattern reveals the outcome (e.g., collections fields only filled for defaulters) | `leakage_scan.py` missingness check |
| **Selection leakage** | Training only on cases that reached a stage the outcome influences | Define the population at prediction time, not in hindsight |
| **Tuning leakage** | Repeated peeking at the test set to choose models | Freeze the holdout; log each evaluation |

**Rule of thumb:** for noisy human-behavior targets (churn, conversion, default,
engagement), honest AUCs are usually 0.65–0.85. Above ~0.9, the burden of proof is on the
model.

---

## 5. Point-in-time feature rules

For each feature, document: **source table, the timestamp that defines availability, and
the latency between the event and when the field lands in the warehouse.**

- Join features with `feature_time <= prediction_time - latency`. In SQL, use an "as-of"
  join (`QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY feature_time DESC) = 1` over
  the filtered rows), or your feature store's point-in-time join.
- Tables of type SCD1, or "current state" tables, overwrite history, so they cannot be
  used for backtesting unless snapshots exist. Prefer SCD2 or event logs.
- Watch out for backfilled data. A field added in 2025 but backfilled to 2022 may use
  information that wasn't available in 2022.
- Account for latency. Data that lands with a T+2 delay in the warehouse cannot be used
  for T+0 scoring, even though it looks available in historical tables.
- **Train/serve parity:** use the same feature code path for training and serving, or at
  least compare their distributions (`drift_check.py`) on overlapping days.

---

## 6. Leakage audit procedure

1. Run `scripts/leakage_scan.py --data table.parquet --target y --time-col ts --id-cols customer_id`.
2. For each flagged feature, ask its owner or the documentation *when* it is populated.
3. Fit the model, then inspect the top 10 features by permutation importance. Each should
   have a plausible causal story that fits the prediction timestamp.
4. Drop the top feature and refit. If performance collapses from 0.97 to 0.70, the top
   feature was carrying the model, and it needs scrutiny.
5. Do a "time-travel" test: score a past date using only data as of that date (from
   snapshots). The result should match the backtest.
