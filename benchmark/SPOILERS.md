# Answer keys (spoilers)

> **Do not expose this folder to an agent you are benchmarking.** Copy only the generated
> task inputs into the agent's working directory. Keep `benchmark/`, this file and the
> generators outside the agent's reach.

## Eval 2: SRM checkout test
- Control 2,031 / 48,210 = 4.213%, treatment 2,260 / 50,944 = 4.436%, relative lift +5.3%.
- SRM chi-square ≈ 75.4, p ≈ 4e-18 (assuming a 50/50 design). The excess over 50/50 is
  ≈1,367 users per arm.
- Two-sided p for the lift ≈ 0.084. The n needed for a 5% relative MDE is ≈143–146k per arm.

## Eval 4: fraud Experiment Mode (`fixtures/build_fraud.py`, seed 42)
- Baseline (logistic regression on 4 raw features) validation PR-AUC ≈ 0.286. Legitimate
  features plus gradient boosting reach ≈ 0.46–0.48.
- `chargeback_filed` is a post-outcome leak: 85% of fraud rows versus 0.4% of legitimate
  rows. Using it inflates PR-AUC far above any honest ceiling.
- Gradient-boosted models in scikit-learn can exceed the 30 ms p99 guardrail on
  single-row scoring, because of thread-pool startup.
- Locked: `evaluate.py`, `data/valid.parquet`, `data/holdout.parquet`.

## Eval 5: NRR Auto-Research (`fixtures/build_nrr.py`, seed 11)
- Trailing-12m NRR: Mar-2026 = 116.0%, Sep-2026 = 108.3% (drop 7.7pp).
- Removing each planted driver alone raises Sep NRR by approximately:
  - **A:** legacy Pro repricing at renewal from Apr-2026 (≈40% of renewing Pro accounts
    ×0.75, plus ≈7% renewal churn): ≈ +2.5pp in isolation. Driver-level
    Shapley/sequential bridges typically land at 3.5–3.6pp because of interactions.
  - **B:** churn among Acme-acquired accounts after the May-2026 billing migration: ≈ +2.6pp.
  - **C:** FX conversion change in Jul-2026 (EUR at spot ≈1.05 instead of budget 1.10), a
    measurement artifact: ≈ +0.9–1.1pp.
  - Background drift: ≈ 1.3pp.
- The ×0.75 cluster is a deliberately too-regular pattern. It should be flagged for
  billing verification.
- Red herrings: the APAC usage decline and APAC sales reorg, the mobile redesign, and the
  analytics add-on.

## Eval 6: messy CRM EDA (`fixtures/customers.csv`)
The 12 planted defects:
1. region `NA` means North America (pandas reads it as null by default);
2. country variants US / us / " US" / United States;
3. income -999 sentinel;
4. signup_date 1900-01-01;
5. future signup dates (2031-05-01);
6. amount stored as text with thousands separators;
7. last_nps missing exactly when churned = 1 (a target leak);
8. contact_email and phone are PII;
9. 60 duplicate customer_id values;
10. 40 exact duplicate rows;
11. source_system is constant;
12. status case variants.

Generator side effects, not planted but legitimate findings: status versus churned
disagree, and region is independent of country.
