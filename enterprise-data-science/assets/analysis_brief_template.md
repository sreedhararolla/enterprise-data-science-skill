# Analysis Brief: [Title]

**Owner (DS):** [name] · **Decision owner:** [name, role] · **Decision needed by:** [date]
**Status:** Draft / Agreed · **Last updated:** [date]

## 1. Decision
What will be done differently depending on the result?
> e.g., "Retention team decides which customers get a 20% discount offer each month."

## 2. Question
> e.g., "Which active customers are likely to cancel in the next 60 days?"

- **Type:** Prediction / Causal effect / Measurement / Forecast / Exploration
- **Unit (one row):** [customer-month, order, account…]
- **Prediction moment:** [when the prediction is made, e.g., "1st of each month, using data through the prior day"]

## 3. Target / outcome
- **Definition:** [exact logic]
- **Window:** [e.g., "cancels within 60 days after the prediction date"]
- **Label source & quality:** [system event / manual / proxy; known issues]

## 4. Success criteria
- **Primary metric:** [metric] ≥ [threshold] vs. baseline [value]
- **Guardrails:** [e.g., precision ≥ 30%; no segment below X]
- **Business bar:** [e.g., "+$500k/yr net of offer cost"]
- **Current baseline / business rule:** [what happens today]

## 5. Cost of errors
| Error | Business consequence | Est. cost |
|---|---|---|
| False positive | [e.g., discount given to a customer who'd have stayed] | [$] |
| False negative | [e.g., churned customer not contacted] | [$] |

## 6. Data
| Source | Grain | Owner | Freshness / latency | Known issues |
|---|---|---|---|---|

- **Trusted reconciliation number:** [e.g., "Finance active-customer count, month-end"]
- **Sensitive data:** [PII / protected attributes involved and handling]

## 7. Approach & validation
- **Method:** [baseline(s), candidate models / causal design]
- **Validation scheme:** [temporal split with N-day gap / grouped by X / experiment design]
- **Final holdout:** [period]

## 8. Constraints
[Latency, batch vs. real-time, interpretability, regulatory, off-limits features, budget]

## 9. Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|

## 10. Out of scope
- ...

## 11. Deliverables & timeline
| Milestone | Date |
|---|---|
| Data audit & reconciliation | |
| Baseline + validation locked | |
| Model / analysis | |
| Readout | |
