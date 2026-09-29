# Benchmark report

**The question:** does this skill make an AI agent a better enterprise data scientist
than the same agent with no skill, or with the best existing data-science skill?

The benchmark agent was Claude (Claude Code sub-agents). The skill itself is
model-agnostic and uses the open Agent Skills format. Results on other models and agents
haven't been measured yet, and contributions are welcome.

## Setup

- **Three setups:**
  - this skill;
  - [borghei/Claude-Skills `data-scientist`](https://github.com/borghei/Claude-Skills/blob/main/data-analytics/data-scientist/SKILL.md),
    the most complete public data-science SKILL.md found (for the EDA task it was paired
    with a planning/EDA skill);
  - no skill.
- **Seven realistic tasks** (prompts and assertions are in `enterprise-data-science/evals/evals.json`):

| # | Task | What it probes |
|---|---|---|
| 1 | "0.97 AUC churn model, VP wants rollout, write it up" | leakage detection, pushing back on a flawed request |
| 2 | Checkout A/B test with a 48.6/51.4 split | SRM, significance, power |
| 3 | Loyalty program in 2 states, "how much did it cause?" | DiD/synthetic control, inference with 2 treated units |
| 4 | Fraud repo, "experiment mode, push PR-AUC, p99 < 30 ms" (sandbox) | autonomous loop discipline; a planted leak column |
| 5 | NRR fell 116% → 108%, "auto-research it" (sandbox, 3 planted drivers) | driver attribution, measurement artifacts, red herrings |
| 6 | EDA on a CRM extract with 12 planted defects | data quality, PII, target leakage, the 'NA' trap |
| 7 | "Build me a churn model" (vague) | clarifying-question quality |

- **Blind grading:** each task's outputs were anonymized and graded by an independent
  grader. The grader scored pass/fail assertions, re-ran scripts, spot-checked numbers
  against the data, and gave a 1–10 holistic score.
- **Objective harness checks** for the fraud task: evaluator hash, whether the leak
  feature was used, and a re-run of the original evaluator on the final code.

## Round 1: 1 run per setup, 21 outputs

| | This skill | borghei | No skill |
|---|---|---|---|
| Ranked 1st | **7/7** | 0 | 0 |
| Holistic score (mean) | **8.9** | 7.1 | 7.0 |
| Assertions passed | **59/59** | 56/59 | 56/59 |

The assertions barely separated the setups, so round 2 used stricter ones.

## Round 2: stricter assertions, 2 runs per setup, 42 outputs, isolated scratch folders

| | This skill (v3) | borghei | No skill |
|---|---|---|---|
| Assertions passed | **129/138 (93.5%)** | 99/138 (72%) | 91/138 (66%) |
| Holistic score (mean ± sd) | **8.4 ± 0.5** | 6.6 ± 0.8 | 5.9 ± 1.4 |
| Mean rank of 6 outputs | **1.6** | 4.1 | 4.9 |
| Tasks with the best mean score | **7/7** | 0 | 0 |
| Mean tokens / run | 117k | 87k | 79k |

**Mean holistic score by task:**

| Task | This skill | borghei | No skill |
|---|---|---|---|
| Leaky churn write-up | **9.0** | 6.5 | 5.5 |
| SRM checkout test | **8.5** | 7.5 | 8.0 |
| Loyalty DiD | **8.0** | 6.5 | 5.5 |
| Fraud experiment mode | **8.0** | 6.5 | 5.0 |
| NRR auto-research | **8.5** | 6.5 | 6.0 |
| Messy CRM EDA | **9.0** | 7.0 | 6.5 |
| Vague churn request | **8.0** | 5.5 | 4.5 |

Per-run data is in [`benchmark/round2_results.json`](benchmark/round2_results.json).

## What the skill changes

The base agent already catches the famous pitfalls: the 0.97 AUC, SRM, the leak column.
Model quality on the fraud task tied across all setups (true PR-AUC 0.46–0.48).
The skill wins on **process and trust**:
- a charter and locked evaluation before iterating;
- noise-aware keep decisions and fresh-seed confirmation;
- a single holdout scoring with calibration and slice checks;
- clarifying questions with defaults;
- reconciliation to trusted numbers;
- driver-level attribution that reconciles to the total;
- concise, self-contained deliverables.

## Validation of bundled tools

- **`profile_data.py`:** caught 12/12 planted defects in the EDA dataset, with no false
  positives on a clean table. The EDA skill it replaced caught 1/12: it reported
  North America ('NA') as 51% missing, and its duplicate-ID check crashed.
- **`leakage_scan.py`:** flagged every planted leak type (post-outcome field, target-encoding
  missingness, backfilled late-period feature, ID column).
- **`experiment.py`:** matches textbook sample sizes (3,841 per arm for 10% → 12%).
- **`labbook.py`:** keep/discard, guardrail, plateau, budget, tamper-detection and
  single-use holdout behavior were all exercised end to end.

## Improvements made from benchmark findings

- **After round 1 (v3):**
  - a deliverable-hygiene section: short replies, self-contained deliverables,
    consistent numbers, and headlines that obey the causal language ladder;
  - driver-based attribution in research mode;
  - the prediction horizon asked explicitly.
- **After round 2 (v5):**
  - a cap on clarifying questions (≤5 questions, ≤8 individual asks, a default on each);
  - ship any simulator behind quoted numbers;
  - flag too-regular patterns for data verification;
  - fixed pre-launch denominators for per-unit effects;
  - seasonality trade-offs in DiD;
  - no private-API latency hacks;
  - two script bug fixes.
- **v5 has not been re-benchmarked yet.**

## Limitations

- **Synthetic tasks, and a single competitor.** "Best" means best among the setups tested.
- **Grading:** one grader per task, and Claude-family models grading Claude-family outputs.
  Assertions were written by the skill author, but graded blind.
- **Round 1 contamination risk:** answer keys sat in a shared scratch folder during
  round 1, and access couldn't be audited. Circumstantial evidence suggests no leakage.
  Round 2 isolated each run.
- **Process incidents in round 2:** two runs killed all Python processes on the shared
  machine mid-benchmark. Final fraud metrics were re-verified by re-running the
  original evaluator.
- **Timing figures are inflated** by 20 concurrent agents sharing one machine.
