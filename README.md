# Enterprise Data Science Skill

An [Agent Skill](https://agentskills.io) that makes your AI agent work like a senior
enterprise data scientist. It asks the right questions before building, reconciles data
before trusting it, validates models the way they will actually be deployed, makes causal
claims honestly, and ships governed, monitored work. It also has two autonomous modes for
problems that need many iterations.

It follows the open **Agent Skills** format (`SKILL.md` plus scripts, references and
assets), so it works in any compatible agent: Claude Code, OpenAI Codex, Gemini CLI,
GitHub Copilot / VS Code, Cursor, OpenCode, Goose, Amp, Roo Code, Kiro, Databricks,
Snowflake Cortex Code, and [many more](https://agentskills.io/clients). Agents without
native skill support can still use it; see [Other agents](#other-agents-and-plain-llm-apps).

In blind benchmarks against the same agent with no skill, and against the strongest public
data-science skill we found, it scored best on **7 of 7 tasks** in both rounds
([benchmark report](BENCHMARK.md)).

---

## What it does

| You ask | What the skill makes the agent do |
|---|---|
| "Build me a churn model" | Ask 3–5 high-leverage questions with defaults (prediction moment, horizon, capacity, error costs), then build with point-in-time features, temporal validation and baselines |
| "My model has 0.97 AUC, help me write it up" | Flag likely leakage, check feature timing, re-validate out of time, and write a decision memo that won't embarrass you |
| "Is this A/B result real?" | Check for sample ratio mismatch, report lift with confidence intervals, check power, and list guardrails before anyone ships |
| "Did the program cause the revenue lift?" | Choose a design (DiD, synthetic control, RDD, IV), state its assumptions, run placebo tests, and use hedged language |
| "Do an EDA on this extract" | Profile it for PII, duplicate keys, sentinels, the `NA` = North America trap, and missingness that leaks the target, then give a fit-for-purpose verdict |
| "Push this model as high as you can overnight" | **Experiment Mode**: a charter, locked evaluator and holdout, noise-aware keep/revert, guardrails, budgets, confirmation re-runs, and one final holdout scoring |
| "Why did NRR drop? Research it end to end" | **Auto-Research Mode**: an issue tree, falsifiable hypotheses, a driver bridge that reconciles to the total, a red-team of the leading story, and a conclusion-first report |

## Repository layout

```
enterprise-data-science/          ← the skill (copy this folder)
├── SKILL.md                      principles, request routing, intake, workflow gates, autonomous modes, red flags
├── references/                   loaded only when relevant
│   ├── intake-questions.md          clarifying-question protocol and question banks for 8 task types
│   ├── eda.md                       enterprise EDA playbook
│   ├── validation-and-leakage.md    temporal/grouped splits, leakage taxonomy, point-in-time features
│   ├── evaluation.md                metric choice, thresholds from cost/capacity, calibration, fairness
│   ├── experimentation-and-causal.md  A/B design, SRM, CUPED, DiD, synthetic control, RDD, IV
│   ├── experiment-mode.md           autonomous optimization loop with guardrails
│   ├── research-mode.md             autonomous hypothesis-driven investigation
│   ├── production-and-governance.md monitoring, retraining, model risk, privacy, regulation
│   ├── communication.md             executive summaries, uncertainty language
│   └── review-checklist.md          pre-delivery QA checklist
├── scripts/                      standalone Python (pandas, numpy, scipy)
│   ├── profile_data.py      data profile with severity-ranked issues
│   ├── leakage_scan.py      out-of-fold univariate power, ID-like columns, missingness and drift flags
│   ├── eval_report.py       metrics with bootstrap CIs vs baseline, calibration, thresholds, slices
│   ├── experiment.py        A/B power, MDE, SRM check, lift with CIs
│   ├── drift_check.py       PSI / KS between reference and current data
│   └── labbook.py           persistent state for autonomous runs: locks, keep/discard, budgets
├── assets/                       analysis brief, model card and autonomous-run charter templates
└── evals/                        7 benchmark prompts with assertions, plus a messy test dataset
```

## Installation

The skill is the `enterprise-data-science/` folder. Install it by putting that folder where
your agent looks for skills. The folder name must stay `enterprise-data-science`, because
it has to match the `name` in SKILL.md.

```bash
git clone https://github.com/sreedhararolla/enterprise-data-science-skill.git
```

**Cross-agent convention (recommended when supported).** Many agents read the shared
`.agents/skills/` directory:

```bash
# per project
mkdir -p .agents/skills && cp -r enterprise-data-science-skill/enterprise-data-science .agents/skills/
```

**Agent-specific locations.** Check your agent's docs for the exact path, since these
change between versions:

| Agent | Where skills go | Docs |
|---|---|---|
| Claude Code | `~/.claude/skills/` (user) or `.claude/skills/` (project) | [docs](https://code.claude.com/docs/en/skills) |
| Claude apps (web/desktop) | Zip the folder and upload it in Settings → Capabilities → Skills | [docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) |
| OpenAI Codex | Codex skills directory | [docs](https://developers.openai.com/codex/skills/) |
| Gemini CLI | Gemini CLI skills directory | [docs](https://geminicli.com/docs/cli/skills/) |
| GitHub Copilot / VS Code | Copilot agent skills location | [docs](https://code.visualstudio.com/docs/copilot/customization/agent-skills) |
| Cursor | Cursor skills location | [docs](https://cursor.com/docs/context/skills) |
| OpenCode | OpenCode skills directory | [docs](https://opencode.ai/docs/skills/) |
| Goose, Amp, Roo Code, Kiro, OpenHands, Databricks, Snowflake, … | See each tool's page | [client list](https://agentskills.io/clients) |

Once installed, the agent loads only the skill's name and description at startup. It reads
the full instructions automatically when a task matches, for example "why did churn go up",
"is this lift real", "do an EDA", or "run experiments overnight". You can also invoke it by
name.

### Other agents and plain LLM apps

If your agent doesn't support Agent Skills natively:

1. Put the `enterprise-data-science/` folder somewhere the agent can read, such as your
   repo.
2. Add a pointer to your agent's instruction file (`AGENTS.md`, `CLAUDE.md`,
   `GEMINI.md`, `.cursorrules`, `.github/copilot-instructions.md`, or a system prompt):

   ```markdown
   For any data science, ML, analytics, experiment or causal-inference task, first read
   `enterprise-data-science/SKILL.md` and follow it. Load files from its `references/`
   folder when it tells you to, and use its `scripts/` for profiling, leakage scans,
   evaluation, A/B math, drift checks and autonomous-run state.
   ```

3. For chat apps without file access, paste `SKILL.md` into the system prompt or a
   project's instructions. Add the most relevant `references/*.md` file for your task
   type, since the chat app can't load them on demand. The scripts need a code-execution
   environment.

## Requirements

- Python 3.9+ with `pandas`, `numpy` and `scipy`. `pyarrow` is optional, for Parquet.
- No network access is needed for the scripts. The skill never asks the agent to send
  your data anywhere.

## Using the scripts directly

Every script runs standalone and prints Markdown you can paste into a report.

```bash
cd enterprise-data-science
python scripts/profile_data.py --data customers.csv --key customer_id --target churned
python scripts/leakage_scan.py --data train.parquet --target is_fraud --time-col txn_time
python scripts/eval_report.py  --preds preds.csv --y-true y --y-score score --capacity 500
python scripts/experiment.py   srm --counts 48210 50944
python scripts/experiment.py   power --baseline 0.041 --mde-rel 0.05
python scripts/drift_check.py  --reference train.parquet --current last_week.parquet
python scripts/labbook.py      init --objective "Maximize PR-AUC" --metric pr_auc --direction max \
                               --lock evaluate.py --holdout data/holdout.parquet --guardrail "latency_ms<=30"
```

Run any script with `--help` for its options.

## Autonomous modes in brief

- **Experiment Mode** runs a propose → run → keep/revert loop against a locked metric, in
  the style of Karpathy's *autoresearch*. It adds:
  - noise-aware keep rules;
  - fingerprinted evaluator and holdout files, so the agent can't "improve" the metric by
    editing the evaluator;
  - guardrails such as latency and fairness limits;
  - run, time and cost budgets;
  - plateau handling;
  - a confirmation re-run;
  - a single final holdout scoring.

  State lives in `labbook.py`, so long runs survive context resets.
- **Auto-Research Mode** answers open questions. It:
  - pins down the precise fact to explain;
  - builds a non-overlapping issue tree, checking for measurement artifacts first;
  - writes falsifiable predictions before querying the data;
  - attributes the change by driver (counterfactual or Shapley), reconciling the drivers
    to the total;
  - red-teams the leading explanation;
  - reports its conclusion first, with confidence levels.

Both modes start from a one-page charter (`assets/program_template.md`) that sets what
the agent may do without asking and what always needs a human.

## Evaluating it yourself

`enterprise-data-science/evals/evals.json` contains the 7 benchmark prompts and their
assertions. `evals/files/customers.csv` is a synthetic CRM extract with 12 planted data
defects. Run the prompts with and without the skill in your own agent and compare. See
[BENCHMARK.md](BENCHMARK.md) for the method and results.

## Contributing

Issues and pull requests are welcome, especially:
- new reference files, such as forecasting depth, recommender systems or LLM evaluation;
- harness-specific install notes;
- new eval prompts with planted answer keys.

Before submitting, keep `SKILL.md` under 500 lines and make sure every script still runs
with `--help`.

## License

[MIT](LICENSE) © 2026 Sreedhar Reddy Arolla
