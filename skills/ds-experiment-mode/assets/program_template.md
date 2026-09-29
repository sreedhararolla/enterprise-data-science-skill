# Autonomous Run Charter: [title]

> Agree on this once with the human. After that, the agent runs without asking for
> anything this charter covers, and stops to ask for anything it doesn't.
>
> **This charter never overrides the host agent's rules.** Approval prompts, permission
> settings, sandboxing, network limits, and cost controls of the environment always take
> precedence. If the host asks for approval, ask; if an action is blocked, stop and report.

**Mode:** Experiment / Auto-Research · **Owner:** [human] · **Date:** [yyyy-mm-dd] · **Branch:** `exp/[yyyymmdd]-[slug]`

## 1. Objective
- **Goal:** [e.g., "Maximize PR-AUC of the SMB churn model" / "Explain the Q3 SMB churn rise"]
- **Decision it feeds:** [who acts on it, and how]
- **Success bar:** [e.g., "PR-AUC ≥ 0.48 on holdout (baseline 0.41)" / "≥ 80% of the change explained with high/medium confidence"]

## 2. Measurement (Experiment Mode)
- **Metric & direction:** [pr_auc, max]
- **Harness command:** `python run_experiment.py` → prints one JSON line: `{"metric":…, "std":…, <guardrails>}`
- **Validation scheme:** [temporal: train < 2026-04-01, valid 2026-04..06, 30-day gap]
- **Seeds/folds per run:** [3]
- **Noise (baseline seed std):** [0.003] → **min_delta:** [0.004]
- **Holdout:** [path], scored **once**, at the end

## 3. Surfaces
- **Editable:** [features.py, model_config.yaml, train.py]
- **Locked (fingerprinted):** [evaluate.py, data/prepare.py, data/valid.parquet, holdout]
- **Allowed libraries:** [already installed only / list]

## 4. Budget & limits
- **Per-run time box:** [10 min] (hard kill at 2x)
- **Total:** [80 runs] / [10 hours] / [$ warehouse scan or GPU-hour cap]
- **Patience (plateau trigger):** [12 runs without a keep]

## 5. Guardrails (every run must report these and pass them)
- [latency_ms ≤ 50]
- [fairness_gap (TPR difference across groups) ≤ 0.05]
- [model size ≤ 200 MB]

## 6. Allowed without asking
- Edit the editable surface in an isolated worktree or experiment branch; commit every
  candidate, and undo with `git revert` (never `reset --hard`, `clean -f`, or force-push)
- Run the harness, read-only warehouse queries within the scan budget
- Web search for methods and literature

## 7. Must stop and ask
- New data sources or access; anything touching production
- Installing packages; spending beyond the budget
- Changing the metric, validation scheme, or locked files (including "fixing" the evaluator)
- Sending data to any external service
- Anything involving raw PII beyond the approved tables

## 8. Stop conditions
- Budget exhausted · success bar met · plateau after 2 strategy changes · lock breach · 3 consecutive environment crashes

## 9. Deliverable
- `experiment_report.md` / `research_report.md` (lab-book report plus executive summary)
- Final holdout result with CI; what worked, what didn't, the practical ceiling, next steps
- Model card, if the model is headed to production

## 10. Research questions (Auto-Research Mode)
- **Fact to explain:** [one precise sentence, filled in after orientation]
- **Known context / suspected causes:** [launches, pricing changes, incidents]
- **Data in scope:** [tables]
- **Off-limits:** [...]
