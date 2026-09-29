#!/usr/bin/env python3
"""Scan a modeling table for likely target leakage and other red flags.

For every feature, estimates *univariate* predictive power against the target using
out-of-fold target encoding over quantile bins (numeric) or categories. Because the
encoding is out-of-fold, a unique ID column cannot memorize the target, so a high score
here means the feature genuinely separates the target on its own. For noisy business
targets, that is usually a sign of leakage.

Flags
  VERY_STRONG   univariate AUC >= --auc-flag (binary) or R2 >= --r2-flag (regression)
  STRONG        a softer threshold; verify when the feature is populated
  ID_LIKE       near-unique values (should not be a feature)
  MISSING_LEAK  whether the value is missing predicts the target
  NAME          column name suggests post-outcome information
  CONSTANT      a single value
  DRIFTS_LATER  (with --time-col) power rises notably in the later half of the data,
                a symptom of backfills or definition changes

Usage
  python leakage_scan.py --data table.parquet --target churned
  python leakage_scan.py --data t.csv --target y --time-col snapshot_date --id-cols customer_id
"""
import argparse
import re
import sys

import numpy as np
import pandas as pd
from scipy.stats import rankdata

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8")

NA_VALUES = ["", "NaN", "nan", "NULL", "null", "None", "N/A", "n/a", "#N/A"]  # deliberately not "NA": it is often a real code (North America, Namibia)

SUSPECT_NAME = re.compile(
    r"(^|_)(after|post|outcome|result|label|target|future|final|closed|close|cancel\w*|"
    r"churn\w*|refund\w*|chargeback\w*|resolution|resolved|status|days_to|paid|approved|"
    r"default\w*|won|lost|converted|conversion|end_date|termination|writeoff|write_off)(_|$)",
    re.I,
)


def load(path):
    if path.endswith((".parquet", ".pq")):
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False, keep_default_na=False, na_values=NA_VALUES)


def auc(y, s):
    y = np.asarray(y)
    n1 = y.sum()
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(s)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def r2(y, p):
    ss_res = ((y - p) ** 2).sum()
    ss_tot = ((y - y.mean()) ** 2).sum()
    return 1 - ss_res / ss_tot if ss_tot > 0 else np.nan


def to_codes(col, bins):
    """Map a column to discrete codes: quantile bins for numeric, categories otherwise."""
    if pd.api.types.is_bool_dtype(col):
        col = col.astype("float")
    if pd.api.types.is_numeric_dtype(col) and col.nunique(dropna=True) > bins:
        try:
            codes = pd.qcut(col, q=bins, labels=False, duplicates="drop")
        except ValueError:
            codes = col
        return codes.astype("float").fillna(-1).astype(int).astype(str)
    if pd.api.types.is_datetime64_any_dtype(col):
        codes = pd.qcut(col.astype("int64").where(col.notna()), q=bins, labels=False, duplicates="drop")
        return codes.astype("float").fillna(-1).astype(int).astype(str)
    return col.astype("object").where(col.notna(), "__NA__").astype(str)


def oof_encode(codes, y, folds, rng, smoothing=20):
    n = len(y)
    idx = rng.permutation(n)
    fold_id = np.empty(n, dtype=int)
    fold_id[idx] = np.arange(n) % folds
    out = np.empty(n, dtype=float)
    codes = codes.to_numpy()
    for f in range(folds):
        tr, va = fold_id != f, fold_id == f
        prior = y[tr].mean()
        stats_ = pd.DataFrame({"c": codes[tr], "y": y[tr]}).groupby("c")["y"].agg(["sum", "count"])
        enc = (stats_["sum"] + prior * smoothing) / (stats_["count"] + smoothing)
        out[va] = pd.Series(codes[va]).map(enc).fillna(prior).to_numpy()
    return out


def power(codes, y, binary, folds, rng):
    enc = oof_encode(codes, y, folds, rng)
    if binary:
        a = auc(y, enc)
        return max(a, 1 - a) if not np.isnan(a) else np.nan
    return r2(y, enc)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="CSV or Parquet file")
    ap.add_argument("--target", required=True)
    ap.add_argument("--time-col", help="timestamp column for drift-over-time check (excluded as a feature)")
    ap.add_argument("--id-cols", nargs="*", default=[], help="identifier columns to exclude")
    ap.add_argument("--exclude", nargs="*", default=[], help="other columns to exclude")
    ap.add_argument("--bins", type=int, default=20)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--sample", type=int, default=300_000, help="max rows to scan")
    ap.add_argument("--auc-flag", type=float, default=0.90)
    ap.add_argument("--auc-warn", type=float, default=0.80)
    ap.add_argument("--r2-flag", type=float, default=0.50)
    ap.add_argument("--r2-warn", type=float, default=0.30)
    ap.add_argument("--top", type=int, default=40, help="rows to show in the table")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    df = load(a.data)
    if a.target not in df.columns:
        sys.exit(f"target '{a.target}' not in columns")
    df = df[df[a.target].notna()]
    if len(df) > a.sample:
        df = df.sample(a.sample, random_state=a.seed)
    df = df.reset_index(drop=True)

    yraw = df[a.target]
    binary = yraw.nunique() == 2
    if binary:
        pos = sorted(yraw.unique(), key=str)[-1]
        y = (yraw == pos).astype(float).to_numpy()
    elif pd.api.types.is_numeric_dtype(yraw):
        y = yraw.astype(float).to_numpy()
    else:
        sys.exit("target must be binary or numeric (multiclass: scan one-vs-rest per class)")

    excluded = {a.target, *a.id_cols, *a.exclude} | ({a.time_col} if a.time_col else set())
    feats = [c for c in df.columns if c not in excluded]

    late_mask = None
    if a.time_col:
        t = pd.to_datetime(df[a.time_col], errors="coerce")
        late_mask = (t >= t.median()).to_numpy()

    n = len(df)
    rows = []
    for c in feats:
        col = df[c]
        flags = []
        nun = col.nunique(dropna=True)
        miss = col.isna().mean()
        if nun <= 1:
            rows.append(dict(feature=c, power=np.nan, missing=miss, unique=nun, flags="CONSTANT", note=""))
            continue
        codes = to_codes(col, a.bins)
        pw = power(codes, y, binary, a.folds, rng)
        hi, warn = (a.auc_flag, a.auc_warn) if binary else (a.r2_flag, a.r2_warn)
        if pw >= hi:
            flags.append("VERY_STRONG")
        elif pw >= warn:
            flags.append("STRONG")
        is_int_or_str = not pd.api.types.is_float_dtype(col)
        if is_int_or_str and nun / n > 0.95:
            flags.append("ID_LIKE")
        note = ""
        if 0.01 < miss < 0.99:
            m = col.isna().to_numpy().astype(float)
            if binary:
                ma = auc(y, m)
                ma = max(ma, 1 - ma)
                if ma >= 0.60:
                    flags.append("MISSING_LEAK")
                    note = (f"target rate {y[m == 1].mean():.1%} when missing vs "
                            f"{y[m == 0].mean():.1%} when present")
            else:
                d = abs(y[m == 1].mean() - y[m == 0].mean()) / (y.std() + 1e-12)
                if d >= 0.5:
                    flags.append("MISSING_LEAK")
                    note = f"target mean differs by {d:.2f} sd when missing"
        if SUSPECT_NAME.search(c):
            flags.append("NAME")
        if late_mask is not None and late_mask.sum() > 200 and (~late_mask).sum() > 200:
            e = power(codes[~late_mask].reset_index(drop=True), y[~late_mask], binary, a.folds, rng)
            l = power(codes[late_mask].reset_index(drop=True), y[late_mask], binary, a.folds, rng)
            if not (np.isnan(e) or np.isnan(l)) and l - e >= 0.08:
                flags.append("DRIFTS_LATER")
                note = (note + "; " if note else "") + f"power early {e:.2f} -> late {l:.2f}"
        rows.append(dict(feature=c, power=pw, missing=miss, unique=nun, flags=",".join(flags), note=note))

    res = pd.DataFrame(rows).sort_values("power", ascending=False, na_position="last")
    metric = "AUC (univariate, OOF)" if binary else "R2 (univariate, OOF)"
    print(f"# Leakage scan: `{a.data}`")
    print(f"- Rows scanned: {n:,}; features: {len(feats)}; target: `{a.target}` "
          f"({'binary, positive=' + repr(pos) + f', rate {y.mean():.2%}' if binary else 'numeric'})")
    print(f"- Power metric: {metric}. For noisy business targets, single features rarely exceed "
          f"{'AUC 0.75' if binary else 'R2 0.2'}.\n")

    flagged = res[res["flags"] != ""]
    print(f"## Flagged features ({len(flagged)})")
    if flagged.empty:
        print("None. Still confirm point-in-time availability for the top features.\n")
    else:
        print("| Feature | Power | Missing | Unique | Flags | Note |")
        print("|---|---|---|---|---|---|")
        for r in flagged.itertuples():
            pw = "" if pd.isna(r.power) else f"{r.power:.3f}"
            print(f"| `{r.feature}` | {pw} | {r.missing:.1%} | {r.unique:,} | {r.flags} | {r.note} |")
        print()

    print(f"## Top {min(a.top, len(res))} features by univariate power")
    print("| Feature | Power | Missing | Unique |")
    print("|---|---|---|---|")
    for r in res.head(a.top).itertuples():
        pw = "" if pd.isna(r.power) else f"{r.power:.3f}"
        print(f"| `{r.feature}` | {pw} | {r.missing:.1%} | {r.unique:,} |")

    print("\n## Next steps")
    print("- For each VERY_STRONG / STRONG / NAME / MISSING_LEAK feature, ask its owner *when* "
          "it is populated relative to the prediction time.")
    print("- ID_LIKE columns should not be features. DRIFTS_LATER suggests a backfill or definition change.")
    print("- Univariate power misses leaks that only show up in combination with other features. "
          "Also inspect the fitted model's top permutation importances.")


if __name__ == "__main__":
    main()
