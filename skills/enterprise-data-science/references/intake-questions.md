# Intake: asking the right clarifying questions

Wrong assumptions made in the first five minutes are the most expensive mistakes in data
science: the wrong target, the wrong grain, the wrong population, or the wrong decision
cost. A few good questions up front prevent days of rework. Asking too many, or asking
things you could look up, wastes the user's time. This protocol balances the two.

## The protocol

1. **Look before you ask.** Read the files, schema, code, and data the user pointed to.
   Never ask something the data or code can answer, such as "what columns are there?" or
   "what's the date range?". Ask about **intent, definitions, decisions, and
   constraints**, which only humans know.
2. **Scale the number of questions to the stakes.**

   | Stakes | Examples | Intake |
   |---|---|---|
   | Low | Quick metric lookup, exploratory chart | 0–1 questions, or state the assumptions inline and proceed |
   | Medium | Analysis for a stakeholder, a one-off model, experiment readout | One round of 3–5 questions |
   | High | Production model, regulated decision, autonomous run, exec-facing causal claim | Full intake: 1–2 rounds, recorded as a brief or charter |

3. **Ask in one batch, not a drip, and keep it small.** Put the questions that would
   change the approach first. **Budget: at most 5 numbered questions and at most 8
   individual asks in total** (count every sub-question). Cut "also useful" extras:
   if something is worth asking, give it a number and a default, otherwise leave it
   out. Don't ask anything your own discovery queries or profiling will answer; say
   you'll check it instead.
4. **Offer a recommended default for every ask, including sub-asks,** with a one-line
   reason, so the user can reply "defaults are fine". Put the default next to the
   question, not in a separate assumptions list. If your environment has a structured question
   tool (such as multiple-choice prompts), use it: 2–4 options per question, with the
   recommended option first.
5. **Explain why a question matters** when that isn't obvious. For example: "When is the
   prediction made? This decides which features are legal; get it wrong and the model
   looks great offline but fails in production."
6. **If the user says "just go",** proceed. Open the deliverable with an **Assumptions**
   block listing every default you chose and its impact if wrong.
7. **Re-ask when the facts change.** If the data contradicts an answer (the numbers don't
   reconcile, the grain isn't what was described, a feature turns out to be
   post-outcome), stop and ask. Don't silently work around it.
8. **For autonomous modes,** ask everything up front: the charter interview is the last
   planned conversation. During the run, ask only about things outside the charter.

## Question bank

Pick the 3–7 most decision-relevant questions for the task. You don't need all of them.

### Any analysis
- What decision will this inform, and who makes it? By when?
- What would change your mind or action? What result would surprise you?
- Which number should this match (the dashboard, finance report, or system of record)?
- Any known data issues, migrations, or definition changes in this period?
- Who is the audience (an exec, a peer data scientist, an auditor)? What format do they need?

### Predictive model
- **Unit and timing:** what is one row, and exactly when is the prediction made? What
  data is available at that moment, and with what delay?
- **Target and horizon:** its precise definition, how far ahead to predict (the
  window), and how labels are produced. Is there a known noise rate? Ask about the
  horizon explicitly; don't bury it in a default.
- **Action:** what happens to a high score (an outreach, a block, a review)? Is capacity
  limited (e.g., "500 reviews a day")?
- **Error costs:** a false positive costs [$ / harm], and a false negative costs [$ / harm].
- **Baseline:** what does the business do today (a rule, a manual process, nothing)?
- **Constraints:** batch or real-time, latency, explainability requirements, off-limits
  features, regulatory context.
- **Deployment:** who runs it, how often it is scored, and how outcomes feed back.

### Experiment / A/B test
- The hypothesis, and the single primary metric. Which guardrails must not degrade?
- The unit of randomization. Could users influence each other (teams, a marketplace,
  shared inventory)?
- The smallest effect worth shipping (the MDE), and the traffic available per day.
- Has the test already run? If so: was the analysis plan fixed beforehand, was the result
  peeked at, and what are the per-arm counts (for the SRM check)?
- What decision follows a neutral result?

### Causal question without an experiment ("did X cause Y?")
- What exactly was the intervention, when did it start, and who was or wasn't exposed? Why them?
- Did anything else change at the same time?
- Is there a comparison group, a threshold rule, or a staggered rollout? (This determines
  whether DiD, RDD, or synthetic control is possible.)
- How certain does the decision need to be? Would "associated with" be enough, or is a
  test needed?

### Metric movement ("why did X drop?")
- Which exact metric definition and dashboard? Compared with which period?
- Are the size and timing already confirmed, or only noticed?
- What changed recently (launches, pricing, marketing, tracking, pipelines, incidents)?
- Which segments does the business care most about?

### Forecasting
- The horizon, the granularity (daily, weekly; SKU or store), and how the forecast is used
  (inventory, staffing, a budget)?
- Is the cost of over-forecasting symmetric with the cost of under-forecasting? Are
  intervals needed, or only point forecasts?
- Known future events (promotions, price changes, holidays)? Structural breaks in history (e.g., COVID)?
- Must forecasts be consistent across a hierarchy (SKU → category → total)?

### EDA / new dataset
- Which question is this data meant to answer?
- What is the expected grain and key? Is there a target?
- What trusted number should it reconcile to? Are there known quality issues?
- Does it contain personal data, and what handling is approved?

### Autonomous run (Experiment or Auto-Research Mode)
Fill the charter (the `assets/program_template.md` bundled with the `ds-experiment-mode` and `ds-auto-research` skills) through these questions:
- The objective and the success bar ("good enough to stop" is what?)
- The metric, the validation scheme, and the holdout (Experiment Mode), or the precise
  question and decision (Research Mode)
- **Editable** files versus **locked** files
- The time box per run; the total budget (runs, hours, dollars)
- Guardrails (latency, fairness, model size, cost)
- What may be done without asking; what must never be done (production, PII, external
  services, new packages)
- How to report progress: an end-of-run report only, or checkpoints?

## Example intake (medium stakes, churn model)

> Before I build this, a few questions that change the approach. Defaults are in brackets, so
> just say "defaults" if they're fine:
> 1. **When is the prediction made?** [1st of each month, using data through the prior day]. This decides which features are legal.
> 2. **Churn definition and how far ahead to predict?** [no paid subscription within the 30 days after the prediction date]. The horizon sets the label window and the validation gap.
> 3. **What happens to flagged customers, and how many can the team handle?** [CS outreach, ~300/month]. This sets the threshold.
> 4. **Rough cost of a missed churner vs. an unnecessary outreach?** [$1,200 LTV vs. $40]
> 5. **Which number should the customer count match?** [the finance month-end active count]
>
> I've already checked the tables: 24 months of history, ~41k active customers, `churn_date` is populated for 11%.
