"""Build the NRR sandbox (eval 5, Auto-Research Mode) and print the answer key.

Planted drivers from 2026 onward:
  A. Legacy "Pro" plan repriced +25% at renewal from 2026-04 -> downgrades (contraction) + some churn
  B. Accounts acquired via "Acme" migrated to new billing 2026-06 -> elevated churn Jul-Sep
  C. MEASUREMENT: EUR accounts converted at fixed budget rate 1.10 until 2026-06, daily spot (~1.05) from 2026-07
Red herring: APAC active-user decline in 2026 with no revenue effect.
"""
import os
import sys
import numpy as np
import pandas as pd

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
rng = np.random.default_rng(11)
months = pd.period_range("2024-01", "2026-09", freq="M")
N = 900
acc = pd.DataFrame({
    "account_id": [f"A{i:04d}" for i in range(N)],
    "segment": "enterprise",
    "region": rng.choice(["NA", "EMEA", "APAC"], N, p=[.5, .3, .2]),
    "plan": rng.choice(["Pro (legacy)", "Business", "Enterprise+"], N, p=[.32, .43, .25]),
    "acquired_via": np.where(rng.random(N) < .16, "Acme acquisition", "organic"),
    "start_month": [str(m) for m in rng.choice(pd.period_range("2023-06", "2026-06", freq="M"), N)],
    "renewal_month_of_year": rng.integers(1, 13, N),
})
acc["billing_currency"] = np.where((acc.region == "EMEA") & (rng.random(N) < .8), "EUR", "USD")
base = rng.lognormal(np.log(9000), 0.6, N)
growth = rng.normal(0.0135, 0.006, N)


def simulate(drivers):
    rows = []
    r = np.random.default_rng(5)
    for i, a in acc.iterrows():
        start = pd.Period(a.start_month, "M")
        mrr = base[i]
        alive = True
        for m in months:
            if m < start or not alive:
                continue
            u = r.random(4)
            mrr *= 1 + growth[i] + r.normal(0, 0.01)
            if u[0] < 0.0035:  # background churn
                alive = False
                continue
            if "A" in drivers and a.plan == "Pro (legacy)" and m >= pd.Period("2026-04", "M") and m.month == a.renewal_month_of_year:
                if u[1] < 0.07:
                    alive = False
                    continue
                if u[2] < 0.40:
                    mrr *= 0.75
            if "B" in drivers and a.acquired_via == "Acme acquisition" and pd.Period("2026-07", "M") <= m <= pd.Period("2026-09", "M"):
                if u[3] < 0.045:
                    alive = False
                    continue
            if a.billing_currency == "EUR":
                rate = 1.05 + r.normal(0, 0.004) if ("C" in drivers and m >= pd.Period("2026-07", "M")) else 1.10
                local = mrr / 1.10
                usd = local * rate
            else:
                usd = mrr
            rows.append((a.account_id, str(m), round(usd, 2)))
    return pd.DataFrame(rows, columns=["account_id", "month", "mrr_usd"])


def nrr(mrr, end):
    end = pd.Period(end, "M")
    startm = end - 12
    s = mrr[mrr.month == str(startm)].set_index("account_id").mrr_usd
    e = mrr[mrr.month == str(end)].set_index("account_id").mrr_usd.reindex(s.index).fillna(0)
    return e.sum() / s.sum()


full = simulate({"A", "B", "C"})
res = {"q1": nrr(full, "2026-03"), "q3": nrr(full, "2026-09")}
key = {"NRR Mar-2026": res["q1"], "NRR Sep-2026": res["q3"]}
for d in ["A", "B", "C"]:
    cf = simulate({"A", "B", "C"} - {d})
    key[f"Sep NRR without {d}"] = nrr(cf, "2026-09")
none = simulate(set())
key["Sep NRR no drivers"] = nrr(none, "2026-09")
drop = res["q1"] - res["q3"]
for d in ["A", "B", "C"]:
    key[f"share of drop explained by {d}"] = (key[f"Sep NRR without {d}"] - res["q3"]) / drop

full.to_csv(f"{out}/mrr_monthly.csv", index=False)
acc.drop(columns=[]).to_csv(f"{out}/accounts.csv", index=False)
# usage with APAC red herring
use = full[["account_id", "month"]].merge(acc[["account_id", "region"]], on="account_id")
decline = np.where((use.region == "APAC") & (use.month >= "2026-01"), 0.75, 1.0)
use["active_users"] = np.maximum(1, (rng.lognormal(3.5, 0.5, len(use)) * decline).round()).astype(int)
use.drop(columns="region").to_csv(f"{out}/product_usage_monthly.csv", index=False)
pd.DataFrame([
    ("2026-02-10", "product", "Launched new analytics add-on (Business & Enterprise+)"),
    ("2026-04-01", "pricing", "Pricing update: legacy Pro plan list price +25%, applied at each account's renewal"),
    ("2026-05-20", "operations", "Acme customer accounts migrated to main billing platform; Acme support desk closed"),
    ("2026-06-15", "sales", "APAC sales team reorganized"),
    ("2026-07-01", "finance-data", "Revenue pipeline: non-USD MRR now converted at daily spot rate (previously annual budget rate)"),
    ("2026-08-05", "product", "Mobile app redesign released"),
], columns=["date", "team", "change"]).to_csv(f"{out}/change_log.csv", index=False)
with open(f"{out}/README.md", "w", encoding="utf-8") as fh:
    fh.write("""# Revenue data extract (enterprise segment)

- `accounts.csv`: one row per enterprise account (plan, region, billing currency, acquisition source, start month, renewal month)
- `mrr_monthly.csv`: month-end MRR in USD per active account (no row = not a customer that month)
- `product_usage_monthly.csv`: monthly active users per account
- `change_log.csv`: company change log (product, pricing, operations, data pipeline)

NRR (trailing 12 months) = MRR at month M from accounts that were customers at M-12, divided by their MRR at M-12.
""")
print({k: round(v, 4) for k, v in key.items()})
