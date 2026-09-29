# Auto-Research Mode: autonomous, hypothesis-driven investigation

Auto-Research Mode answers open-ended questions end to end, with minimal human input:
"why did churn rise in Q3?", "what drives enterprise expansion?", "where are we losing
margin?", "is there an opportunity in segment X?", "what's the best approach to
forecasting our long-tail SKUs?". It works like a disciplined analyst: decompose the
question, state falsifiable hypotheses, run the cheapest tests that tell them apart, keep
score, try to refute the leading story, and report what is explained and what isn't.

## Contents
1. Charter
2. Orient: pin down the fact to explain
3. Build the issue tree
4. Write falsifiable hypotheses
5. The loop
6. Red-team the leading explanation
7. Method and literature research
8. Evidence standards and the garden of forking paths
9. Stopping and handoffs
10. Final report

---

## 1. Charter

Agree on these once, in a few lines (`assets/program_template.md`, research section):
- the question and the decision it feeds
- the deliverable
- the budget: hours, number of queries, warehouse scan cost
- the data in scope, and the access you have
- what is off-limits (PII, production systems, contacting people)

Then run autonomously. Ask the human only for things outside the charter, or for facts
nobody could find in the data, such as "was there a pricing change in June?". Batch
those questions and keep working on other branches while you wait.

Initialize the lab book:
```bash
python scripts/labbook.py init --mode research --objective "Explain the +1.8pp rise in SMB monthly churn (Jul–Sep 2026)" \
  --metric explained_share --direction max --budget-hours 6 --patience 8
```

## 2. Orient: pin down the fact to explain

Before generating hypotheses, establish the phenomenon precisely. Most wasted
investigations explain something that isn't quite what happened.
- **Reconcile** the metric to the trusted source (SKILL.md principle 2).
- **Measure it:** how large is it versus normal variation (the same period last year, the
  forecast band, a control group)? If it is inside the noise band, report that. Stop
  unless the user still wants a deeper look.
- **Timing:** is the onset sudden or gradual, on which date, and does it persist?
- **Location:** a first-pass decomposition by the main dimensions (segment, region,
  channel, product, platform, cohort). Is the change concentrated or broad?

Write the result as one sentence: *"SMB churn rose from 3.1% to 4.9% starting the week
of Jul 7; 70% of the increase is in monthly-billed plans; enterprise is flat."* That
sentence is what the rest of the investigation must explain.

## 3. Build the issue tree

Break the question down into branches that are **mutually exclusive and collectively
exhaustive** (MECE), so that you don't miss a cause and don't double-count one.
**Always make "measurement artifact" the first branch.** Tracking changes, definition
changes, pipeline bugs, and backfills explain a surprising share of "real" movements, and
they are cheap to check.

Typical top-level splits:
- **Measurement** (the number changed but reality didn't) versus **real change**
- **Mix** (the composition of the population changed) versus **rate** (behavior changed within segments)
- **Internal** causes (pricing, product, operations, marketing, sales) versus
  **external** ones (seasonality, competitors, macro, regulation)
- **Metric identity decompositions:** revenue = customers × conversion × orders per
  customer × average order value; churn = the sum over cohorts of share × cohort churn.

## 4. Write falsifiable hypotheses

For every leaf worth testing, record:
- **Hypothesis:** "The June 30 price increase on monthly plans drove the churn rise."
- **Prediction (if true, we would see…):** "the increase is concentrated in plans that got
  the price change; onset right after the first renewal at the new price; price-related
  cancellation reasons up; annual plans (price-protected) flat."
- **Test:** the cheapest query or analysis that could show the prediction is **false**.
- **Prior:** how plausible it is, given what you know (high/med/low).
- **Impact:** how much of the effect it could explain if true (high/med/low).

```bash
python scripts/labbook.py hyp add "June 30 monthly-plan price increase drove SMB churn" \
  --prediction "rise concentrated in repriced plans; onset after first renewal at new price; annual flat" \
  --test "churn by plan x billing cycle x renewal-date cohort, Jun–Sep" --prior high --impact high
```

**Write the prediction before looking at the data.** Predictions written after the fact
always fit.

## 5. The loop

Repeat until a stop condition is hit:
1. `python scripts/labbook.py state` shows the open hypotheses ranked by prior × impact,
   the supported ones, the notes, and the budget.
2. **Pick** the hypothesis with the best value for its cost. Cheap tests that can
   eliminate whole branches come first, which is why measurement artifacts go first.
3. **Run the test.** Save the query or notebook cell, and push the aggregation down to the
   warehouse.
4. **Resolve it with numbers:**
   `labbook.py hyp resolve h003 --verdict supported --evidence "repriced plans +3.9pp vs +0.2pp non-repriced; onset wk of Jul 7 (first renewals); annual flat; q_churn_by_plan.sql"`.
   "Inconclusive" is a legitimate verdict, but say what data would settle it.
5. **Drill down.** A supported hypothesis spawns child hypotheses (`--parent h003`), such
   as "which customers within repriced plans?" or "is it price itself, or the billing
   email that announced it?". A refuted one closes its whole branch.
6. **Every ~5 resolutions,** write a synthesis note giving the **explained share** so
   far. For example: "the price change explains about 1.2pp of the 1.8pp; mix shift
   explains about 0.2pp; 0.4pp is unexplained". Keep the decomposition additive, so the
   parts sum to the total.

   **Too-regular patterns are data questions first.** Many accounts changing by exactly
   the same ratio (e.g. every downgrade is precisely ×0.75), identical step changes on
   one date, or round-number clusters are rarely customer behavior. They usually come
   from a system rule, a pipeline change, or a billing defect. Flag them for
   verification with the system owner (billing, finance, data engineering) and state
   both readings, before attributing them to customers.

   **Attribute by driver, not by segment.** "The Acme segment's NRR fell 22pp" is not
   the effect of the Acme migration. That segment line also contains the segment's
   normal expansion and any other drivers acting on it (e.g. Acme accounts on the
   repriced plan). Build the bridge from counterfactuals: recompute the metric with
   each driver's effect removed (for example, churned-because-of-X accounts restored,
   or FX held constant). When drivers overlap, use Shapley averaging over removal orders
   or report the interaction explicitly. Then reconcile: the drivers plus the residual
   must equal the total change.

## 6. Red-team the leading explanation

Before reporting, spend a real share of the budget (around 15–20%) trying to **break** your
best story:
- **Timing:** did the cause happen before the effect, at the right lag?
- **Placebo:** does the "cause" predict effects where it shouldn't (unexposed segments,
  earlier periods, a placebo date)?
- **Dose-response:** do bigger price increases go with more churn?
- **Replication:** does the finding hold in a different period, region, or sample?
- **Rival explanations:** what else changed at the same time (a launch, a competitor
  move, a support backlog)? Check the release and change logs.
- **Confounding:** are the exposed segments different in ways that matter anyway?

If the story survives, the confidence goes up. If it cracks, update the tree.

## 7. Method and literature research

Use this when the question is "what is the best approach to X?", or when an experiment or
investigation is stuck:
- Search papers, official library documentation, and well-regarded practitioner
  write-ups. Prefer sources that are reproducible, recent, and in a similar data regime
  (similar scale, similar noise, tabular versus unstructured).
- For each candidate method, record the claim, the evidence strength, the fit to our
  constraints (data size, latency, interpretability, team skills), and the cost to try.
- Turn the results into lab-book **ideas** (for Experiment Mode) or **hypotheses**, with
  `--source`. Summarize in your own words and cite; don't paste long passages.
- Produce a short comparison table and a recommendation: *"Try X first because…; Y only
  if…; skip Z because it needs labels we don't have."*

## 8. Evidence standards and the garden of forking paths

- **Every verdict cites numbers and a reproducible artifact** (the query text, a notebook
  cell, a file).
- **Count your cuts.** If you sliced the data 40 ways, about two cuts will look
  "significant" by chance. A striking segment you found by searching is a hypothesis to
  replicate, not a finding.
- **Match your language to the evidence** (see the language ladder in
  `experimentation-and-causal.md`). Most investigations end at "associated with" or "most
  consistent with", and that's fine if you say so.
- **Report what you ruled out.** It is half the value, and it stops the same questions
  from being re-investigated.

## 9. Stopping and handoffs

**Stop** when any of these happens:
- about 80% or more of the effect is explained by supported hypotheses that survived red-teaming
- the budget is exhausted
- the remaining branches can't be tested with the available data (list what would be needed)
- the effect turns out to be noise or a measurement artifact.

Hand off to other workflows as needed:
- to **Experiment Mode**, when the research exposes a metric to optimize (e.g., "build a
  better churn model to target the save offer")
- to an **A/B test** (`experimentation-and-causal.md`), when a decision needs causal
  certainty that observational data can't give
- to a **causal design** (DiD, synthetic control), when an intervention hit some units and
  not others.

## 10. Final report

Build it with `labbook.py report` plus an executive summary (`communication.md`):

```markdown
## [Conclusion headline]
**Answer:** … **Confidence:** … **Recommended action:** …

### What explains the change
| Driver | Share of Δ | Evidence | Confidence |
|---|---|---|---|
| Price change on monthly plans | ~1.2pp of 1.8pp | concentrated in repriced plans, onset at first renewal, dose-response | High |
| Mix shift toward monthly plans | ~0.2pp | segment share +6pp | Medium |
| Unexplained | ~0.4pp | — | — |

### Ruled out
- Tracking change (verified against billing system), seasonality (flat LY), support backlog (no correlation by account)

### Open questions & what would resolve them
### Next steps (owner, date)
### Appendix: hypothesis log, queries, assumptions
```
