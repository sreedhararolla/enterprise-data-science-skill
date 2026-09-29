# Enterprise EDA

EDA in an enterprise has one job: **find out whether this data can answer this question,
and what will go wrong if we trust it blindly.** Pretty distributions come second. This
playbook is self-contained, so it doesn't need another EDA skill to be installed.

## Contents
1. Ask first
2. Run the profiler
3. Grain, keys, and reconciliation
4. Fix-or-explain the issues
5. Univariate
6. Target and relationships
7. Time
8. Segments and Simpson's paradox
9. Scale and cost
10. EDA report

---

## 1. Ask first

Before profiling, ask the questions whose answers change what you check. Use the EDA
section of `intake-questions.md`, and ask only what you can't discover yourself:
- What question or decision is this data for? This determines which columns matter.
- What should one row be? Which column(s) should be unique?
- Is there a target or outcome? When is the prediction or decision made?
- What trusted number should this reconcile to (a dashboard, finance, the system of record)?
- Are there known issues, recent migrations, or backfills?
- Does the data contain personal data, and what may you do with it?

## 2. Run the profiler

```bash
python scripts/profile_data.py --data table.parquet --key customer_id --target churned --time-col event_date
```

It flags the following, each with a severity and a recommended action:
- PII columns, detected by name and by value pattern
- duplicate rows and duplicate business keys
- disguised nulls, and the literal `NA` gotcha
- numbers or dates stored as text
- numeric and date sentinels, future dates, and gaps in time coverage
- case and whitespace variants, and constant columns
- **missingness that predicts the target.**

The profiler was validated on a table with 12 planted enterprise data defects and caught
all of them. Treat it as the floor, not the ceiling.

**For warehouse tables,** profile in SQL: push the aggregation down, filter by partition,
and sample (`TABLESAMPLE` or a hash of the key modulo N) for the expensive checks. Then run
the profiler on a sample extract if you need its checks.

## 3. Grain, keys, and reconciliation

The profiler can't do these; they need judgment:
- **Grain:** state it ("one row per customer per month") and verify it with a
  uniqueness check on those columns.
- **Joins:** count rows before and after every join. Check key uniqueness on both sides.
  Report orphaned keys (keys with no match on the other side).
- **Reconcile:** compare total rows, the headline KPI, and a few spot-checked entities
  to the trusted source. Write down the gap and its explanation, e.g. "finance counts
  paused accounts as active; we don't".
- **Population:** who is missing? Deleted or purged records, test accounts, a region not
  yet migrated. Survivorship bias starts here.

## 4. Fix-or-explain the issues

For each HIGH or MED issue, either fix it (and log the fix in the assumptions log with
the affected row counts) or explain why it is acceptable. Never fix silently. Also:
- **PII first:** drop, hash, or aggregate it before anything else, and keep raw values
  out of notebooks, charts, and LLM prompts.
- **Missingness:** figure out why data is missing before choosing a treatment. Missing
  at random (MCAR/MAR) can be imputed. Missingness that depends on the missing value
  itself or on the process (MNAR) may need an indicator column. Missingness that predicts
  the target needs a *timing* check, because it may be a leak.
- **Outliers:** decide whether each is an error (fix it), a real extreme (keep it; use
  robust statistics), or a different population (segment it). Don't cap values by
  reflex.

## 5. Univariate

- **Numeric:** look at p1, p50, and p99, the skew, and zero or negative counts. For heavy
  tails, use log scales and medians rather than means.
- **Categorical:** look at cardinality, the top and rare values, and "Other" bucketing.
  Check whether the category mix shifts over time.
- **Dates:** look at the range, the volume per period (steps in volume indicate tracking
  or pipeline changes), and day-of-week patterns.
- **Text:** look at length distributions, templates or boilerplate, the language mix,
  and whether PII is embedded in free text.

## 6. Target and relationships

- **Target:** the base rate and how it changes over time (a drifting base rate breaks
  both models and experiments). Also check where labels come from, and their delay.
- **Univariate power** of each feature against the target:
  `scripts/leakage_scan.py --data ... --target ... --time-col ...`. Suspiciously strong
  features are leak suspects until their timing is confirmed.
- **Correlations:** use Spearman for skewed data and Cramér's V for categoricals. Flag
  pairs with |r| > 0.8 (redundancy) and relationships that should exist but don't
  (possible join errors).
- **Look at the shape,** not just coefficients. Binned target rates by decile of each top
  feature reveal non-linearity and thresholds.

## 7. Time

- Plot key metrics by week or month. Annotate launches, migrations, and outages.
- Check for trend, seasonality, and structural breaks. A break coinciding with a
  pipeline change is a data issue, not a behavior change.
- For forecasting: check autocorrelation, stationarity, calendar effects, and the
  length of history available per series.

## 8. Segments and Simpson's paradox

- Compare key rates across the three to five segments the business uses.
- Always check whether an aggregate relationship holds *within* segments. A mix shift can
  produce an aggregate trend that no segment shows, or even reverse it (Simpson's paradox).
- Clustering (k-means, HDBSCAN on scaled features) is exploratory. Profile the clusters in
  business terms, or don't present them.

## 9. Scale and cost

- Under 1M rows: work in memory with pandas.
- 1–50M rows: use Polars or DuckDB locally, or aggregate in the warehouse.
- Over 50M rows: aggregate in the warehouse and pull samples. Estimate scan cost before
  running full-table queries.
- For large scatter plots, sample 10–50k points; plot aggregates rather than raw points.

## 10. EDA report

```markdown
# EDA: [table] for [question/decision]
**Verdict:** Fit for purpose / Fit with fixes / Not fit, because […]

## Overview
Grain · rows · time range · source · refresh · reconciles to [trusted source]: yes/gap [x] explained by [y]

## Issues found (from profiler + manual checks)
| Severity | Issue | Rows affected | Action taken / proposed | Owner confirmed? |

## Key facts
- Target base rate [x%], stable/drifting · label delay [n days]
- Top distributions & relationships (with charts)
- Segments that behave differently

## Risks for modeling/analysis
Leakage suspects · survivorship · definition changes · small segments

## Recommended next steps
[Features to build, fixes to make, questions for data owners]

## Assumptions log
```
