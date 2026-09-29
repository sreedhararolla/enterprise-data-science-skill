#!/usr/bin/env python3
"""Compare feature distributions between a reference dataset (e.g. training) and a
current one (e.g. last week's serving data) using the population stability index (PSI),
the KS test, and missing-rate change.

  python drift_check.py --reference train.parquet --current serving_week.parquet [--features a b c]

PSI guide: < 0.1 stable · 0.1–0.2 watch · > 0.2 major shift.
KS p-values are nearly always "significant" at large n, so prioritize PSI and the KS statistic.
"""
import argparse
import sys

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8")

NA_VALUES = ["", "NaN", "nan", "NULL", "null", "None", "N/A", "n/a", "#N/A"]  # deliberately not "NA": it is often a real code (North America, Namibia)

EPS = 1e-4


def load(p):
    return pd.read_parquet(p) if p.endswith((".parquet", ".pq")) else pd.read_csv(p, low_memory=False, keep_default_na=False, na_values=NA_VALUES)


def psi(ref_share, cur_share):
    r = np.clip(ref_share, EPS, None)
    c = np.clip(cur_share, EPS, None)
    return float(np.sum((c - r) * np.log(c / r)))


def numeric_psi(r, c, bins):
    rv = r.dropna().to_numpy()
    cv = c.dropna().to_numpy()
    edges = np.unique(np.quantile(rv, np.linspace(0, 1, bins + 1)))
    if len(edges) < 2:
        edges = np.array([rv.min(), rv.max() + 1e-9])
    edges[0], edges[-1] = -np.inf, np.inf
    rh = np.histogram(rv, edges)[0]
    ch = np.histogram(cv, edges)[0]
    # missing as its own bin
    rs = np.append(rh, r.isna().sum()) / len(r)
    cs = np.append(ch, c.isna().sum()) / len(c)
    ks = ks_2samp(rv, cv) if len(rv) and len(cv) else None
    return psi(rs, cs), ks


def categorical_psi(r, c, top):
    r = r.astype("object").where(r.notna(), "__NA__").astype(str)
    c = c.astype("object").where(c.notna(), "__NA__").astype(str)
    unseen = c[~c.isin(set(r))]
    new = [f"{v} ({n / len(c):.1%})" for v, n in unseen.value_counts().items()]
    keep = r.value_counts().index[:top]
    r = r.where(r.isin(keep), "__OTHER__")
    c = c.where(c.isin(keep), "__OTHER__")
    cats = sorted(set(r) | set(c))
    rs = r.value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
    cs = c.value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
    return psi(rs, cs), new


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--current", required=True)
    ap.add_argument("--features", nargs="*")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--bins", type=int, default=10)
    ap.add_argument("--top-categories", type=int, default=20)
    a = ap.parse_args()

    ref, cur = load(a.reference), load(a.current)
    only_ref = sorted(set(ref.columns) - set(cur.columns))
    only_cur = sorted(set(cur.columns) - set(ref.columns))
    feats = a.features or [c for c in ref.columns if c in cur.columns and c not in a.exclude]

    rows = []
    for f in feats:
        r, c = ref[f], cur[f]
        mr, mc = r.isna().mean(), c.isna().mean()
        note = ""
        if pd.api.types.is_numeric_dtype(r) and pd.api.types.is_numeric_dtype(c) and r.nunique() > a.top_categories:
            p, ks = numeric_psi(r.astype(float), c.astype(float), a.bins)
            ks_s = f"{ks.statistic:.3f}" if ks else ""
            rmed, cmed = r.median(), c.median()
            note = f"median {rmed:.4g} -> {cmed:.4g}"
        else:
            p, new = categorical_psi(r, c, a.top_categories)
            ks_s = ""
            if new:
                note = f"unseen in reference: {', '.join(new[:5])}{'…' if len(new) > 5 else ''}"
        if abs(mc - mr) > 0.05:
            note = (note + "; " if note else "") + f"missing {mr:.1%} -> {mc:.1%}"
        status = "MAJOR" if p > 0.2 else "watch" if p > 0.1 else "stable"
        rows.append((f, p, ks_s, mr, mc, status, note))

    rows.sort(key=lambda x: -x[1])
    print("# Drift check")
    print(f"- Reference: `{a.reference}` ({len(ref):,} rows) · Current: `{a.current}` ({len(cur):,} rows)")
    n_major = sum(r[5] == "MAJOR" for r in rows)
    n_watch = sum(r[5] == "watch" for r in rows)
    print(f"- {len(rows)} features: **{n_major} major**, {n_watch} watch, {len(rows) - n_major - n_watch} stable")
    if only_ref:
        print(f"- **Missing in current:** {', '.join(only_ref)}")
    if only_cur:
        print(f"- New in current: {', '.join(only_cur)}")
    print("\n| Feature | PSI | KS stat | Missing ref | Missing cur | Status | Note |")
    print("|---|---|---|---|---|---|---|")
    for f, p, ks_s, mr, mc, st, note in rows:
        print(f"| `{f}` | {p:.3f} | {ks_s} | {mr:.1%} | {mc:.1%} | {st} | {note} |")
    print("\nFor MAJOR shifts: check for an upstream pipeline or definition change first, then real "
          "population change. Then check whether the model's performance on recent labeled data has degraded.")


if __name__ == "__main__":
    main()
