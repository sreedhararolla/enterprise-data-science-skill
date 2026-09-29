"""leakage_scan.py flags every planted leak type and does not flag an ID column as predictive."""
import numpy as np
import pandas as pd

from conftest import CORE_SCRIPTS


def test_planted_leaks(tmp_path, run):
    rng = np.random.default_rng(1)
    n = 12000
    t = pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 365, n), unit="D")
    tenure = rng.exponential(24, n)
    logit = -2 - 0.04 * tenure
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    df = pd.DataFrame(dict(
        customer_id=np.arange(n), snapshot_date=t, tenure_months=tenure,
        cancellation_reason_code=np.where(y == 1, rng.choice([1, 2, 3], n), 0),
        retention_offer_amt=np.where((y == 1) & (rng.random(n) < .7), rng.uniform(10, 50, n), np.nan),
        account_ref=[f"AC{i:06d}" for i in rng.permutation(n)],
        health_score=np.where(t >= pd.Timestamp("2025-07-01"), -y * 2 + rng.normal(0, 1, n), rng.normal(0, 1, n)),
        region=rng.choice(["NA", "EU"], n), churned=y))
    df.to_csv(tmp_path / "t.csv", index=False)
    out = run(CORE_SCRIPTS / "leakage_scan.py", "--data", tmp_path / "t.csv", "--target", "churned",
              "--time-col", "snapshot_date", "--id-cols", "customer_id").stdout
    flagged = {l.split("`")[1]: l for l in out.split("## Flagged features")[1].split("## Top")[0].splitlines()
               if l.startswith("| `")}
    assert "VERY_STRONG" in flagged["cancellation_reason_code"]
    assert "MISSING_LEAK" in flagged["retention_offer_amt"]
    assert "DRIFTS_LATER" in flagged["health_score"]
    assert "ID_LIKE" in flagged["account_ref"]
    assert "VERY_STRONG" not in flagged["account_ref"] and "STRONG" not in flagged["account_ref"]
    assert "region" not in flagged  # 'NA' must stay a category, not become nulls
