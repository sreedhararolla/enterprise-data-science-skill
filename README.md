# Enterprise Data Science Skills

[![tests](https://github.com/sreedhararolla/enterprise-data-science-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/sreedhararolla/enterprise-data-science-skill/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Three [Agent Skills](https://agentskills.io) that make an AI agent work like a senior
enterprise data scientist. With them, the agent asks the right questions before building,
reconciles data before trusting it, validates models the way they'll be deployed, makes
causal claims honestly, and runs long autonomous work under guardrails.

They use the open **Agent Skills** format (`SKILL.md` plus scripts, references and
assets). That works in Claude Code, OpenAI Codex, Gemini CLI, GitHub Copilot / VS Code,
Cursor, OpenCode, Goose, Amp, Roo Code, Kiro, Databricks, Snowflake Cortex Code, and
[other compatible agents](https://agentskills.io/clients). Agents without native support
can still use them; see [below](#other-agents-and-plain-llm-apps).

| Skill | Use it for | Activates on requests like |
|---|---|---|
| [`enterprise-data-science`](skills/enterprise-data-science/SKILL.md) | Core playbook: intake questions, EDA and data-quality audits, leakage-proof validation, evaluation, A/B tests, causal inference, metric movements, production and governance | "build a churn model", "is this lift real?", "do an EDA on this extract", "did the program cause the increase?" |
| [`ds-experiment-mode`](skills/ds-experiment-mode/SKILL.md) | A guarded autonomous optimization loop for one metric: locked evaluator and holdout, noise-aware keep/revert in an isolated git worktree, guardrails, budgets | "push PR-AUC as high as you can overnight", "keep iterating until it stops improving" |
| [`ds-auto-research`](skills/ds-auto-research/SKILL.md) | An autonomous, hypothesis-driven investigation: issue tree, falsifiable predictions, driver attribution that reconciles to the total, red-teaming | "auto-research why NRR fell", "investigate end to end what drove the churn increase" |

**Evidence.** In a blind benchmark (7 tasks, 2 runs per setup, 42 outputs), an **earlier
v3 snapshot** of the core skill had the best mean score on all 7 tasks. It was compared
against the same agent with no skill and against one public comparator skill selected by
the author. Grading was done by a separate Claude-family grading agent. The current
versions haven't been re-benchmarked yet. Read [BENCHMARK.md](BENCHMARK.md) for the
method and limitations before relying on these numbers.

---

## Installation

```bash
git clone https://github.com/sreedhararolla/enterprise-data-science-skill.git
pip install -r enterprise-data-science-skill/requirements.txt   # pandas, numpy, scipy for the bundled scripts
```

Each skill is a folder under `skills/`. Copy the ones you want to wherever your agent
looks for skills. Keep the folder names unchanged, because each must match the `name` in
its SKILL.md. The two autonomous skills work alone, but they're designed to be installed
alongside the core skill.

**Cross-agent convention (when supported).**
```bash
mkdir -p .agents/skills && cp -r enterprise-data-science-skill/skills/* .agents/skills/
```

**Agent-specific locations.** Paths change between versions, so check your agent's docs:

| Agent | Where skills go | Docs |
|---|---|---|
| Claude Code | `~/.claude/skills/` (user) or `.claude/skills/` (project) | [docs](https://code.claude.com/docs/en/skills) |
| Claude apps (web/desktop) | Zip each skill folder and upload it in Settings → Capabilities → Skills | [docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) |
| OpenAI Codex | Codex skills directory | [docs](https://developers.openai.com/codex/skills/) |
| Gemini CLI | Gemini CLI skills directory | [docs](https://geminicli.com/docs/cli/skills/) |
| GitHub Copilot / VS Code | Copilot agent skills location | [docs](https://code.visualstudio.com/docs/copilot/customization/agent-skills) |
| Cursor | Cursor skills location | [docs](https://cursor.com/docs/context/skills) |
| OpenCode | OpenCode skills directory | [docs](https://opencode.ai/docs/skills/) |
| Others | See each tool's page | [client list](https://agentskills.io/clients) |

At startup the agent loads only each skill's name and description. It reads the full
instructions when a request matches, or when you invoke a skill by name.

### Other agents and plain LLM apps

1. Put the `skills/` folder somewhere your agent can read, such as your repo.
2. Add a pointer to your agent's instruction file (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`,
   `.cursorrules`, `.github/copilot-instructions.md`, or a system prompt):

   ```markdown
   For data science, ML, analytics, experiment or causal-inference work, read
   `skills/enterprise-data-science/SKILL.md` and follow it. For an autonomous
   model-improvement loop, read `skills/ds-experiment-mode/SKILL.md`. For an end-to-end
   "why did this metric change" investigation, read `skills/ds-auto-research/SKILL.md`.
   Load files from each skill's `references/` folder when it tells you to, and use its
   `scripts/`.
   ```

3. For chat apps without file access, paste the relevant SKILL.md, plus the reference
   file for your task, into the system prompt or project instructions. The scripts need a
   code-execution environment.

## Safety by design

- **The host's rules come first.** A skill's charter never overrides the agent's approval
  prompts, permission settings, sandbox, network or cost limits.
- **Git undo is always recoverable.** The skills work in an isolated worktree, commit
  every candidate, and undo with `git revert`. They never use `reset --hard`, `clean -f`
  or force-push. The tests enforce this.
- **The autonomous loop can't game its metric.** The evaluator, splits and holdout are
  fingerprinted, and the holdout can be scored only once.
- **Data handling:** the bundled scripts make no network calls. How the agent itself
  handles your data depends on its runtime and deployment, so review its privacy and
  retention settings before sharing sensitive data. The skills also tell the agent to
  minimize PII and keep it out of outputs and prompts.
- **Processes:** the agent is told never to kill processes it didn't start.

## Bundled scripts

Standalone Python 3.9+ scripts, tested on pandas 2.2 and 3.0. Each prints Markdown.

| Script | In skill | What it does |
|---|---|---|
| `profile_data.py` | core | Severity-ranked data profile: PII, duplicate keys, sentinels, the `NA` = North America trap, numbers or dates stored as text, category variants, missingness that predicts the target |
| `leakage_scan.py` | core, experiment | Out-of-fold univariate power per feature; flags ID-like columns, missingness leaks, and power that jumps in later periods |
| `eval_report.py` | core, experiment | Metrics with bootstrap CIs versus a baseline, tie-aware PR-AUC, calibration, thresholds from cost or capacity, per-slice metrics |
| `experiment.py` | core | A/B test power, MDE, sample-ratio-mismatch check, lift with CIs |
| `drift_check.py` | core | PSI and KS drift per feature between reference and current data |
| `labbook.py` | experiment, research | Persistent state for autonomous runs: locks, keep/discard rules, guardrails, budgets, a one-time holdout, hypotheses |

```bash
cd skills/enterprise-data-science
python scripts/profile_data.py --data customers.csv --key customer_id --target churned
python scripts/experiment.py srm --counts 48210 50944
python scripts/eval_report.py --preds preds.csv --y-true y --y-score score --capacity 500
```

Run any script with `--help` for its options.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest -q tests
```

The test suite (53 tests) checks that:
- every planted data defect is detected;
- PR-AUC matches scikit-learn on tie-heavy data;
- the A/B test math matches textbook values;
- the lab book's lifecycle works (including tamper detection and the one-time holdout);
- every skill follows the Agent Skills spec;
- shared script copies are identical;
- no file recommends destructive git commands.

CI runs on Python 3.9–3.13 with pandas 2.x and 3.x, on Linux, Windows and macOS.

`benchmark/` contains benchmark fixtures, task definitions, grading materials, and the
published results. You supply your own agent harness to run the tasks, and most of the
grading is manual or done by a grading agent. See [benchmark/README.md](benchmark/README.md).

## Contributing

Issues and pull requests are welcome, especially:
- benchmark results on other agents and models;
- new reference material (forecasting depth, recommender systems, LLM evaluation);
- install notes for more harnesses.

Keep each SKILL.md under 500 lines, and make sure `pytest` passes.

## License

[MIT](LICENSE) © 2026 Sreedhar Reddy Arolla
