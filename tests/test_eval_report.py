"""eval_report.py: tie-aware average precision, tie-safe operating points, CLI smoke test."""
import sys

import numpy as np
import pandas as pd
import pytest

from conftest import CORE_SCRIPTS

sys.path.insert(0, str(CORE_SCRIPTS))
import eval_report as er  # noqa: E402


def test_ap_all_ties_independent_of_row_order():
    s = np.full(4, 0.5)
    assert er.avg_precision(np.array([1., 0., 1., 0.]), s) == pytest.approx(0.5)
    assert er.avg_precision(np.array([0., 1., 0., 1.]), s) == pytest.approx(0.5)


def test_ap_perfect_ranking():
    assert er.avg_precision(np.array([1., 1., 0., 0.]), np.array([.9, .8, .2, .1])) == pytest.approx(1.0)


def test_ap_matches_sklearn_with_heavy_ties():
    sk = pytest.importorskip("sklearn.metrics")
    rng = np.random.default_rng(0)
    for _ in range(200):
        n = int(rng.integers(5, 300))
        y = (rng.random(n) < rng.uniform(.05, .6)).astype(float)
        if y.sum() == 0:
            continue
        s = np.round(rng.random(n) + y * rng.uniform(0, .5), int(rng.integers(0, 3)))
        assert er.avg_precision(y, s) == pytest.approx(sk.average_precision_score(y, s), abs=1e-12)


def test_threshold_curve_never_splits_ties():
    y = np.array([1., 0., 1., 0., 1.])
    s = np.array([.9, .5, .5, .5, .1])
    thr, tp, fp = er.threshold_curve(y, s)
    assert list(thr) == [.9, .5, .1]
    assert list(tp + fp) == [1, 4, 5]


def test_cli_classification_and_regression(tmp_path, run):
    rng = np.random.default_rng(1)
    n = 3000
    y = (rng.random(n) < .1).astype(int)
    score = np.clip(.1 + .3 * y + rng.normal(0, .15, n), 0, 1).round(2)  # rounded -> ties
    pd.DataFrame(dict(y=y, score=score, rule=(score > .3).astype(float), seg=rng.choice(list("ab"), n))) \
        .to_csv(tmp_path / "p.csv", index=False)
    out = run(CORE_SCRIPTS / "eval_report.py", "--preds", tmp_path / "p.csv", "--y-true", "y", "--y-score", "score",
              "--baseline-score", "rule", "--segments", "seg", "--cost-fp", "5", "--cost-fn", "100",
              "--capacity", "150", "--bootstrap", "50").stdout
    assert "Headline metrics" in out and "Operating points" in out and "Cost-optimal" in out
    assert "n/a: baseline is a score" in out  # Brier/log loss not compared against a rule score
    yr = rng.normal(100, 20, n)
    pd.DataFrame(dict(y=yr, yhat=yr + rng.normal(0, 5, n), naive=np.roll(yr, 1))).to_csv(tmp_path / "r.csv", index=False)
    out = run(CORE_SCRIPTS / "eval_report.py", "--preds", tmp_path / "r.csv", "--y-true", "y", "--y-pred", "yhat",
              "--baseline-pred", "naive", "--bootstrap", "50").stdout
    assert "MAE skill vs baseline" in out
