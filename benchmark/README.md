# Benchmark kit

Everything needed to re-run the benchmark described in [../BENCHMARK.md](../BENCHMARK.md)
on any agent.

| File | What it is |
|---|---|
| `evals.json` | 7 task prompts plus the stricter round-2 assertions |
| `fixtures/customers.csv` | Input for eval 6: a synthetic CRM extract with 12 planted defects |
| `fixtures/build_fraud.py` | Builds the eval-4 sandbox repo: seeded data, `train.py`, `features.py`, locked `evaluate.py` |
| `fixtures/build_nrr.py` | Builds the eval-5 data extract (accounts, MRR, usage, change log) and prints its answer key |
| `fixtures/grade_fraud.py` | Objective eval-4 checks: evaluator unchanged, leak unused, true PR-AUC and latency re-measured |
| `SPOILERS.md` | Answer keys for evals 2, 4, 5 and 6 |
| `round1_results.json`, `round2_results.json` | Per-run grades, tokens and durations from the published runs |

## Reproducing a run

1. **Build the inputs** (needs `pip install -r ../requirements-dev.txt`):
   ```bash
   python fixtures/build_fraud.py generated/fraud && (cd generated/fraud && git init -q && git add -A && git commit -qm baseline)
   python fixtures/build_nrr.py   generated/nrr
   ```
2. **For each task and configuration,** create a fresh run directory containing only
   the task inputs, copied as `project/`. Give the agent the prompt from `evals.json`, and
   configure the skill under test the way your harness installs skills. **Never let the
   agent see `benchmark/`**; it contains the answer keys.
3. **Isolate runs.** Give each its own scratch directory, and don't run them on a machine
   where one agent can kill another's processes.
4. **Grade blind.** Anonymize the outputs (e.g. letters A–F), grade every assertion
   pass/fail with evidence, re-run candidate scripts, and spot-check the quoted numbers
   against the data. For eval 4, first run `fixtures/grade_fraud.py` and give its JSON to
   the grader as ground truth.

The published results used Claude Code sub-agents both as the agents under test and as
graders. Results with other models or agents, and with independent human or cross-model
graders, would strengthen them considerably.
