# Production, monitoring, and governance

## Contents
1. Production readiness
2. Monitoring
3. Retraining and rollback
4. Documentation: the model card
5. Governance: privacy, fairness, model risk
6. Regulatory context (orientation, not legal advice)

---

## 1. Production readiness

Before handing a model to ML engineering or deploying it yourself, check that:

- **Packaging:** the model and preprocessing live in a single serialized pipeline, with a
  versioned artifact in a model registry (MLflow, Vertex, SageMaker, Azure ML, Databricks),
  including the training data version, code commit, and metrics.
- **Feature parity:** the serving features are computed by the same code (or feature store
  definitions) as training. Run the training pipeline and the serving path on the same
  entities and dates and diff the results.
- **Input contract:** a schema with types, allowed ranges, and allowed nulls, validated at
  inference (pandera, Great Expectations, or pydantic). Define the behavior for invalid
  inputs: reject, impute, or fall back to a rule.
- **Fallback:** what happens if the model service is down or the inputs are bad? Usually
  the current business rule.
- **Latency and cost:** measured at the p99 under expected load, and within budget.
  Single-row scoring with tree ensembles (e.g. sklearn's HistGradientBoosting) is often
  dominated by thread-pool startup, not by the model. Fix this with public, durable
  mechanisms: limit threads (`threadpoolctl.threadpool_limits(1)` or `OMP_NUM_THREADS=1`
  in the serving process), batch requests, export the model to a portable format
  (ONNX, Treelite), or use a verified NumPy tree export with a test that asserts score
  equivalence. **Do not depend on private APIs** (anything starting with `_`), and never
  add a silent fallback to a path that breaks the latency budget. Private methods change
  without notice, and the fallback turns a library upgrade into a production incident.
- **Shadow or canary first:** score in shadow mode alongside the current process, compare
  the decisions, then ramp up gradually. For decisions that affect customers, measure the
  real impact with an A/B test or holdout.
- **Access and security:** least-privilege service accounts, no PII in logs, and
  credentials kept in a secret manager.

## 2. Monitoring

Monitor four layers, each with an owner and an alert threshold:

| Layer | What | Typical signal |
|---|---|---|
| **Data quality** | Nulls, schema changes, volume, freshness | Null rate > 2× baseline; row count ±30%; a late partition |
| **Input drift** | Feature distributions versus training | PSI > 0.2 (major), 0.1–0.2 (watch); KS p-values are overly sensitive at large n, so rely on effect sizes |
| **Prediction drift** | Score distribution, positive rate | Mean score or flag rate shifts beyond the band |
| **Performance** | Actual metric, once labels arrive | Metric below the agreed floor for two consecutive periods |

- Labels often arrive late (churn is known only after 60 days). Use the drift layers as
  early warnings, and measure performance on cohorts once their labels mature.
- `scripts/drift_check.py --reference train.parquet --current last_week.parquet`
  produces a PSI and KS table per feature.
- Keep a **holdout group** (e.g., 5% scored but not acted upon, or handled by the old
  process) where it is ethical and practical. It is the only clean way to measure ongoing
  value and to avoid feedback loops.
- **Feedback loops:** if the model's actions change the labels (fraud blocked means no
  fraud label; offered customers don't churn), then naive retraining learns the policy,
  not the world. Use the holdouts, or log the propensities.

## 3. Retraining and rollback

- **Trigger:** on a schedule (monthly or quarterly), on drift or performance alerts, or
  both. Document which one you use.
- **Champion/challenger:** a retrained model must beat the current one on the same recent
  holdout before promotion. Automated retraining without this gate can silently ship
  something worse.
- **Rollback:** a one-step revert to the previous registry version. Test it.
- **Decommission:** define when to retire the model (the business process changes, value
  falls below its running cost).

## 4. Documentation: the model card

Every production model gets a model card (`assets/model_card_template.md`) that covers
its intended use and its out-of-scope uses, training data and time window, features, the
evaluation (including slices and fairness), limitations, the monitoring plan, the owner,
and the review date. Write it for a reader who has never met you, such as an auditor or
your successor.

## 5. Governance: privacy, fairness, model risk

**Privacy and data minimization**
- Use only the data needed for the purpose, and confirm that the purpose is compatible
  with why the data was collected (consent, terms, or internal policy).
- Pseudonymize identifiers in modeling tables. Keep the re-identification key in a
  separate, access-controlled location.
- Aggregate outputs to minimum group sizes (e.g., k ≥ 10) before sharing. Small cells can
  re-identify people.
- Don't paste raw customer records into external tools or LLM prompts unless your
  organization has approved that.
- Honor deletion and retention rules. Know whether a deletion request requires retraining.

**Fairness**
- Decide whether protected attributes may be used for **testing** (usually yes, and it is
  often necessary) versus as **features** (usually no, in regulated decisions). Get this
  decision from legal or compliance, and document it.
- Test outcomes across groups (see `evaluation.md` §5), look for proxies, and record the
  chosen fairness metric and the rationale.

**Model risk management**
- Tier models by impact: a marketing propensity model is low risk, while credit, pricing,
  hiring, medical, or safety models are high risk. Scale documentation, independent
  validation, and approval to the tier.
- For high-tier models, have someone independent of the builder validate them
  (conceptual soundness, data, outcome analysis, ongoing monitoring). This is the core of
  frameworks like the US Federal Reserve/OCC SR 11-7 guidance for banks.
- Keep an inventory: every production model with its owner, tier, last validation date,
  and status.

## 6. Regulatory context (orientation, not legal advice)

Regulations vary by jurisdiction and change often. Treat this as a list of what to ask
your legal or compliance team about, not as the answer.

- **GDPR / UK GDPR:** lawful basis, purpose limitation, data minimization, and rights
  concerning solely automated decisions with legal or similarly significant effects.
- **EU AI Act:** a risk-based regime. High-risk uses (e.g., credit scoring, employment,
  essential services) carry requirements on data governance, documentation, human
  oversight, accuracy, and logging. Obligations phase in over time, so check the current
  applicability dates.
- **US lending (ECOA / Reg B, FCRA):** adverse action notices require specific principal
  reasons, and disparate impact matters. Explanations must be accurate for the actual model.
- **Healthcare (HIPAA)** and **financial services (SR 11-7, sector regulators),** plus
  state privacy laws (e.g., CCPA/CPRA) and local rules on automated hiring tools
  (e.g., NYC Local Law 144 bias audits).

When a use case touches one of these areas, flag it early in Phase 0. Retrofitting
compliance after a model is built is expensive and sometimes impossible.
