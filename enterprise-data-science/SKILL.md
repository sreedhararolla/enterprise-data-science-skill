---
name: enterprise-data-science
description: >
  Senior enterprise data scientist playbook, plus two autonomous modes: Experiment Mode
  (autoresearch-style loop that edits, runs, and keeps or reverts changes against a locked
  metric within a budget) and Auto-Research Mode (hypothesis-driven investigation of open
  questions). Covers framing, data reconciliation, leakage-proof validation, baselines,
  A/B tests, causal claims, evaluation (CIs, calibration, slices, cost), exec briefs, and
  governed, monitored models. Use for any data science or ML work with business stakes:
  building or reviewing models, experiments, "did X cause Y", "why did metric drop",
  metrics and thresholds, leakage, model cards, drift. Also use when asked to run
  autonomously, overnight, "keep iterating until it improves", auto-tune or auto-improve a
  model, or research an approach, even without saying "data science" (e.g. "my AUC is 0.97",
  "is this lift real").
license: MIT
compatibility: Works in any Agent Skills-compatible agent. Bundled scripts need Python 3.9+ with pandas, numpy and scipy (pyarrow optional for Parquet).
metadata:
  author: Sreedhar Reddy Arolla
  version: "1.0.0"
---

# Enterprise Data Science

In an enterprise, a data scientist is paid for **better decisions**, not for models.
The model, the notebook and the p-value are only means to that end. What makes
enterprise work different from a Kaggle notebook:

- **Someone acts on the output.** Money, customers, or regulatory exposure depend on it,
  so a confident wrong answer is far worse than an honest "we can't tell yet".
- **The data was built for something else.** Warehouse tables were designed for billing,
  ops, or dashboards, not your question. They carry backfills, definition changes, and
  silent joins that fan out rows.
- **Other people inherit your work.** Reviewers, auditors, ML engineers, and future-you
  need to rerun it, understand it, and trust it.
- **Governance is real.** PII, fairness, model-risk review, and explainability rules shape
  what you may build, so they are design inputs, not paperwork you add at the end.

This skill is how a strong senior data scientist works. Scale the rigor to the stakes:
a quick metric lookup doesn't need a model card, but a credit model needs everything here.

---

## Operating principles

These are the habits that separate trustworthy work from impressive-looking work. Each
one exists because skipping it is a common, expensive failure.

1. **Start from the decision, not the data.** Before any code, know who will act, what
   they will do differently, and which error hurts more: a false positive or a false
   negative. That choice sets the metric, the threshold, and how much rigor you need. An
   analysis without a decision attached usually becomes a slide nobody uses.

2. **Reconcile before you analyze.** Tie your base numbers (row counts, totals, the
   headline KPI) to a source of truth the business already trusts: the finance number,
   the official dashboard, the system of record. If they don't match, stop and find out
   why. Otherwise the first stakeholder question ("why doesn't this match the dashboard?")
   will sink the whole analysis.

3. **Baseline before cleverness.** Always report a trivial baseline (predict the majority
   class, last period's value, seasonal naive, current business rule) and a simple model
   (regularized linear or logistic regression, or a shallow tree). Complex models must beat these by a
   margin that matters for the business, not just a better fourth decimal place. Most of
   the value is usually in the simple model plus good features.

4. **Validation must mirror deployment.** Split the data the way the future will arrive.
   If you predict next month, train on the past and test on later periods. If the model
   scores new customers, keep each customer entirely in train or entirely in test. Random
   K-fold on temporal or grouped data is the most common reason models collapse in
   production. See `references/validation-and-leakage.md`.

5. **Every number carries its uncertainty and its denominator.** Say "conversion rose
   from 4.1% to 4.6% (+0.5pp, 95% CI +0.1 to +0.9, n=48k per arm)", not "conversion
   rose 12%". Leaders make better calls when they see the spread, and you are protected
   when noise regresses to the mean.

6. **Match causal language to the study design.** Observational correlations may be
   described as "associated with". "Caused", "drove", and "the impact of" need a
   randomized experiment or a credible quasi-experimental design with its assumptions
   stated. Stakeholders will hear causation in whatever you write, so choose the words on
   purpose. See `references/experimentation-and-causal.md`.

7. **Suspect great results before celebrating them.** Unusually good performance is more
   often a bug, a leak, or a sample-ratio problem than a breakthrough. Run the red-flag
   table below before you tell anyone.

8. **Reproducible or it didn't happen.** Keep code in version control, pin the
   environment, set seeds, record query text and data snapshot dates, put parameters in
   config, and never hardcode credentials. Someone else must be able to get your numbers.

9. **Write for the person who acts.** Lead with the answer and the recommended action,
   then the confidence level, then the evidence. Methodology goes in an appendix. See
   `references/communication.md`.

---

## Ask before you build

Wrong assumptions in the first five minutes are the costliest errors in data science:
the wrong target, the wrong grain, the wrong population, or the wrong error costs. A
senior data scientist asks sharp questions first. Follow `references/intake-questions.md`:

1. **Look first, then ask.** Inspect the files, schemas, and code the user pointed to, so
   you never ask something the data can answer. Ask about intent, definitions,
   decisions, and constraints, which only humans know.
2. **Scale to the stakes.** A quick lookup gets 0–1 questions. A stakeholder analysis or
   one-off model gets one batch of 3–5. A production model, a regulated decision, or an
   autonomous run gets a full intake, recorded as a brief or charter.
3. **Ask in one batch,** with the question that would most change the approach first.
   Give **a recommended default and a one-line reason for each question**, so "defaults
   are fine" is a valid reply. If your environment offers a structured question tool
   (for example, a multiple-choice prompt), use it with the recommended option listed
   first.
4. **Show you've done your homework.** For example: "I checked the tables: 24 months of
   history, `churn_date` populated for 11%."
5. **If the user says "just go",** proceed. Open the deliverable with an **Assumptions**
   block listing each default and its impact if wrong.
6. **Re-ask when the data contradicts an answer** (the numbers don't reconcile, the grain
   differs, a feature is post-outcome). Don't silently work around it.

## Route the request

Figure out what kind of work this is, then go only as deep as it needs. Don't turn a
quick question into a twelve-step program.

| Request looks like | What to do | Read |
|---|---|---|
| "What was X last quarter?" / quick metric | Confirm the metric definition, reconcile against a trusted number, answer with the denominator and caveats | — |
| "Why did X drop/spike?" | Metric-movement playbook (below): data issues first, then mix, then real change | `references/communication.md` |
| New dataset / "what's in this data" / EDA | Ask the EDA intake questions, run `scripts/profile_data.py`, then check grain, keys, and reconciliation, and fix or explain each issue | `references/eda.md` |
| Build a predictive model | Phases 0 to 5 in full | `references/validation-and-leakage.md`, `references/evaluation.md` |
| Forecasting | Phases 0 to 5 with rolling-origin backtests and seasonal-naive baselines | `references/validation-and-leakage.md` §Time series |
| Design or read an A/B test | Power the test before launch; check SRM and guardrails before reading lift | `references/experimentation-and-causal.md`, `scripts/experiment.py` |
| "Did X cause Y?" with no experiment | Pick a quasi-experimental design, state its assumptions, run falsification checks | `references/experimentation-and-causal.md` §Observational |
| Review someone's analysis or model | Run the review checklist; lead with the issues that would change the decision | `references/review-checklist.md` |
| Ship, monitor, or document a model | Model card, monitoring plan, handoff | `references/production-and-governance.md`, `assets/model_card_template.md` |
| Anything touching people's data or regulated decisions | Governance checks before building | `references/production-and-governance.md` §Governance |
| "Improve this model as much as you can", "run experiments overnight", "keep iterating", auto-tune | **Experiment Mode** (below) | `references/experiment-mode.md` |
| Open-ended "why / what drives / where's the opportunity", or "research the best approach to X" | **Auto-Research Mode** (below) | `references/research-mode.md` |

---

## The workflow

Each phase ends with a **gate**: a short list of what must be true before you move on.
If a gate fails, go back rather than pressing forward. Late surprises cost far more than
early ones.

### Phase 0 — Frame the decision

Get these answers through the intake protocol above. Use the question bank for the task
type in `references/intake-questions.md`. Anything the user leaves to you becomes a
stated default in the Assumptions block.

- **Decision and owner:** what action changes based on the result, and who takes it?
- **Unit and moment of prediction:** what is one row (customer, order, account-week), and
  exactly *when* is the prediction made? This single fact defines leakage.
- **Target:** its exact definition, observation window, and how labels are produced
  (system event, manual review, proxy). Label noise caps achievable accuracy.
- **Cost of errors:** false positive versus false negative in business terms (dollars,
  customer harm, analyst hours). This drives both metric and threshold.
- **Success bar:** the lift over the current baseline or business rule that would justify
  changing behavior, and the date the decision is needed.
- **Constraints:** latency, batch versus real-time, interpretability or regulatory needs,
  features that are off-limits (protected attributes and their proxies).

For substantial projects, write this as a one-page brief using
`assets/analysis_brief_template.md` and get the owner to agree before modeling.

**Gate:** you can state in two sentences what decision this informs, what metric and
threshold represent success, and when the prediction is made.

### Phase 1 — Audit and reconcile the data

Start with `scripts/profile_data.py --data <file> --key <id> --target <y>`. It flags:
- PII
- duplicate keys
- disguised nulls and the `NA` gotcha
- numbers and dates stored as text
- sentinel values and future dates
- category variants
- missingness that predicts the target.

Then follow `references/eda.md`, and make sure these checks happen, since the profiler
can't do them:

- **Grain and keys:** confirm the grain is what you think. Check that primary keys are
  unique, and count rows before and after every join; a changed count means fan-out or
  dropped rows.
- **Reconciliation:** tie totals and the headline KPI to a trusted number (principle 2),
  and write down any gap and its explanation.
- **Point-in-time correctness:** for every feature, ask whether its value would have been
  known at prediction time. Watch for snapshot tables overwritten with current values,
  "last updated" fields, statuses, and aggregates computed over the full history.
- **Disguised missingness:** look for sentinels like -1, 0, 9999, `1900-01-01`, empty
  strings, "N/A" or "unknown". Check whether missingness correlates with the target,
  which is often a leak or a process artifact. The reverse also happens: pandas reads
  the literal string `NA` as null by default, which silently erases North America (or
  Namibia) from a region column. Load categorical codes with `keep_default_na=False`.
- **Definition drift:** metric logic, tracking, or source systems that changed during the
  window. Plot volumes over time and look for steps.
- **Population:** who is excluded (churned users purged, test accounts, one region)?
  Survivorship bias can quietly change the answer.
- **Sensitive data:** identify PII and protected attributes. Minimize, mask, or drop them
  unless there is a documented need.

Run `scripts/leakage_scan.py` on any supervised modeling table (see "Bundled scripts").

**Gate:** row counts and the KPI reconcile (or the gap is explained), each feature is
confirmed available at prediction time, and PII handling is decided.

### Phase 2 — Lock the validation design and baselines

Decide these **before** training anything, and write them down. Choosing the split or
metric after seeing results is how optimism creeps in.

- **Split scheme** that mirrors deployment: temporal with a gap sized to the label
  window, grouped by entity, or both. Keep a final holdout you touch only once.
- **Primary metric** tied to the decision, plus one or two secondary metrics and any
  guardrails (e.g., a precision floor, or a fairness gap ceiling). See `references/evaluation.md`.
- **Baselines:** a trivial one, the current business rule, and a simple model.
- **Preprocessing inside the pipeline:** fit scalers, imputers, target encoders, and
  feature selection inside each training fold only. Fitting them on all the data leaks
  test information.

**Gate:** the split, metric, and baselines are written down, and every preprocessing step
is fit only on training folds.

### Phase 3 — Model or analyze

- Start with the simple model. Add complexity (gradient boosting, then deep learning if
  the data is unstructured or huge) only when validation shows it pays off.
- Feature work usually beats algorithm work. Invest in domain features: recency,
  frequency, trends, ratios, and time since events.
- Tune hyperparameters with nested or inner-fold CV, or on a dedicated validation window,
  never on the test set. Track every experiment (MLflow, W&B, or a simple log) with its
  params, data version, and metrics.
- For class imbalance, prefer class weights and proper metrics (PR-AUC, cost-weighted)
  over resampling. If you resample, do it only inside training folds, and recalibrate afterward.
- Keep an **assumptions and decisions log** as you go (template below). This makes review
  fast and saves you when someone asks "why did you drop those rows?" three months later.

### Phase 4 — Evaluate like a skeptic

A single aggregate metric is not an evaluation. Cover:

1. **Versus baselines,** with confidence intervals (bootstrap). Is the lift outside the
   noise, and is it big enough to matter?
2. **Calibration,** if anyone will use the scores as probabilities or set thresholds on
   them. Report the Brier score and a reliability table, and recalibrate if needed.
3. **Threshold and cost:** choose the operating point from the business cost of errors or
   from capacity (e.g., "the team can review 500 cases a day"), not the default 0.5.
4. **Slices:** check performance by segment, region, tenure, and protected groups, and
   flag slices where n is too small to trust.
5. **Error analysis:** read 20 to 50 of the worst errors. Patterns here yield the next
   best feature, or reveal a labeling bug.
6. **Stability:** check performance across time periods or folds. A model that is great
   in one month and poor in the next is not ready.
7. **Explainability** at the level the audience needs: global importance (permutation or
   SHAP) and a few per-case explanations. Sanity-check that the top drivers make domain
   sense; a surprising top feature is often a leak.

Run `scripts/eval_report.py` on out-of-sample predictions to produce most of this at once.

**Gate:** the model beats the baselines by a meaningful, statistically credible margin; it
is calibrated or the threshold is set with that in mind; no critical slice fails; and the
red-flag table is clean.

### Phase 5 — Communicate and hand off

- Write the executive summary first (see `references/communication.md`): the answer,
  recommendation, confidence, business impact in dollars or units, the key caveats, and
  the next step.
- For models going to production: complete a model card (`assets/model_card_template.md`),
  a monitoring plan, and a retraining and rollback plan. See
  `references/production-and-governance.md`.
- Run `references/review-checklist.md` on your own work before sharing it.

---

## Autonomous modes

Complex problems are rarely solved in one pass. They need dozens of experiments or a
chain of hypotheses, each shaped by the last result. The two modes below let you work
through that loop for hours without a human, while staying trustworthy. Both follow the
same pattern:

1. **Agree on a charter once** (`assets/program_template.md`): objective, metric or
   question, editable versus locked surface, budget, guardrails, what needs permission,
   and stop conditions. After that, don't ask about anything it covers. Keep working
   until a stop condition is hit. Do stop for anything outside it (new data access,
   spending, production systems, packages, changing the metric).
2. **Keep state in the lab book** (`scripts/labbook.py`), not in memory. Start every
   iteration with `labbook.py state`, a summary of about 30 lines. Long runs stay cheap,
   and the work survives context compaction or a restart.
3. **Protect the measurement.** Fingerprint the evaluator, the splits, and the holdout.
   Keep a change only when it beats the noise. Make extra complexity earn a higher bar.
   Guardrails must pass. The holdout gets scored once, at the end. An autonomous
   optimizer will exploit any loophole in its measurement, so remove the loopholes
   before you start.
4. **Change strategy when stuck.** On a plateau: ablate, redo the error analysis, move
   to a different layer of the problem, or scout the literature. Stop cleanly when the
   ceiling is real.
5. **Finish with a report a human can audit:** what worked, what didn't, the confirmed
   result, and next steps.

**Experiment Mode** optimizes one metric. It works like Karpathy's *autoresearch* loop:
propose one atomic change, commit, run the time-boxed harness, then keep the change or
`git reset` to the best commit. The enterprise additions are noise-aware keep rules,
guardrails, budgets, a confirmation re-run to correct best-of-N optimism, and a one-time
holdout. See `references/experiment-mode.md`.

**Auto-Research Mode** answers open questions:
- pin down the precise fact to explain
- build a MECE issue tree, with "measurement artifact" as the first branch
- write falsifiable predictions *before* querying
- test the cheapest discriminating evidence first
- track the share of the effect explained so far
- red-team the leading story, then report the drivers and what was ruled out.

It also covers method and literature research ("what's the best approach to X?"). See
`references/research-mode.md`.

The modes can chain: research often reveals a metric worth optimizing (then use
Experiment Mode) or a causal question that needs an A/B test.

---

## Red flags: stop and investigate

When you see one of these, assume a problem until proven otherwise, and tell the user
plainly rather than burying it.

| Symptom | Usual cause | Check |
|---|---|---|
| AUC > ~0.95 or R² > ~0.9 on a behavioral or business target | Target leakage | Rank single-feature power (`leakage_scan.py`); check the timestamps of the top features |
| Test/holdout score ≥ train or CV score | Leakage, split bug, or distribution shift | Re-check the split logic and look for duplicate entities across splits |
| One feature dominates importance | Leak, ID, or a proxy of the target | Ask how and when that field gets populated |
| An ID, row number, or timestamp is predictive | Ordering leak or data drift | Drop it and apply a temporal split |
| Great offline, poor in production | Train/serve skew or point-in-time errors | Compare feature distributions at training versus serving (`drift_check.py`) |
| A/B arm sizes differ from the design | Sample ratio mismatch (SRM): assignment or logging bug | `experiment.py srm`. Don't read results until SRM passes |
| Big lift (>10–20%) on a mature product | Bug, novelty effect, SRM, or peeking | Check guardrails and SRM, look at the effect over time, try an A/A test |
| p just under 0.05 after several looks or metrics | Peeking or multiple comparisons | Pre-registered analysis, sequential methods, correction for multiple metrics |
| The trend reverses within segments | Simpson's paradox or mix shift | Decompose by segment: rate change versus mix change |
| Row count changes after a join | Fan-out or dropped keys | Check key uniqueness on both sides |
| The number doesn't match the dashboard | Definition, filter, timezone, or currency differences | Reconcile the definitions line by line |
| A metric step change on a specific date | Tracking or definition change, backfill, or outage | Annotate a timeline with deploys and pipeline changes |

---

## Metric-movement playbook ("why did X drop?")

Work in this order. Most "drops" turn out to be the first two:

1. **Is it real?** Check data freshness, pipeline failures, tracking or definition changes,
   bot filtering, timezone, and partial-day effects. Compare against an independent source.
2. **Is it expected?** Seasonality, holidays, calendar effects, known launches, and
   marketing changes. Compare to the same period last year and to the forecast.
3. **Where is it?** Decompose the change by segment (platform, region, channel, cohort,
   new versus existing). Separate the **rate effect** (behavior changed inside segments)
   from the **mix effect** (segment weights changed).
4. **Why?** Build hypotheses for the concentrated segments, test them against the data,
   and say which ones you ruled out.
5. **Report** in the form "X moved by Δ (vs. expected range). Y% is explained by A,
   Z% by B, remainder unexplained. Confidence: medium. Next step: …"

---

## Assumptions and decisions log

Keep one for any non-trivial piece of work and include it in the deliverable:

```markdown
| # | Date | Assumption / decision | Why | Impact if wrong | Verified? |
|---|------|-----------------------|-----|-----------------|-----------|
| 1 | 2026-09-27 | Exclude test accounts (is_internal = 1) | Not real customers | Low — 0.3% of rows | Yes, with eng |
| 2 | 2026-09-27 | Churn = no login in 60 days | Matches CS team definition | High — changes the label | Pending owner sign-off |
```

---

## Deliverable hygiene (check before sending)

A blind benchmark of this skill found that its outputs are strong on substance. Where
they lost points was packaging. Fix these every time:

- **Short first, depth in files.** The reply the user reads should fit on about a page
  (roughly 800 words at most, and don't restate appendix content in the body):
  the answer, the recommendation, confidence, the key numbers, questions, and next steps.
  Put the methodology, tables, and appendices in separate files, and don't repeat the
  same content in the reply, the memo, and the log.
- **Self-contained deliverables.** Never tell the user to run a script they don't have.
  If a bundled script (e.g. `leakage_scan.py`) is part of the recommended workflow,
  copy it into the output folder and reference that copy. Don't talk about skill
  internals (lab book, skill name) in stakeholder-facing text unless it helps them.
- **One set of numbers.** Before sending, reread the reply, the memo, the logs, and
  any chart titles. Every figure, duration, and recommendation must match everywhere.
  Contradictions like "rerun 2 weeks" in one place and "4 weeks" in another destroy
  trust.
- **Headlines obey the language ladder.** A headline can't be more causal or certain
  than the evidence in the body supports. Say "most consistent with a failed
  repricing", not "repricing backfired", unless the design supports causation.
- **Every quoted number is reproducible from what you ship.** If you validate tooling on
  simulated data, include the simulator (with its seed) next to the results, so a
  reviewer can regenerate every figure you cite.
- **Hashing is not anonymization.** A hashed email or ID is still personal data
  (pseudonymous). Drop it unless it is needed for joins, and keep the key map separate.

## Code and deliverable standards

- **Push compute to the warehouse.** Aggregate in SQL, and pull samples or aggregates into
  Python rather than full tables. Filter on partition columns. Estimate scan costs on large
  tables before you run them.
- **Parameterize queries** (no string-concatenated user input) and keep credentials in the
  environment or a secret manager, never in notebooks.
- **Make it reproducible:** seeds, a pinned environment (`requirements.txt`, lockfile or
  conda env), query text saved with results, and snapshot dates recorded.
- **Keep notebooks for exploration and pipelines for production.** Move reusable logic
  into modules with tests. Before sharing a notebook, restart it and run all cells top to bottom.
- **Keep sensitive data out of logs and outputs.** Don't print raw PII in outputs,
  charts, or LLM prompts, and aggregate to safe group sizes before sharing.

---

## Bundled scripts

All scripts are standalone Python (pandas, numpy, scipy only). Run them with `--help`
for their options. They produce Markdown you can paste into a report.

- `scripts/profile_data.py`: the enterprise data profile. It returns a list of issues,
  each with a severity and a recommended action: PII, duplicate keys, disguised nulls or
  `NA`, numbers or dates stored as text, sentinels, future dates, gaps in time coverage,
  category variants, constant columns, and missingness that predicts the target.

- `scripts/experiment.py`: A/B test math.
  - `power`: sample size per arm for a proportion or mean metric, given a baseline and MDE
  - `mde`: the minimum detectable effect for a given sample size
  - `srm`: the sample ratio mismatch chi-square test
  - `analyze`: difference and relative lift with CIs, from summary counts or means
- `scripts/leakage_scan.py`: ranks each feature's univariate predictive power against the
  target (out-of-fold, so categorical IDs can't cheat), and flags suspiciously strong
  features, ID-like columns, target-correlated missingness, leak-suggestive names, and
  (with `--time-col`) features whose power jumps in later periods.
- `scripts/eval_report.py`: evaluation report from a CSV of out-of-sample predictions.
  - Classification: metrics with bootstrap CIs versus a baseline, calibration (Brier and
    reliability table), a threshold table with optional costs or capacity, and per-slice
    metrics with small-n warnings.
  - Regression: MAE, RMSE, and bias versus mean or naive baselines, plus per-slice metrics.
- `scripts/drift_check.py`: population stability index (PSI) and KS tests between a
  reference dataset (training) and a current one (serving or recent data), per feature.
- `scripts/labbook.py`: persistent state for the autonomous modes. It provides:
  - `init`, with a charter, locks, and guardrails
  - `log`, which decides keep or discard automatically and suggests the git action
  - `idea` (the backlog) and `hyp` (hypotheses with predictions and verdicts)
  - `state` (a compact summary for each iteration)
  - `holdout` (single use) and `report`.

---

## Reference files

Read the one that matches the task; you don't need them all.

- `references/intake-questions.md`: the clarifying-question protocol and question banks
  for each task type, with a worked example.
- `references/eda.md`: the self-contained enterprise EDA playbook: grain and keys,
  reconciliation, fix-or-explain, target analysis, time, segments, and a report template.

- `references/validation-and-leakage.md`: split strategies (temporal, grouped, nested
  CV, backtesting), a leakage taxonomy with examples, and point-in-time feature rules.
- `references/evaluation.md`: choosing metrics by problem, thresholds from cost or
  capacity, calibration, fairness metrics, and uncertainty for model metrics.
- `references/experimentation-and-causal.md`: experiment design, power, SRM, CUPED,
  peeking and sequential testing, multiple metrics, interference, and observational
  methods (DiD, synthetic control, RDD, IV, matching and weighting) with their assumptions.
- `references/production-and-governance.md`: MLOps handoff, monitoring (drift,
  performance, data quality), retraining, model cards, model-risk management, privacy,
  fairness, and regulatory context.
- `references/communication.md`: executive summary structure, language for uncertainty
  and causality, how to present model results, and chart rules.
- `references/review-checklist.md`: the pre-delivery QA checklist, also used to review
  others' work.
- `references/experiment-mode.md`: the autonomous optimization loop, search policy,
  plateau playbook, integrity rules, confirmation and holdout, and long-running jobs in an agent harness.
- `references/research-mode.md`: autonomous hypothesis-driven investigation, issue trees,
  red-teaming, method and literature research, and evidence standards.
- `assets/analysis_brief_template.md`, `assets/model_card_template.md`,
  `assets/program_template.md` (the charter for autonomous runs): fill-in templates.
