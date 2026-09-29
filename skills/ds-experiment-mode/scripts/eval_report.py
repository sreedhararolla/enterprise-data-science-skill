#!/usr/bin/env python3
"""Evaluation report from out-of-sample predictions (CSV or Parquet).

Classification (binary):
  python eval_report.py --preds preds.csv --y-true y --y-score score \
      [--baseline-score rule_score] [--segments region plan] \
      [--cost-fp 5 --cost-fn 200] [--capacity 500] [--cluster-col customer_id]

Regression:
  python eval_report.py --preds preds.csv --y-true y --y-pred yhat [--baseline-pred naive] [--segments region]

Produces Markdown: headline metrics with bootstrap CIs vs a baseline, calibration
(classification), a threshold / operating-point table, and per-segment metrics with
small-sample warnings. With --cluster-col, bootstrap resamples whole clusters (use this
when rows are grouped, e.g. several rows per customer).
"""
import argparse
import sys

import numpy as np
import pandas as pd
from scipy.stats import rankdata

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8")

NA_VALUES = ["", "NaN", "nan", "NULL", "null", "None", "N/A", "n/a", "#N/A"]  # deliberately not "NA": it is often a real code (North America, Namibia)


# ------------------------------------------------------------------ metrics
def roc_auc(y, s):
    n1 = y.sum()
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(s)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def threshold_curve(y, s):
    """Cumulative TP/FP at each DISTINCT score threshold (descending), so tied scores are
    always flagged together and results never depend on row order."""
    order = np.argsort(-s, kind="mergesort")
    ys, ss = y[order], s[order]
    tp = np.cumsum(ys)
    fp = np.cumsum(1 - ys)
    last = np.r_[np.where(np.diff(ss) != 0)[0], len(ss) - 1]  # last index of each tie block
    return ss[last], tp[last], fp[last]


def avg_precision(y, s):
    """Average precision = sum over distinct thresholds of (R_n - R_{n-1}) * P_n
    (the same definition as sklearn.metrics.average_precision_score); tie-aware."""
    n1 = y.sum()
    if n1 == 0:
        return np.nan
    _, tp, fp = threshold_curve(y, s)
    prec = tp / (tp + fp)
    rec = tp / n1
    return float(np.sum(np.diff(np.r_[0.0, rec]) * prec))


def brier(y, s):
    return np.mean((s - y) ** 2)


def logloss(y, s):
    s = np.clip(s, 1e-15, 1 - 1e-15)
    return -np.mean(y * np.log(s) + (1 - y) * np.log(1 - s))


CLS_METRICS = {"ROC-AUC": roc_auc, "PR-AUC (avg precision)": avg_precision,
               "Brier": brier, "Log loss": logloss}
LOWER_BETTER = {"Brier", "Log loss", "MAE", "RMSE", "WAPE", "|Bias|"}


def mae(y, p):
    return np.mean(np.abs(y - p))


def rmse(y, p):
    return np.sqrt(np.mean((y - p) ** 2))


def wape(y, p):
    d = np.abs(y).sum()
    return np.abs(y - p).sum() / d if d else np.nan


def abs_bias(y, p):
    return abs(np.mean(p - y))


REG_METRICS = {"MAE": mae, "RMSE": rmse, "WAPE": wape, "|Bias|": abs_bias}


# ------------------------------------------------------------------ bootstrap
def boot_indices(n, clusters, B, rng):
    if clusters is None:
        for _ in range(B):
            yield rng.integers(0, n, n)
    else:
        codes, uniq = pd.factorize(clusters)
        members = pd.Series(np.arange(n)).groupby(codes).apply(np.array).to_list()
        k = len(uniq)
        for _ in range(B):
            pick = rng.integers(0, k, k)
            yield np.concatenate([members[i] for i in pick])


def boot_ci(fn, y, a, b, clusters, B, rng):
    """CI for fn(y, a) and, if b is given, for the paired difference fn(y,a) - fn(y,b)."""
    vals, diffs = [], []
    for idx in boot_indices(len(y), clusters, B, rng):
        yy = y[idx]
        va = fn(yy, a[idx])
        vals.append(va)
        if b is not None:
            diffs.append(va - fn(yy, b[idx]))
    vals = np.array(vals, dtype=float)
    ci = np.nanpercentile(vals, [2.5, 97.5])
    dci = np.nanpercentile(np.array(diffs, dtype=float), [2.5, 97.5]) if b is not None else None
    return ci, dci


def f(x, d=4):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


# ------------------------------------------------------------------ classification
def classification(df, a, rng):
    y = df[a.y_true].to_numpy().astype(float)
    s = df[a.y_score].to_numpy().astype(float)
    if not set(np.unique(y)) <= {0.0, 1.0}:
        sys.exit("--y-true must be 0/1 for classification")
    if s.min() < 0 or s.max() > 1:
        print("> Note: scores are outside [0,1]; Brier, log loss and calibration assume probabilities.\n")
    prev = y.mean()
    clusters = df[a.cluster_col].to_numpy() if a.cluster_col else None
    b = df[a.baseline_score].to_numpy().astype(float) if a.baseline_score else None
    const = np.full_like(s, prev)

    print(f"# Evaluation report (binary classification)")
    print(f"- n = {len(y):,}; positives = {int(y.sum()):,} (prevalence {prev:.2%})")
    if y.sum() < 100:
        print(f"- **Warning:** only {int(y.sum())} positives, so the metric CIs will be wide.")
    base_name = f"`{a.baseline_score}`" if b is not None else "constant (prevalence)"
    print(f"- Baseline: {base_name}; bootstrap B={a.bootstrap}"
          f"{', clustered by `' + a.cluster_col + '`' if clusters is not None else ''}\n")

    print("## Headline metrics")
    print("| Metric | Model | 95% CI | Baseline | Δ vs baseline (95% CI) |")
    print("|---|---|---|---|---|")
    for name, fn in CLS_METRICS.items():
        m = fn(y, s)
        comp = b if b is not None else const
        better = "lower is better" if name in LOWER_BETTER else "higher is better"
        # Brier/log loss compare probabilities; a rule score or rank is not one, so the comparison is meaningless.
        if b is not None and name in ("Brier", "Log loss") and not a.baseline_is_probability:
            ci, _ = boot_ci(fn, y, s, None, clusters, a.bootstrap, rng)
            print(f"| {name} | {f(m)} | {f(ci[0])} – {f(ci[1])} | n/a | n/a: baseline is a score, not a probability "
                  f"(pass --baseline-is-probability if it is calibrated) |")
            continue
        bm = fn(y, comp)
        ci, dci = boot_ci(fn, y, s, comp, clusters, a.bootstrap, rng)
        print(f"| {name} | {f(m)} | {f(ci[0])} – {f(ci[1])} | {f(bm)} | "
              f"{m - bm:+.4f} ({dci[0]:+.4f} – {dci[1]:+.4f}); {better} |")

    # calibration
    print("\n## Calibration (10 quantile bins)")
    bins = pd.qcut(pd.Series(s).rank(method="first"), 10, labels=False)
    cal = pd.DataFrame({"bin": bins, "y": y, "s": s}).groupby("bin").agg(
        n=("y", "size"), mean_score=("s", "mean"), observed=("y", "mean"), min_s=("s", "min"), max_s=("s", "max"))
    ece = (cal.n * (cal.mean_score - cal.observed).abs()).sum() / cal.n.sum()
    print("| Decile | Score range | n | Mean predicted | Observed rate | Ratio obs/pred | Lift vs avg |")
    print("|---|---|---|---|---|---|---|")
    for i, r in cal.iterrows():
        ratio = r.observed / r.mean_score if r.mean_score > 0 else np.nan
        print(f"| {int(i) + 1} | {r.min_s:.3f}–{r.max_s:.3f} | {int(r.n):,} | {r.mean_score:.3f} | "
              f"{r.observed:.3f} | {f(ratio, 2)} | {r.observed / prev:.2f}x |")
    print(f"\nExpected calibration error (ECE): {ece:.4f}. "
          f"{'Well calibrated.' if ece < 0.02 else 'Consider recalibration (isotonic/Platt) on a held-out fold if scores are used as probabilities.'}")

    # thresholds
    print("\n## Operating points")
    thr_d, tp_d, fp_d = threshold_curve(y, s)
    flagged_d = tp_d + fp_d
    P = y.sum()
    rows = []
    ks = sorted({max(1, int(round(q * len(y)))) for q in [0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50]})
    if a.capacity:
        ks = sorted(set(ks) | {min(a.capacity, len(y))})
    tie_note = False
    for k in ks:
        # use the largest distinct threshold that flags at most k cases (ties are never split)
        i = np.searchsorted(flagged_d, k, side="right") - 1
        if i < 0:
            i = 0  # the top tie block alone exceeds k: report it, flagged count shows the overshoot
        tp, fp, n_flag = tp_d[i], fp_d[i], flagged_d[i]
        tie_note |= n_flag != k
        fn_ = P - tp
        row = dict(k=k, n_flag=int(n_flag), thr=thr_d[i], prec=tp / n_flag, rec=tp / P if P else np.nan,
                   lift=(tp / n_flag) / prev,
                   cost=(fp * a.cost_fp + fn_ * a.cost_fn) if a.cost_fp is not None and a.cost_fn is not None else None,
                   cap=(a.capacity == k))
        rows.append(row)
    has_cost = a.cost_fp is not None and a.cost_fn is not None
    hdr = "| Flag top | Threshold | Precision | Recall | Lift |" + (" Expected cost |" if has_cost else "")
    print(hdr)
    print("|---" * (hdr.count("|") - 1) + "|")
    for r in rows:
        tag = " **(capacity)**" if r["cap"] else ""
        shown = f"{r['k']:,}" if r["n_flag"] == r["k"] else f"{r['k']:,} → {r['n_flag']:,} (ties)"
        line = (f"| {shown} ({r['n_flag'] / len(y):.1%}){tag} | {r['thr']:.4f} | {r['prec']:.3f} | "
                f"{r['rec']:.3f} | {r['lift']:.2f}x |")
        if has_cost:
            line += f" {r['cost']:,.0f} |"
        print(line)
    if tie_note:
        print("\nNote: tied scores are never split, so some rows flag a different count than requested.")
    if has_cost:
        costs = fp_d * a.cost_fp + (P - tp_d) * a.cost_fn
        costs = np.concatenate([[P * a.cost_fn], costs])  # index 0: flag nobody
        j = int(np.argmin(costs))
        k_best = 0 if j == 0 else int(flagged_d[j - 1])
        base_cost = min(P * a.cost_fn, (len(y) - P) * a.cost_fp)
        thr_best = thr_d[j - 1] if j > 0 else np.inf
        print(f"\nCost-optimal: flag top {k_best:,} (score ≥ {f(thr_best)}), expected cost {costs[j]:,.0f} "
              f"vs {base_cost:,.0f} for the best trivial policy (flag all / none). "
              f"If calibrated, theoretical threshold = {a.cost_fp / (a.cost_fp + a.cost_fn):.4f}.")

    # segments
    if a.segments:
        print("\n## Segments")
        for seg in a.segments:
            print(f"\n### by `{seg}`")
            print("| Value | n | Positives | Prevalence | ROC-AUC | PR-AUC | Mean score / observed | Note |")
            print("|---|---|---|---|---|---|---|---|")
            g = df.groupby(df[seg].astype(str).fillna("__NA__"))
            for val, sub in sorted(g, key=lambda kv: -len(kv[1]))[: a.max_segment_values]:
                yy = sub[a.y_true].to_numpy().astype(float)
                ss = sub[a.y_score].to_numpy().astype(float)
                npos = int(yy.sum())
                note = "insufficient data (<30 positives)" if npos < 30 else ""
                cal_ratio = ss.mean() / yy.mean() if yy.mean() > 0 else np.nan
                if not note and not np.isnan(cal_ratio) and not 0.8 <= cal_ratio <= 1.25:
                    note = "miscalibrated in this segment"
                print(f"| {val} | {len(yy):,} | {npos:,} | {yy.mean():.2%} | {f(roc_auc(yy, ss), 3)} | "
                      f"{f(avg_precision(yy, ss), 3)} | {f(cal_ratio, 2)} | {note} |")


# ------------------------------------------------------------------ regression
def regression(df, a, rng):
    y = df[a.y_true].to_numpy().astype(float)
    p = df[a.y_pred].to_numpy().astype(float)
    clusters = df[a.cluster_col].to_numpy() if a.cluster_col else None
    if a.baseline_pred:
        b = df[a.baseline_pred].to_numpy().astype(float)
        bname = f"`{a.baseline_pred}`"
    else:
        b = np.full_like(y, y.mean())
        bname = "constant mean of y_true (optimistic: uses test mean)"
    print("# Evaluation report (regression)")
    print(f"- n = {len(y):,}; y mean {y.mean():.4g}, sd {y.std():.4g}")
    print(f"- Baseline: {bname}; bootstrap B={a.bootstrap}\n")
    print("## Headline metrics")
    print("| Metric | Model | 95% CI | Baseline | Δ vs baseline (95% CI) |")
    print("|---|---|---|---|---|")
    for name, fn in REG_METRICS.items():
        m, bm = fn(y, p), fn(y, b)
        ci, dci = boot_ci(fn, y, p, b, clusters, a.bootstrap, rng)
        print(f"| {name} | {f(m)} | {f(ci[0])} – {f(ci[1])} | {f(bm)} | {m - bm:+.4f} ({dci[0]:+.4f} – {dci[1]:+.4f}); lower is better |")
    skill = 1 - mae(y, p) / mae(y, b) if mae(y, b) > 0 else np.nan
    print(f"\nMAE skill vs baseline: {skill:+.1%} (positive = better than baseline).")
    print("\n## Error by prediction decile")
    dec = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False)
    t = pd.DataFrame({"d": dec, "y": y, "p": p}).groupby("d").agg(n=("y", "size"), mean_pred=("p", "mean"), mean_actual=("y", "mean"))
    print("| Decile | n | Mean predicted | Mean actual | Bias |")
    print("|---|---|---|---|---|")
    for i, r in t.iterrows():
        print(f"| {int(i) + 1} | {int(r.n):,} | {r.mean_pred:.4g} | {r.mean_actual:.4g} | {r.mean_pred - r.mean_actual:+.4g} |")
    if a.segments:
        print("\n## Segments")
        for seg in a.segments:
            print(f"\n### by `{seg}`")
            print("| Value | n | MAE | Bias (pred-actual) | WAPE | Note |")
            print("|---|---|---|---|---|---|")
            g = df.groupby(df[seg].astype(str).fillna("__NA__"))
            for val, sub in sorted(g, key=lambda kv: -len(kv[1]))[: a.max_segment_values]:
                yy = sub[a.y_true].to_numpy().astype(float)
                pp = sub[a.y_pred].to_numpy().astype(float)
                note = "small n" if len(yy) < 50 else ""
                print(f"| {val} | {len(yy):,} | {mae(yy, pp):.4g} | {np.mean(pp - yy):+.4g} | {f(wape(yy, pp), 3)} | {note} |")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preds", required=True)
    ap.add_argument("--y-true", required=True)
    ap.add_argument("--y-score", help="predicted probability/score (classification)")
    ap.add_argument("--y-pred", help="predicted value (regression)")
    ap.add_argument("--baseline-score", help="column with a baseline/current-rule score (classification)")
    ap.add_argument("--baseline-is-probability", action="store_true",
                    help="baseline score is a calibrated probability, so compare Brier/log loss too")
    ap.add_argument("--baseline-pred",help="column with a baseline prediction (regression), e.g. seasonal naive")
    ap.add_argument("--segments", nargs="*", default=[])
    ap.add_argument("--max-segment-values", type=int, default=15)
    ap.add_argument("--cost-fp", type=float)
    ap.add_argument("--cost-fn", type=float)
    ap.add_argument("--capacity", type=int, help="number of cases the team can act on")
    ap.add_argument("--cluster-col", help="resample whole clusters in the bootstrap")
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    df = pd.read_parquet(a.preds) if a.preds.endswith((".parquet", ".pq")) else pd.read_csv(a.preds, keep_default_na=False, na_values=NA_VALUES)
    rng = np.random.default_rng(a.seed)
    if a.y_score:
        df = df.dropna(subset=[a.y_true, a.y_score]).reset_index(drop=True)
        classification(df, a, rng)
    elif a.y_pred:
        df = df.dropna(subset=[a.y_true, a.y_pred]).reset_index(drop=True)
        regression(df, a, rng)
    else:
        sys.exit("Give --y-score (classification) or --y-pred (regression)")


if __name__ == "__main__":
    main()
