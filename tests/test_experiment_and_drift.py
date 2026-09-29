"""experiment.py matches textbook numbers; drift_check.py flags shifts and unseen categories."""
import numpy as np
import pandas as pd

from conftest import CORE_SCRIPTS


def test_power_textbook(run):
    out = run(CORE_SCRIPTS / "experiment.py", "power", "--baseline", "0.10", "--mde-abs", "0.02").stdout
    assert "n per arm: 3,841" in out


def test_mde_roundtrip(run):
    out = run(CORE_SCRIPTS / "experiment.py", "mde", "--baseline", "0.10", "--n-per-arm", "3841").stdout
    assert "+2.000pp" in out


def test_srm_detected(run):
    out = run(CORE_SCRIPTS / "experiment.py", "srm", "--counts", "48210", "50944").stdout
    assert "SRM DETECTED" in out


def test_analyze_lift(run):
    out = run(CORE_SCRIPTS / "experiment.py", "analyze", "--control", "2031", "48210",
              "--treatment", "2260", "50944").stdout
    assert "+5.30%" in out and "Not statistically detectable" in out


def test_drift(tmp_path, run):
    rng = np.random.default_rng(0)
    n = 4000
    ref = pd.DataFrame(dict(x=rng.normal(0, 1, n), region=rng.choice(["NA", "EU"], n), keep=rng.normal(0, 1, n)))
    cur = pd.DataFrame(dict(x=rng.normal(1, 1, n), region=np.where(rng.random(n) < .1, "MEA", rng.choice(["NA", "EU"], n))))
    ref.to_csv(tmp_path / "ref.csv", index=False)
    cur.to_csv(tmp_path / "cur.csv", index=False)
    out = run(CORE_SCRIPTS / "drift_check.py", "--reference", tmp_path / "ref.csv", "--current", tmp_path / "cur.csv").stdout
    x_line = next(l for l in out.splitlines() if l.startswith("| `x`"))
    assert "MAJOR" in x_line
    assert "unseen in reference: MEA" in out
    assert "Missing in current:** keep" in out
    region = next(l for l in out.splitlines() if l.startswith("| `region`"))
    assert "| 0.0% |" in region  # 'NA' is a value, not a null
