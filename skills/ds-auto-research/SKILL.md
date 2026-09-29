---
name: ds-auto-research
description: >
  Autonomous, hypothesis-driven investigation of an open business or data question, end
  to end: pin down the exact fact to explain, build a MECE issue tree (measurement
  artifacts first), write falsifiable predictions before querying, test the cheapest
  discriminating evidence, attribute the change by driver with a bridge that reconciles to
  the total, red-team the leading story, and deliver a conclusion-first report with
  confidence levels and what was ruled out. Use when asked to investigate or "auto-research"
  questions like "why did NRR / churn / revenue drop?", "what drives expansion?", "where
  are we losing margin?", or "research the best approach to X". Not for quick metric
  lookups or for optimizing a model metric.
license: MIT
compatibility: Works in any Agent Skills-compatible agent. Needs read access to the data (files or a warehouse). Bundled lab-book script needs Python 3.9+.
metadata:
  author: Sreedhar Reddy Arolla
  version: "1.1.0"
---

# Auto-Research: autonomous, hypothesis-driven investigation

Auto-Research answers open-ended questions end to end, with minimal human input. It works
like a disciplined analyst:
- decompose the question;
- state falsifiable hypotheses;
- run the cheapest tests that tell them apart;
- keep score;
- try to refute the leading story;
- report what is explained and what isn't.

**Host rules come first.** The charter below sets what you may do without asking the
user. It never overrides the host agent's approval prompts, permissions, sandbox, network
access, or cost limits. This workflow is **read-only on data**: it queries and analyzes,
and never writes to production systems or contacts people.

## Contents
1. Charter
2. Orient: pin down the fact to explain
3. Build the issue tree
4. Write falsifiable hypotheses
5. The loop
6. Red-team the leading explanation
7. Method and literature research
8. Evidence standards
9. Stopping and handoffs
10. Final report

---

## 1. Charter

Agree on these once, in a single batch of questions, each with a default
(`assets/program_template.md`, research section):
- the question and the decision it feeds
- the deliverable and its deadline
- the budget: hours, number of queries, warehouse scan cost
- the data in scope and your access to it
- what's off-limits (PII, production systems, contacting people)

Then run autonomously. Ask only for things outside the charter, or facts nobody could
find in the data (e.g. "was there a pricing change in June?"). Batch those questions, and
keep working on other branches while you wait.

Initialize the lab book (the state file that survives context resets):
```bash
python scripts/labbook.py init --mode research \
  --objective "Explain the +1.8pp rise in SMB monthly churn (Jul–Sep 2026)" \
  --metric explained_share --direction max --budget-hours 6 --patience 8
```

## 2. Orient: pin down the fact to explain

Most wasted investigations explain something that isn't quite what happened.
- **Reconcile** the metric to a trusted source (finance, the official dashboard, the
  system of record). Recompute it from the data and explain any gap.
- **Size it:** compare it with normal variation (the same period last year, the forecast
  band, a control group). If it's inside the noise, say so, and stop unless the user
  still wants more.
- **Timing:** is the onset sudden or gradual, on which date, and does it persist?
- **Location:** a first-pass decomposition by the main dimensions. Is it concentrated or
  broad?
- **Load data carefully:** literal codes like `NA` (North America) are read as null by
  default in pandas and R. Load categorical codes with `keep_default_na=False`.

Write the result as one sentence, e.g. *"SMB churn rose from 3.1% to 4.9% starting the
week of Jul 7; 70% of the increase is in monthly-billed plans; enterprise is flat."*
That sentence is what the rest must explain.

## 3. Build the issue tree

Decompose the question into branches that are **mutually exclusive and collectively
exhaustive** (MECE). **Always make "measurement artifact" the first branch.** Tracking
changes, definition changes, pipeline bugs, backfills, and currency or unit conversions
explain a surprising share of "real" movements, and they're cheap to check.

Typical top-level splits:
- **Measurement** (the number changed, reality didn't) versus a **real change**
- **Mix** (the composition shifted) versus **rate** (behavior within segments changed)
- **Internal** (pricing, product, operations, marketing, sales) versus **external**
  (seasonality, competitors, macro)
- **Metric identities:** revenue = customers × conversion × orders × AOV;
  NRR = expansion − contraction − churn over the starting base.

## 4. Write falsifiable hypotheses

For every leaf worth testing, record:
- **Hypothesis:** "The June 30 price increase on monthly plans drove the churn rise."
- **Prediction (if true, we'd see…):** "the rise is concentrated in repriced plans; onset
  follows the first renewal at the new price; annual (price-protected) plans are flat."
- **Test:** the cheapest query that could prove the prediction **false**.
- **Prior** and **impact** (high/med/low).

```bash
python scripts/labbook.py hyp add "June 30 monthly-plan price increase drove SMB churn" \
  --prediction "rise concentrated in repriced plans; onset after first renewal; annual flat" \
  --test "churn by plan x billing cycle x renewal cohort, Jun–Sep" --prior high --impact high
```

**Write the prediction before looking at the data.** Predictions written after the fact
always fit.

## 5. The loop

Repeat until a stop condition is hit:
1. `python scripts/labbook.py state` lists the open hypotheses ranked by prior × impact,
   plus the supported ones, notes, and budget.
2. **Pick** the best value for its cost. Cheap tests that eliminate whole branches come
   first.
3. **Run the test.** Save the query, and push the aggregation down to the warehouse.
4. **Resolve it with numbers:** `python scripts/labbook.py hyp resolve h003 --verdict
   supported --evidence "repriced +3.9pp vs +0.2pp; onset wk of Jul 7; annual flat;
   q_churn_by_plan.sql"`. "Inconclusive" is a valid verdict, but say what would settle it.
5. **Drill down.** A supported hypothesis spawns children (`--parent h003`). A refuted
   one closes its branch.
6. **Every ~5 resolutions,** write a synthesis note with the **explained share** so far.

**Too-regular patterns are data questions first.** Many accounts changing by exactly the
same ratio (e.g. every downgrade is precisely ×0.75), identical steps on one date, or
round-number clusters are rarely customer behavior. They usually point to a system rule,
a pipeline change, or a billing defect. Flag them for verification with the system owner
(billing, finance, data engineering), and state both readings before attributing them to
customers.

**Attribute by driver, not by segment.** "Segment X's NRR fell 22pp" is not the effect
of event X. That segment line also contains the segment's normal behavior and any other
drivers acting on it. Build the bridge from counterfactuals: recompute the metric with
each driver's effect removed (e.g., accounts that churned because of X restored, or FX
held constant). When drivers overlap, use Shapley averaging over removal orders, or report
the interaction. **The drivers plus the residual must equal the total change.**

## 6. Red-team the leading explanation

Spend about 15–20% of the budget trying to **break** your best story:
- **Timing:** did the cause precede the effect, at the right lag?
- **Placebo:** does the "cause" predict effects where it shouldn't (unexposed segments,
  earlier periods, placebo dates)?
- **Dose-response:** does a bigger exposure bring a bigger effect?
- **Replication:** does it hold in another period, region, or sample?
- **Rival explanations:** what else changed then? Check release and change logs.
- **Confounding:** do the exposed units differ in ways that matter anyway?

If the story survives, confidence rises. If it cracks, update the tree.

## 7. Method and literature research

Use this for "what's the best approach to X?", or when an investigation is stuck:
- Search papers, official docs, and reputable practitioner write-ups. Prefer sources that
  are reproducible, recent, and from a similar data regime.
- For each method, record the claim, the evidence strength, its fit to your constraints
  (data size, latency, interpretability, skills), and the cost to try.
- Summarize in your own words and cite. Don't paste long passages.
- Finish with a comparison table and a recommendation: *"Try X first because…; Y only
  if…; skip Z because…"*

## 8. Evidence standards

- **Every verdict cites numbers and a reproducible artifact** (the query text, a
  notebook cell, a file). Ship the scripts or queries behind every number you quote.
- **Count your cuts.** Slice 40 ways and about two will look significant by chance. A
  striking segment you found by searching is a hypothesis to replicate, not a finding.
- **Match your language to the evidence:**

  | Evidence | Say |
  |---|---|
  | Randomized experiment | "X **caused** …" |
  | Strong quasi-experiment, checks passed | "Our best estimate is that X **increased** Y by …, assuming …" |
  | Adjusted observational comparison | "X is **associated with** …; unmeasured factors could explain part" |
  | Raw correlation or trend | "Y was higher when X was present; we **can't yet say** whether X drove it" |

  Most investigations end at "associated with" or "most consistent with". That's fine
  if you say so, and headlines must follow the same rule.
- **Report what you ruled out,** with evidence. It's half the value.

## 9. Stopping and handoffs

**Stop** when any of these happens:
- about 80% or more of the effect is explained by hypotheses that survived red-teaming;
- the budget is exhausted;
- the remaining branches can't be tested with the available data (list what's needed);
- the effect is noise or a measurement artifact.

**Hand off** when:
- a metric to optimize emerges (a model-improvement loop such as `ds-experiment-mode`);
- a decision needs causal certainty (an A/B test);
- an intervention hit some units and not others (a quasi-experimental design such as DiD
  or synthetic control).

## 10. Final report

Keep the reply about a page, conclusion first. Put the detail in attached files, and keep
every number consistent across the reply, report, and logs.

```markdown
## [Conclusion headline — no more causal than the evidence]
**Answer:** … **Confidence:** … **Recommended action:** …

### What explains the change
| Driver | Contribution | Evidence | Confidence |
|---|---|---|---|
| Price change on monthly plans | ~1.2pp of 1.8pp | concentrated in repriced plans, onset at first renewal, dose-response | High |
| Mix shift toward monthly plans | ~0.2pp | segment share +6pp | Medium |
| Unexplained | ~0.4pp | — | — |

### Ruled out
- Tracking change (verified against billing), seasonality (flat last year), …

### Questions for the business (each with the default you assumed)
### Next steps (owner, date)
### Appendix: hypothesis log (`labbook.py report`), queries, assumptions
```
