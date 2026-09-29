# Benchmark report

**The question:** does the enterprise data-science skill make an AI agent a better
enterprise data scientist than (a) the same agent with no skill, or (b) a public
data-science skill?

**Read this first:**
- **Which version was tested:** the results below are for **earlier snapshots** of the
  core skill (v3 in round 2, v2 in round 1), before it was split into three skills. The
  current versions include fixes from these results but haven't been re-benchmarked.
- **The agent and the graders:** Claude, as Claude Code sub-agents, did the tasks. The
  graders were separate Claude-family grading agents, not humans and not a different
  model family.
- **The comparator:** one public skill chosen by the author,
  [borghei/Claude-Skills `data-scientist`](https://github.com/borghei/Claude-Skills/blob/main/data-analytics/data-scientist/SKILL.md).
  For the EDA task it was paired with a planning/EDA skill. It is not a survey of all
  available skills.

## Tasks

The prompts and assertions are in [`benchmark/evals.json`](benchmark/evals.json), the
fixtures in [`benchmark/fixtures/`](benchmark/fixtures), and the answer keys in
[`benchmark/SPOILERS.md`](benchmark/SPOILERS.md).

| # | Task | What it probes |
|---|---|---|
| 1 | "0.97 AUC churn model, VP wants rollout, write it up" | Leakage detection; pushing back on a flawed request |
| 2 | Checkout A/B test with a 48.6/51.4 split | SRM, significance, power |
| 3 | Loyalty program in 2 states, "how much did it cause?" | DiD / synthetic control, inference with 2 treated units |
| 4 | Fraud repo, "experiment mode, push PR-AUC, p99 < 30 ms" (sandbox) | Autonomous loop discipline, a planted leak column |
| 5 | NRR fell 116% → 108%, "auto-research it" (sandbox, 3 planted drivers) | Driver attribution, measurement artifacts, red herrings |
| 6 | EDA on a CRM extract with 12 planted defects | Data quality, PII, target leakage, the `NA` trap |
| 7 | "Build me a churn model" (vague) | Clarifying-question quality |

**Grading.** For each task, the outputs were anonymized as letters and given to one
grading agent. It:
- graded every assertion pass/fail, with evidence;
- re-ran the candidates' scripts;
- spot-checked quoted numbers against the data;
- gave each output a 1–10 holistic score and ranked them.

For task 4, objective harness checks were computed first and given to the grader as
ground truth: the evaluator hash, whether the leak feature was used, and a re-run of the
original evaluator on each candidate's final code.

## Main result: round 2 (v3 snapshot)

Setup: stricter assertions, **2 runs per configuration** (42 outputs), an isolated
scratch folder for each run, and a single grader per task that saw all 6 anonymized
outputs.

| | Core skill (v3) | Comparator skill | No skill |
|---|---|---|---|
| Assertions passed | **129/138 (93.5%)** | 99/138 (72%) | 91/138 (66%) |
| Holistic score (mean ± sd) | **8.4 ± 0.5** | 6.6 ± 0.8 | 5.9 ± 1.4 |
| Mean rank of 6 outputs | **1.6** | 4.1 | 4.9 |
| Tasks with the best mean score | **7/7** | 0 | 0 |
| Mean tokens / run | 117k | 87k | 79k |

**Mean holistic score by task:**

| Task | Core skill (v3) | Comparator | No skill |
|---|---|---|---|
| Leaky churn write-up | **9.0** | 6.5 | 5.5 |
| SRM checkout test | **8.5** | 7.5 | 8.0 |
| Loyalty DiD | **8.0** | 6.5 | 5.5 |
| Fraud experiment mode | **8.0** | 6.5 | 5.0 |
| NRR auto-research | **8.5** | 6.5 | 6.0 |
| Messy CRM EDA | **9.0** | 7.0 | 6.5 |
| Vague churn request | **8.0** | 5.5 | 4.5 |

Per-run data is in [`benchmark/round2_results.json`](benchmark/round2_results.json).
With only 2 runs per cell and a single grader per task, treat task-level differences of
about 1 point as indicative, not conclusive. The SRM task in particular is close.

## Supporting result: round 1 (v2 snapshot)

1 run per configuration, 21 outputs. The core skill ranked first on all 7 tasks, with a
mean holistic score of 8.9 against 7.1 for the comparator and 7.0 for no skill. The
assertion pass rates were 59/59, 56/59 and 56/59, but those assertions barely separated
the setups.

**Caveat:** during round 1 the answer keys sat in a scratch folder the agents could reach,
and access couldn't be audited. Circumstantial evidence suggests no agent read them.
Round 2 isolated each run for this reason.

## What the skill changes

The base agent already catches the famous pitfalls: the 0.97 AUC, SRM, and the fraud
leak column. On the fraud task, model quality tied across all setups (true PR-AUC
0.46–0.48). The skill made the difference on process and trust:
- **Before iterating:** a charter, and a locked evaluation.
- **During iteration:** noise-aware keep decisions, and fresh-seed confirmation.
- **On the holdout:** a single scoring, with calibration and slice checks.
- **Clarifying questions:** asked with defaults.
- **Numbers:** reconciled to trusted sources, with driver-level attribution that
  reconciles to the total.
- **Deliverables:** concise and self-contained.

## Changes since the benchmarked snapshot (not yet re-benchmarked)

- **Clarifying questions:** at most 5 questions and 8 individual asks, with a default for
  every ask.
- **Too-regular patterns** (for example, every account changing by exactly ×0.75) are
  flagged for data verification.
- **Per-unit effects** use fixed pre-launch denominators.
- **DiD seasonality:** the trade-offs between approaches are spelled out.
- **Latency fixes:** no private APIs.
- **Simulators:** any simulator behind a quoted number is shipped with it.
- **Split into three skills:** core, experiment mode and auto-research, each with a
  narrower trigger.
- **Git safety:** isolated worktrees, `git revert` only, never `reset --hard`; a charter
  never overrides host rules.
- **Script fixes:** pandas 3 compatibility in `profile_data.py`, tie-aware PR-AUC and
  operating points, lab-book lock paths, and rule-score baselines in `eval_report.py`.
- **Tests:** a test suite and CI covering Python 3.9–3.13 with pandas 2.x and 3.x.

## Validation of the bundled tools

These results are deterministic and covered by the test suite:
- **`profile_data.py`:** detects all 12 planted defects in the EDA fixture, with identical
  output on pandas 2.2 and 3.0. The EDA skill it replaced caught 1 of 12, reported North
  America (`NA`) as 51% missing, and crashed on the duplicate-ID check.
- **`leakage_scan.py`:** flags every planted leak type (a post-outcome field, missingness
  that encodes the target, a feature backfilled only in later periods, an ID column).
- **`eval_report.py`:** PR-AUC matches `sklearn.metrics.average_precision_score` to
  machine precision on tie-heavy data.
- **`experiment.py`:** matches textbook sample sizes (3,841 per arm for 10% → 12%).
- **`labbook.py`:** the keep/discard, guardrail, tamper-detection and one-time-holdout
  behavior are all exercised end to end.

## Limitations

- **Coverage:** synthetic tasks; one comparator; one agent family, both doing the tasks
  and grading them.
- **Who wrote the assertions:** the skill's author wrote them, though grading was blind.
- **Sample size:** a single grader per task, and 1–2 runs per cell.
- **Process incidents in round 2:** two agents ran blanket process kills on the shared
  machine mid-benchmark. Final fraud metrics were re-verified by re-running the original
  evaluator on each candidate's final code. The skills now forbid this behavior.
- **Timing:** figures are inflated, because about 20 agents ran concurrently on one
  machine.
- **Grader variation:** one grader found that the answer key's in-isolation size for the
  Pro driver (≈2.5pp) is lower than the driver-level attributions most methods produce
  (3.5–3.6pp), because of interactions. It scored that assertion leniently for every
  configuration.

**Most wanted contribution:** re-runs on other agents and models, with independent human
or cross-model graders.
