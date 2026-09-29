---
name: ds-experiment-mode
description: >
  Autonomous, guarded optimization loop for an ML model or pipeline (autoresearch-style):
  agree a charter, lock the evaluator and holdout, then repeatedly make one change, run a
  time-boxed evaluation, and keep or revert it with noise-aware rules, guardrails
  (latency, fairness), budgets, plateau handling, a fresh-seed confirmation and a single
  final holdout scoring. Use only when there is an existing evaluation harness and one
  metric to push, and the user asks to iterate autonomously, e.g. "push PR-AUC as high as
  you can", "run experiments overnight", "keep iterating until it stops improving",
  "auto-tune this model". Not for one-off modeling questions or open-ended "why" questions.
license: MIT
metadata:
  author: Sreedhar Reddy Arolla
  version: "1.2.0"
---

# Experiment Mode: guarded autonomous optimization

**Requirements:** Needs shell access and git. Bundled scripts need Python 3.9+ with pandas, numpy and scipy; they make no network calls. Works in any Agent Skills-compatible agent.

Experiment Mode runs many propose → run → measure → keep/revert cycles without a human in
the loop, like Karpathy's *autoresearch*, but with the protections an enterprise needs:
noise-aware decisions, locked evaluation, guardrails, budgets, recoverable history, and a
one-time holdout.

**Host rules come first.** The charter below defines what *you* may do without asking
the user. It never overrides the host agent's own approval prompts, permission settings,
sandbox, network, or cost limits. If the host asks for approval, ask. If an action is
blocked, stop and report; don't find a workaround.

## Contents
1. When to use it
2. The charter
3. Setup (isolated worktree)
4. The loop
5. Search policy
6. Plateau playbook
7. Crashes and timeouts
8. Integrity rules
9. Stopping, confirmation, and the holdout
10. Long-running jobs
11. Final deliverable

---

## 1. When to use it

Use it when all three of these hold:
- There is **one scalar metric** to optimize, with a direction (e.g., validation PR-AUC,
  WAPE, latency).
- There is a **harness**: a single command that trains and evaluates a candidate and
  prints the metric, within a bounded time.
- Candidates are made by **editing a well-defined surface** (a feature file, a model
  config, `train.py`).

If the goal is to *understand* something ("why did churn rise?"), this is the wrong
skill; use an investigation workflow instead (e.g. the `ds-auto-research` skill). If the
metric or validation scheme isn't settled yet, settle it first. The split must mirror
deployment (temporal and/or grouped), and there must be baselines and a final holdout
nobody has touched. An autonomous loop pointed at the wrong metric just produces the
wrong answer faster.

## 2. The charter: agree once, then run unattended

Fill in `assets/program_template.md` with the user, the way autoresearch uses
`program.md`. It defines:
- the objective and success bar
- the metric and the validation scheme
- the **editable** surface and the **locked** surface
- the time box per run, and the total budget (runs, hours, money)
- guardrails
- allowed and forbidden actions
- stop conditions

Ask the charter questions in one batch, with a default for each. Once agreed, **don't ask
the user about anything the charter covers.** Keep going until a stop condition is hit.
**Do stop and ask** before anything outside it: new data access, spending beyond the
budget, installing packages, touching production, sending data to external services,
changing the metric or validation scheme, or anything the host environment requires
approval for.

## 3. Setup

1. **Work in an isolated worktree or branch, never on the user's working copy.**
   ```bash
   git worktree add ../<repo>-exp-<yyyymmdd> -b exp/<yyyymmdd>-<slug>
   ```
   If worktrees aren't possible, use a new branch after confirming the working tree is
   clean. Never discard the user's uncommitted work.
2. **Every candidate becomes a commit,** so every result is recoverable. To undo a
   candidate, use `git revert --no-edit <sha>`, which keeps history. **Never use
   `git reset --hard`, `git clean -f`, `git checkout -- .`, or force-pushes** in this
   workflow; they destroy work that can't be recovered.
3. **Harness:** confirm or write `run_experiment.py` so that it:
   - runs K seeds or folds (3 is typical);
   - enforces the time box and exits non-zero on failure;
   - prints one JSON line (`{"metric": ..., "std": ..., "latency_ms": ...}`);
   - never touches the holdout.

   Keep the harness deterministic: set seeds, pin versions, and use a fixed data snapshot.
4. **Measure the noise:** run the unchanged baseline on 3–5 seeds. Set `min_delta` to
   about 1–2× the seed std, or to the smallest gain that matters to the business if that
   is larger. Without this, the loop keeps seed luck.
5. **Initialize the lab book,** locking everything that must not change:
   ```bash
   python scripts/labbook.py init --mode experiment \
     --objective "Churn model: maximize PR-AUC on 2026-Q2 temporal validation" \
     --metric pr_auc --direction max --min-delta 0.004 \
     --budget-runs 80 --budget-hours 10 --patience 12 \
     --guardrail "latency_ms<=50" --guardrail "fairness_gap<=0.05" \
     --lock evaluate.py --lock data/prepare.py --lock data/valid.parquet \
     --holdout data/holdout.parquet
   python scripts/labbook.py log --desc "baseline" --metric 0.412 --std 0.003 \
     --commit $(git rev-parse --short HEAD) --extra latency_ms=4 fairness_gap=0.02
   ```
6. **Seed the idea backlog** from the brief, EDA findings, error analysis, and method
   scouting: `python scripts/labbook.py idea add "recency x frequency interaction" --priority 4`.

## 4. The loop

Repeat until a stop condition is hit:

1. **Read the state:** `python scripts/labbook.py state` (about 30 lines: best result,
   recent runs, rejected ideas, top ideas, budget, lock status). Rely on it instead of
   re-reading old logs, which keeps each iteration's context small.
2. **Choose one change** (§5). Write it as a one-line hypothesis: *"Adding 90-day spend
   trend will lift PR-AUC because error analysis showed declining spenders being missed."*
3. **Make one atomic change and commit it.** Two changes at once hide which one helped.
4. **Run the harness** with a hard timeout of about 2× the time box.
5. **Log it:** `python scripts/labbook.py log --desc "<hypothesis>" --metric M --std S
   --commit <sha> --complexity simpler|same|more --extra latency_ms=..`
6. **Follow the decision.**
   - **KEEP:** stay on this commit.
   - **DISCARD:** `git revert --no-edit <sha>`. The change stays in history, recoverable.
   - **CRASH:** see §7.

   The rule: an improvement must exceed max(min_delta, combined seed std). A `more`
   complex change must clear twice that bar. A `simpler` change is kept if it's within
   noise of the best.
7. **Every ~10 runs, consolidate.** Write a `note` recording what works, what's dead,
   and where gains probably are, then re-prioritize ideas. After any batch of feature
   changes, run `python scripts/leakage_scan.py` on the modeling table.

Override a decision (`--decision keep --reason ...`) only for a stated reason. The
override is recorded.

## 5. Search policy

**Expected value by layer.** On enterprise tabular problems most gains come from the top:
1. **Data and label fixes:** the label definition, dedup, point-in-time corrections, and
   filtering bad rows out of training (never out of validation).
2. **Features:** recency, frequency and monetary features; trends and deltas; ratios;
   time since last event; entity aggregates; domain rules turned into features.
3. **Model family and objective:** linear → gradient boosting → specialized. Use a loss
   that matches the metric.
4. **Hyperparameters:** run a *batch* search (e.g. a fixed-budget Optuna run) inside one
   run, on training-only splits, and log it as one experiment. Never tune on validation
   outside counted runs.
5. **Ensembling and stacking:** last, and only if the gain justifies the operational cost.

**Explore versus exploit.** Mostly make incremental changes from the current best. About
every 5th run, try a bold idea: a different representation, model family, or target.
Base choices on error analysis (worst slices), feature importance, and the rejected list
(don't retry without a new angle).

**Method scouting.** When starting out, or on a plateau, look up how others solved
similar problems: papers, reputable write-ups, library docs. Add the promising ones as
ideas with `--source`. Prefer reproducible methods from a similar data regime over
leaderboard tricks.

## 6. Plateau playbook

When `state` shows PLATEAU (no keep in `patience` runs):
1. **Ablate the kept changes.** Revert each recent keep one at a time; some passed by luck.
2. **Redo the error analysis.** Look at the 50 worst errors and the worst slices.
3. **Move up a layer** in §5.
4. **Scout methods** and add 3–5 ideas.
5. **Question the ceiling.** Estimate the limit set by label noise or missing signal.
6. If two strategy changes both plateau, **stop**. State the practical ceiling and what
   would move it (new data, a relabel, a different target).

## 7. Crashes and timeouts

- **Trivial bugs:** fix and rerun. It still counts as the same idea.
- **Out of memory or a timeout:** try a smaller variant once, or log it as a timeout.
- **Conceptually broken ideas:** `labbook.py log --status crash`, then move on.
- **Three crashes in a row:** stop and check the environment. Don't burn budget on a
  broken machine.

## 8. Integrity rules (anti-gaming)

An autonomous optimizer finds every shortcut to a better number. These rules keep the
number meaningful:
- **Never edit locked files:** the evaluator, the metric, splits, data preparation, the
  holdout. `labbook.py` fingerprints them and discards results if they change. If the
  evaluator has a genuine bug, stop and tell the user.
- Never train on validation or holdout rows, tune on the holdout, or drop "hard" rows
  from validation.
- Features must be available at prediction time. Treat any gain above ~5× the typical
  gain as a suspected leak: run the leakage scan and check the feature's timing *before*
  keeping it.
- Guardrails are mandatory. A run that doesn't report one is discarded.
- Don't relax `min_delta` mid-run.
- **Latency fixes use public, durable mechanisms,** such as thread limits
  (`threadpoolctl`), batching, ONNX/Treelite export, or a NumPy tree export with a test
  asserting identical scores. Never use private APIs (names starting with `_`) or a
  silent fallback to a path that breaks the budget.

## 9. Stopping, confirmation, and the holdout

**Stop** when any of these happens:
- the budget is exhausted;
- the success bar is met;
- the plateau playbook is exhausted;
- a lock integrity check fails;
- something outside the charter or the host's permissions is needed.

**Confirmation.** The best of N noisy comparisons is biased upward. Before declaring a
winner:
1. Rerun the top 2–3 candidates with **new seeds** (and a different fold or time window
   if available).
2. Choose by the confirmation results, preferring the simpler one on ties.
3. Score the **holdout once**: `python scripts/labbook.py holdout --metric X`. The lab
   book refuses a second scoring unless it is forced with a stated reason. Report the
   holdout number as the expected performance, with a CI:
   `python scripts/eval_report.py --preds holdout_preds.csv --y-true y --y-score score`.

## 10. Long-running jobs

- For runs over ~2 minutes, use background execution with a timeout if your environment
  supports it. Otherwise run with a hard timeout. Don't sit polling.
- The lab book is the memory. After a context reset or restart, `labbook.py state`
  restores everything needed.
- **Never stop processes you didn't start** (no `taskkill /IM python.exe` or
  `pkill python`). Other jobs may share the machine; stop only your own PIDs.
- **Parallelism** (optional): run independent ideas in separate worktrees. Only one
  orchestrator writes to the lab book.
- Keep it cheap: screen ideas on samples, confirm at full scale, and watch compute and
  warehouse costs.

## 11. Final deliverable

1. `python scripts/labbook.py report > experiment_report.md` gives the improvement path,
   all runs and ideas.
2. Put a short executive summary on top (about a page, conclusion first):
   - the best model versus the baseline, with the **holdout** number and CI;
   - what drove the gains (confirmed by ablation where possible);
   - what didn't work;
   - the practical ceiling and what would move it;
   - next steps.
3. Keep numbers identical across the summary, report, and logs. Include every script you
   reference.
4. Leave the work on the experiment branch or worktree for the user to review and merge.
   Don't merge into their main branch unless they ask.
5. If the model will ship, add a model card and a monitoring plan.
