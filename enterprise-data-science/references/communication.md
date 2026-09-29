# Communicating results

The analysis is only as valuable as the decision it changes. Busy leaders give you about
30 seconds, so the first paragraph must carry the whole message.

## Executive summary structure (BLUF: bottom line up front)

```markdown
## [Answer as a headline: "Retention offer pays back; roll out to high-risk segment"]

**Recommendation:** [the action, who does it, by when]
**Impact:** [$ or units, with a range] — e.g., "+$1.2M/yr (range $0.6–1.8M)"
**Confidence:** High / Medium / Low — [one line on why: "randomized test, 6 weeks, 210k users"]
**Key caveats:** [1–3 bullets that could change the decision]
**Next step / decision needed:** [what you need from the reader]

### Supporting evidence
1. [Finding 1, one sentence + chart]
2. [Finding 2]
3. [What we ruled out]

### Appendix: method, data, assumptions log, detailed tables
```

Rules:
- The **headline is a conclusion**, not a topic. "Q3 churn analysis" is a topic; "Churn
  rose 1.2pp, driven by the price change in SMB" is a conclusion.
- **One number per claim, with its comparison and range.** Make "vs. what?" obvious
  (last year, forecast, control, target).
- Put **confidence levels** on everything, and explain them in plain words.
- Say what you **ruled out**. It builds trust and prevents re-litigation.
- Separate **findings** (what the data shows) from **recommendations** (what we should do)
  from **opinions** (judgment calls).
- If the answer is "we can't tell," say it clearly and name what would resolve it
  (more time, an experiment, better data).

## Words for uncertainty

| Confidence | Wording |
|---|---|
| High | "The data shows…", "X caused…" (experiment only) |
| Medium | "Our best estimate is…", "likely", "most consistent with…" |
| Low | "Early signal…", "directionally…", "we can't rule out…" |

Avoid "significant" in casual language, because readers hear "big". Say "statistically
detectable" or give the CI. Avoid false precision: "+12.37%" suggests certainty you don't
have, so write "about +12% (range +4% to +20%)".

## Presenting a model

Don't present AUC to executives. Translate it:

- "If we contact the top 10% of customers the model flags, we reach 45% of the customers
  who would churn, versus 10% with random selection. That's 4.5× more efficient."
- A **lift or gains chart** or a **decile table** (the positive rate by score decile)
  lands better than ROC curves.
- Show the **threshold trade-off** as a business choice: "At 500 reviews a day we catch
  about 62% of fraud dollars; at 800 a day, about 74%."
- Name the top drivers in business language, with the caveat that they are predictive,
  not causal: "Customers who stop logging in and file support tickets are at the highest
  risk. This tells us *who*, not *why*."
- State the limitations and where the model shouldn't be used.

## Charts that communicate

- **One message per chart**, with the message as the title ("SMB churn doubled after
  the June price change").
- Label lines directly instead of using legends. Highlight the series that matters and
  gray out the rest.
- Start bar charts at zero. For line charts, choose axes that show the variation honestly.
- Show uncertainty (error bars or bands) for estimates.
- Annotate the events that explain the shape (a launch, an outage, a price change).
- If the `dataviz` or `data:create-viz` skill is available, use it for the mechanics of
  styling and producing the chart.

## Metric-movement write-up template

```markdown
**[Metric] fell [Δ] ([x%]) week-over-week, outside the normal ±[y]% range.**
- [a]% of the drop is from [segment/cause A] — [evidence]
- [b]% is mix shift: [segment] grew as a share of traffic and has lower [metric]
- Ruled out: tracking change (verified against [source]), seasonality (same week LY was flat)
- Confidence: Medium. Unexplained remainder: [c]%
- Next: [owner] to confirm [hypothesis] by [date]
```
