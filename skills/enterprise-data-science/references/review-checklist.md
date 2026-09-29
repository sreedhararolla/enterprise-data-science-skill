# Review checklist

Use this list before sharing your own work, and when reviewing someone else's. When
reviewing, **lead with the issues that would change the decision**, then the
methodological issues, then style. Say what is good, too, so it survives the next revision.

Mark each item ✅ OK, ⚠️ concern, ❌ blocker, or n/a.

## 1. Framing
- [ ] The decision, the decision owner, and what "success" means are stated
- [ ] The metric matches how the output will be used (see `evaluation.md` §1)
- [ ] The population, time window, and grain are explicit

## 2. Data
- [ ] The base numbers reconcile to a trusted source (or the gap is explained)
- [ ] Row counts are checked before and after joins; keys are unique where assumed
- [ ] Filters and exclusions are listed with the row counts they remove
- [ ] Disguised nulls and sentinel values are handled
- [ ] Definition or tracking changes in the window are checked
- [ ] PII is minimized, and nothing sensitive appears in outputs or charts

## 3. Validation (models)
- [ ] The split mirrors deployment (temporal and/or grouped); there is a gap for the label window
- [ ] All preprocessing is fit inside training folds
- [ ] The holdout was used once, after choices were frozen
- [ ] Every feature is available at prediction time (point-in-time)
- [ ] The leakage scan is clean, or the flagged features are justified
- [ ] Results are not suspiciously good (see the SKILL.md red-flag table)

## 4. Evaluation
- [ ] Trivial baselines and the business-rule baseline are reported
- [ ] Confidence intervals are given on the key metrics and on the model-vs-baseline difference
- [ ] The threshold is chosen from cost or capacity, not 0.5
- [ ] Calibration is checked if the scores are used as probabilities
- [ ] Slice and fairness results are given; small slices are flagged
- [ ] Error analysis has been done; the top drivers make domain sense

## 5. Experiments / causal
- [ ] The primary metric and analysis were pre-registered; there is a power calculation
- [ ] SRM passed
- [ ] The analysis unit matches the randomization unit
- [ ] No peeking, or a sequential method was used
- [ ] Multiple comparisons are handled; segment findings are labeled exploratory
- [ ] The causal language matches the design (see the language ladder)
- [ ] Observational studies state their assumptions and include falsification and sensitivity checks

## 6. Reproducibility
- [ ] Code is in version control; the environment is pinned; seeds are set
- [ ] Queries and data snapshot dates are saved
- [ ] The notebook runs top to bottom from a clean kernel
- [ ] No credentials in the code; parameters are in config

## 7. Communication
- [ ] The headline states the conclusion and the recommendation, and is no more causal or certain than the body
- [ ] Every number, duration, and recommendation is identical across the reply, memos, logs, and charts
- [ ] The reply the user reads fits on about a page; the depth is in attached files and isn't duplicated
- [ ] Every script or file the user is told to use is included in the deliverables
- [ ] Impact is in business units, with a range
- [ ] The confidence level and key caveats are stated
- [ ] What was ruled out is included
- [ ] The assumptions log is attached

## 8. Production (if shipping)
- [ ] There is a model card
- [ ] An input contract and a fallback are defined
- [ ] Train/serve parity is verified
- [ ] A monitoring plan with owners and thresholds exists
- [ ] A retraining gate (champion/challenger) and a tested rollback exist
- [ ] Governance tier and approvals are in place for the risk level

## Review output format

```markdown
**Verdict:** Ready / Ready with fixes / Not ready

**Blockers (would change the decision):**
1. [issue] — [why it matters] — [suggested fix]

**Concerns (should fix):**
1. ...

**Nice to have:**
1. ...

**What's strong:** ...
```
