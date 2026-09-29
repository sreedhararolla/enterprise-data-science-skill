# Experimentation and causal inference

## Contents
1. Before launch: design
2. Power and sample size
3. During the test
4. Analysis
5. Common traps
6. Observational causal inference
7. Language ladder

---

## 1. Before launch: design

Write a short pre-registration before the test starts. It prevents the most common form
of self-deception, which is choosing the metric or the stopping point after seeing the data.

- **Hypothesis:** "Changing X will increase Y because Z."
- **Unit of randomization:** user, account, session, store, or region. Randomize at the
  level where interference is contained (e.g., randomize accounts, not individual users,
  for B2B tools used by teams).
- **Primary metric (one),** secondary metrics, and **guardrails** (latency, errors,
  unsubscribes, revenue per user, support tickets) that must not degrade.
- **MDE:** the smallest effect worth acting on (a business decision), then the sample size
  and duration from the power calculation.
- **Duration:** at least one full weekly cycle (usually two), even if the sample size is
  reached sooner, so weekday and weekend behavior are both covered.
- **Decision rule:** ship if the primary metric improves significantly and no guardrail
  degrades beyond its tolerance. Decide in advance what happens with a neutral result.
- **Analysis unit = randomization unit.** If you randomize users but analyze sessions or
  page views, use the delta method or cluster-robust standard errors. Otherwise the
  p-values will be far too small.

## 2. Power and sample size

```bash
python scripts/experiment.py power --baseline 0.041 --mde-rel 0.05 --alpha 0.05 --power 0.8
python scripts/experiment.py power --metric mean --baseline 52.3 --sd 110 --mde-abs 1.5
python scripts/experiment.py mde --baseline 0.041 --n-per-arm 60000
```

- Revenue-type metrics are heavy-tailed, and their large SD means huge sample sizes are
  needed. Options: winsorize or cap at p99 (pre-registered), use a proxy metric, or
  apply **CUPED** (below).
- If traffic is too low to detect a reasonable MDE, say so. The alternatives are a bigger
  change, a more sensitive metric, a longer test, or accepting a directional read (with
  its lower confidence stated).

## 3. During the test

- **Check SRM first, and early:** `python scripts/experiment.py srm --counts 50410 49120`.
  At p < 0.001, stop. Assignment or logging is broken (bot filtering, redirects, crashes
  in one arm, caching). The results cannot be trusted, no matter how good they look.
- **Don't peek and stop.** Checking daily and stopping the first time p < 0.05 inflates
  the false positive rate to 20–30% or more. If you need to monitor, use a sequential
  method (group sequential boundaries, always-valid p-values or mSPRT) chosen before
  launch. Monitoring guardrails for harm is fine, and encouraged.
- **Watch for novelty and primacy effects:** plot the treatment effect by day. An effect
  that decays is often a novelty spike.

## 4. Analysis

```bash
# proportions: conversions and totals per arm
python scripts/experiment.py analyze --metric proportion --control 2050 50000 --treatment 2230 50100
# means: mean, sd, n per arm
python scripts/experiment.py analyze --metric mean --control 52.3 110 50000 --treatment 53.9 112 50100
```

- Report the absolute and relative lift, each with a CI, plus the p-value. The CI is more
  useful than the p-value for decisions: "somewhere between +0.1pp and +0.9pp".
- The relative-lift CI uses the delta method, and the script handles it.
- **CUPED / regression adjustment:** use the metric's pre-period value as a covariate
  (`Y_adj = Y − θ(X_pre − mean(X_pre))`, with `θ = cov(Y, X_pre)/var(X_pre)`). This
  often reduces variance by 20–50%, which shortens tests. Use it only with covariates
  measured **before** assignment.
- **Multiple metrics or segments:** with 20 metrics, one will be "significant" by
  chance. Pre-register the primary metric; treat everything else as exploratory, or apply
  Benjamini–Hochberg. Segment findings that were not pre-registered are hypotheses for the
  next test, not conclusions.
- **Heterogeneous effects:** these are worth exploring (causal forests, or segment
  interactions), but confirm them in a follow-up test before targeting based on them.

## 5. Common traps

| Trap | Symptom | Fix |
|---|---|---|
| SRM | Arm sizes differ from design | Debug assignment and logging; discard the results |
| Peeking | "Significant" on day 3, gone by day 14 | Fixed horizon, or sequential design |
| Unit mismatch | Tiny p-values on session metrics | Delta method, or cluster-robust SEs |
| Interference / network effects | Marketplace, social, or shared inventory | Cluster or switchback randomization, geo tests |
| Trigger dilution | Effect only on users who see the change | Analyze triggered users (those who reached the change point in both arms) |
| Survivorship in the metric | Revenue per *purchaser* rises because fewer marginal buyers purchased | Use per-assigned-user metrics |
| Twyman's law | Too good to be true | It usually is. Check SRM, logging, and A/A tests |
| Long-term effects | Short-term clicks, long-term churn | Holdback groups; long-term proxy metrics |

## 6. Observational causal inference

When randomization is impossible, choose a design whose assumptions you can defend, **state
them explicitly**, and run falsification checks. Without a design, you have a correlation.

| Method | Use when | Key assumption | Check |
|---|---|---|---|
| **Difference-in-differences** | A treated group and a comparable control, with before and after data | Parallel trends absent treatment | Plot pre-trends; run an event study; placebo on pre-periods. With staggered adoption, use modern estimators (Callaway–Sant'Anna, Sun–Abraham), not two-way fixed effects |
| **Synthetic control** | One or a few treated units (a region, a market) and many donor units | A weighted mix of donors reproduces the treated unit's pre-period | Pre-period fit; placebo-in-space tests |
| **Regression discontinuity** | Treatment assigned by a threshold on a score (credit score ≥ 700) | No manipulation at the cutoff; continuity | Density test at the cutoff (McCrary); covariate balance; bandwidth sensitivity |
| **Instrumental variables** | Something shifts treatment but affects the outcome only through treatment | Exclusion restriction (untestable, so argue it) | First-stage strength (F > 10); overidentification tests if more than one instrument |
| **Matching / weighting (PSM, IPW, AIPW)** | Rich pre-treatment covariates | No unmeasured confounding | Covariate balance (SMD < 0.1); overlap / positivity; **sensitivity analysis** (E-value, Rosenbaum bounds) |
| **Interrupted time series** | Only aggregate series and a known intervention date | No concurrent shock | Control series; placebo dates |

**Seasonality in DiD.** When treated units have different seasonal patterns from the
controls, plain unit + time fixed effects are biased. There are two common fixes, and
they fail in different ways:
- **Unit × calendar-month effects** (or same-calendar-month baselines) are more precise,
  but they absorb any treated-specific **trend** into the effect estimate.
- **Year-over-year differencing** is robust to unit trends and seasonality, but has
  lower power, loses the first year of data, and roughly doubles the minimum
  detectable effect.

Estimate both, report the minimum detectable effect (MDE) from placebo spread for each,
and explain any disagreement.

**Per-unit denominators must be fixed before treatment.** For "revenue per customer",
divide by a customer base frozen before launch (e.g. customers active in the 12 months
before launch), not by a rolling or monthly-active count. A program can change a rolling
count, for example by reactivating lapsed customers or attracting new ones, which moves
the ratio even when spending doesn't change. Report the effect on total revenue and on
customer counts separately, too. If they diverge, test whether a treated-specific trend
exists in the pre-period.

General rules:

- Draw the causal graph (DAG) first, even informally. Control for **confounders**, never
  **mediators** (they block the effect) or **colliders** (they create bias).
- Only pre-treatment covariates belong in adjustment sets.
- Report a sensitivity analysis: "An unmeasured confounder would need to be associated
  with both treatment and outcome by a risk ratio of 2.1 to explain this away."
- Useful Python libraries: `statsmodels`/`linearmodels` (DiD, IV), `DoWhy` / `EconML`
  (identification, heterogeneous effects), `CausalML`, `pysyncon` (synthetic control),
  `rdrobust` (RDD).

## 7. Language ladder

Match the claim to the evidence:

| Evidence | Say |
|---|---|
| Randomized experiment, clean SRM, pre-registered metric | "X **caused** a +0.5pp (CI +0.1 to +0.9) increase in Y" |
| Strong quasi-experiment with checks passed | "Our best estimate is that X **increased** Y by …, assuming [key assumption]; checks A and B support this" |
| Adjusted observational comparison | "After adjusting for A, B, C, X is **associated with** …; unmeasured factors could explain part of this" |
| Raw correlation or trend | "Y was higher when X was present; we **can't yet say** whether X drove it" |
