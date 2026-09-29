#!/usr/bin/env python3
"""Enterprise data profile: finds the data-quality problems that silently break analyses.

  python profile_data.py --data customers.csv [--key customer_id] [--target churned]
                         [--time-col signup_date] [--sample 500000]

Checks (each finding gets a severity and a recommended action):
  * PII columns (by name and by value pattern), for minimization before analysis
  * duplicate rows; duplicate business keys (--key)
  * true nulls vs disguised nulls ("", "n/a", "unknown", "-", "tbd", ...)
  * the literal string "NA", which pandas reads as null by default (North America, Namibia)
  * numbers stored as text ("1,234.56", "$12", "45%"), dates stored as text
  * numeric sentinels (-1, -999, 9999, ...), impossible negatives
  * date sentinels (1900-01-01, 1970-01-01), future dates, gaps in time coverage
  * category variants that differ only by case or whitespace ("US", "us", " US")
  * constant and near-constant columns, high-cardinality categoricals
  * missingness that predicts the target (--target): a leakage or process signal
Output is Markdown.
"""
import argparse
import re
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8")

NA_VALUES = ["", "NaN", "nan", "NULL", "null", "None", "N/A", "n/a", "#N/A"]  # deliberately not "NA"
DISGUISED = {"", "n/a", "na", "none", "null", "nil", "unknown", "unk", "tbd", "tba", "-", "--", "?", ".",
             "missing", "not available", "not applicable", "#n/a", "undefined", "test", "xxx", "default"}
NUM_SENTINELS = {-1, -9, -99, -999, -9999, -99999, 999, 9999, 99999, 999999, 9999999}
PII_TOKENS = re.compile(r"(^|_)(e_?mail|email_?address|phone|phone_?number|mobile|cell|cellphone|ssn|social_?security|"
                        r"passport|national_?id|tax_?id|first_?name|last_?name|full_?name|surname|name|user_?name|login|"
                        r"address|street|zip|zip_?code|postcode|postal_?code|dob|birth_?date|date_?of_?birth|"
                        r"ip|ip_?address|card_?number|card_?num|iban|account_?number|license|latitude|longitude|lat|lon|lng)(_|$)")


def pii_name(col):
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(col)).lower()
    snake = re.sub(r"[^a-z0-9]+", "_", snake)
    return PII_TOKENS.search(snake) is not None
PII_VALUE = {
    "email": re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$"),
    "phone": re.compile(r"^\+?[\d\s().-]{10,18}$"),
    "ssn": re.compile(r"^\d{3}-\d{2}-\d{4}$"),
    "card": re.compile(r"^(?:\d[ -]?){13,19}$"),
    "ipv4": re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$"),
}
NUMERIC_TEXT = re.compile(r"^\s*[-+]?[$€£¥]?\s*[-+]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?\s*%?\s*$")


def is_text(s):
    """True for text columns in both pandas 2 (object) and pandas 3 (str / string dtypes)."""
    if pd.api.types.is_bool_dtype(s) or isinstance(s.dtype, pd.CategoricalDtype):
        return False
    return s.dtype == object or pd.api.types.is_string_dtype(s)


def load(path, sample):
    if path.endswith((".parquet", ".pq")):
        df = pd.read_parquet(path)
    elif path.endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, keep_default_na=False, na_values=NA_VALUES)
    else:
        df = pd.read_csv(path, low_memory=False, keep_default_na=False, na_values=NA_VALUES)
    total = len(df)
    if sample and total > sample:
        df = df.sample(sample, random_state=0)
    return df, total


def auc(y, s):
    from scipy.stats import rankdata
    n1 = y.sum()
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(s)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--key", nargs="*", default=[], help="business key column(s) expected to be unique")
    ap.add_argument("--target", help="target column, used to check whether missingness predicts it")
    ap.add_argument("--time-col", help="main event/snapshot date column for coverage and gap checks")
    ap.add_argument("--sample", type=int, default=1_000_000)
    ap.add_argument("--today", help="reference date for 'future' checks (default: today)")
    a = ap.parse_args()

    df, total = load(a.data, a.sample)
    n = len(df)
    today = pd.Timestamp(a.today) if a.today else pd.Timestamp.today().normalize()
    issues = []  # (severity, column, issue, action)
    prof = []

    def add(sev, col, issue, action):
        issues.append((sev, col, issue, action))

    # ---------------- table level
    dup_rows = int(df.duplicated().sum())
    if dup_rows:
        add("MED", "(table)", f"{dup_rows:,} exact duplicate rows ({dup_rows / n:.2%})",
            "Find the source (double load? join fan-out?) before deduplicating")
    if a.key:
        missing_keys = [k for k in a.key if k not in df.columns]
        if missing_keys:
            sys.exit(f"--key column(s) not found: {missing_keys}")
        kd = df.drop_duplicates()
        dk = int(kd.duplicated(subset=a.key).sum())
        if dk:
            ex = kd[kd.duplicated(subset=a.key, keep=False)][a.key].drop_duplicates().head(3).to_dict("records")
            add("HIGH", "+".join(a.key), f"{dk:,} duplicate business keys after removing exact duplicates (e.g. {ex})",
                "Rows conflict for the same key: decide the grain or the dedup rule (latest? sum?) with the data owner")
    y = None
    if a.target:
        t = df[a.target]
        if t.nunique() == 2:
            pos = sorted(t.dropna().unique(), key=str)[-1]
            y = (t == pos).to_numpy().astype(float)

    # ---------------- columns
    for c in df.columns:
        s = df[c]
        nn = s.notna()
        null_rate = 1 - nn.mean()
        nun = s.nunique(dropna=True)
        kind = "text" if is_text(s) else str(s.dtype)
        notes = []

        if nun <= 1:
            add("LOW", c, f"constant column (value {s.dropna().iloc[0]!r})" if nun == 1 else "entirely null",
                "Drop from features; confirm it isn't a broken extract")
            prof.append((c, "constant", null_rate, nun, ""))
            continue
        top_share = s.value_counts(normalize=True, dropna=True).iloc[0]
        if top_share > 0.98 and nun > 1:
            notes.append(f"near-constant ({top_share:.1%} one value)")

        if pii_name(c):
            add("HIGH", c, "column name suggests PII", "Minimize: drop, hash, or aggregate before analysis; keep out of outputs and prompts")

        if is_text(s):
            sv = s[nn].astype(str)
            stripped = sv.str.strip()
            low = stripped.str.lower()
            # PII by value
            samp = stripped.sample(min(2000, len(stripped)), random_state=0) if len(stripped) else stripped
            looks_date = len(samp) > 0 and pd.to_datetime(samp, errors="coerce", format="mixed").notna().mean() > 0.9
            for kind_, rx in ({} if looks_date else PII_VALUE).items():
                share = samp.str.match(rx).mean() if len(samp) else 0
                if share > 0.5 and not (kind_ in ("phone", "card") and NUMERIC_TEXT.match(samp.iloc[0] or "")):
                    add("HIGH", c, f"values look like {kind_} ({share:.0%} of sample)",
                        "Treat as PII: minimize, hash, or drop; don't print raw values")
                    break
            # literal NA
            n_na = int((stripped == "NA").sum())
            if n_na:
                add("MED", c, f"literal 'NA' in {n_na:,} rows ({n_na / n:.1%}); pandas/R read this as null by default",
                    "Confirm the meaning (North America? Namibia? null?) and load with keep_default_na=False")
            # disguised nulls
            dmask = low.isin(DISGUISED) & (stripped != "NA")
            if dmask.any():
                vals = sv[dmask].value_counts().head(4).to_dict()
                add("MED", c, f"{int(dmask.sum()):,} disguised nulls {vals}", "Convert to real nulls, then decide how to impute")
            # numbers stored as text
            num_share = stripped.str.match(NUMERIC_TEXT).mean() if len(stripped) else 0
            if num_share > 0.9:
                parsed = pd.to_numeric(stripped.str.replace(r"[,$€£¥%\s]", "", regex=True), errors="coerce")
                add("HIGH", c, f"numeric values stored as text ({num_share:.0%} parse, e.g. {sv.iloc[0]!r})",
                    "Parse to numeric (strip thousands separators and currency); sums and sorts are wrong as text")
                kind = "numeric-as-text"
                s_num = parsed
            else:
                s_num = None
            # dates stored as text
            if s_num is None and nun > 10:
                dt = pd.to_datetime(stripped.sample(min(2000, len(stripped)), random_state=0), errors="coerce", format="mixed")
                if dt.notna().mean() > 0.9:
                    kind = "date-as-text"
                    s = pd.to_datetime(stripped, errors="coerce", format="mixed").reindex(df.index)
            # case / whitespace variants
            if kind == "text" and nun <= 500:
                ws = int((sv != stripped).sum())
                grp = pd.DataFrame({"raw": stripped, "norm": low}).drop_duplicates().groupby("norm")["raw"].agg(list)
                variants = grp[grp.str.len() > 1]
                if len(variants) or ws:
                    ex = "; ".join("/".join(v[:4]) for v in variants.head(3))
                    add("MED", c, f"{len(variants)} value(s) with case/whitespace variants ({ex})"
                        + (f"; {ws:,} values with leading/trailing spaces" if ws else ""),
                        "Normalize (strip, casefold); also look for synonyms (e.g. US / United States) and map them with a documented mapping")
                if nun > 50 and nun / nn.sum() < 0.9:
                    notes.append(f"high-cardinality categorical ({nun:,})")
            if kind == "text" and nun / max(1, nn.sum()) > 0.95:
                kind = "id/text"
            if s_num is not None:
                s = s_num

        # numeric checks
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            v = s.dropna()
            if len(v):
                vc = v.value_counts()
                sent = [(k, int(cnt)) for k, cnt in vc.items() if k in NUM_SENTINELS and cnt / len(v) > 0.002]
                q1, q3 = v.quantile([.25, .75])
                sent = [(k, cnt) for k, cnt in sent if k < q1 - 3 * (q3 - q1) or k > q3 + 3 * (q3 - q1) or cnt / len(v) > 0.05]
                if sent:
                    add("HIGH", c, "sentinel values " + ", ".join(f"{k:g} x{cnt:,}" for k, cnt in sent),
                        "Replace with null (plus a missing indicator if informative) before computing stats")
                neg = int((v < 0).sum())
                if neg and not sent and re.search(r"(amount|price|revenue|income|qty|quantity|count|age|duration|days|size)", c, re.I):
                    add("MED", c, f"{neg:,} negative values in a column that is usually non-negative",
                        "Confirm whether these are refunds or reversals, or errors")
                notes.append(f"p1/p50/p99 = {v.quantile(.01):.4g}/{v.median():.4g}/{v.quantile(.99):.4g}")
                if pd.api.types.is_integer_dtype(s) and nun / n > 0.95:
                    kind = "id?"

        # date checks
        if pd.api.types.is_datetime64_any_dtype(s):
            v = s.dropna()
            if len(v):
                old = int((v.dt.year < 1901).sum()) + int((v == pd.Timestamp("1970-01-01")).sum())
                fut = int((v > today).sum())
                if old:
                    add("MED", c, f"{old:,} placeholder dates (year < 1901 or 1970-01-01)", "Convert to null; check the source default")
                if fut:
                    add("MED", c, f"{fut:,} future dates (max {v.max().date()})", "Typo, timezone, or a planned date? Confirm the semantics")
                ok = v[(v.dt.year >= 1901) & (v <= today)]
                if len(ok):
                    notes.append(f"range {ok.min().date()} → {ok.max().date()}")
                    months = ok.dt.to_period("M").value_counts().sort_index()
                    full = pd.period_range(months.index.min(), months.index.max(), freq="M")
                    gaps = [str(p) for p in full if p not in months.index]
                    if gaps and c == a.time_col:
                        add("MED", c, f"{len(gaps)} month(s) with no records: {', '.join(gaps[:6])}", "Outage or extract gap? Don't read these as zero activity")

        # nulls and target association
        if null_rate > 0.2:
            add("MED" if null_rate < 0.6 else "HIGH", c, f"{null_rate:.1%} null", "Why missing? Missing at random or by process? Decide drop, impute, or indicator")
        if y is not None and c != a.target and 0.01 < null_rate < 0.99:
            m = df[c].isna().to_numpy().astype(float)
            aa = auc(y, m)
            if max(aa, 1 - aa) >= 0.6:
                add("HIGH", c, f"missingness predicts the target: rate {y[m == 1].mean():.1%} when null vs {y[m == 0].mean():.1%}",
                    "Likely leakage or process artifact: find out when and why this field is populated")
        prof.append((c, kind, null_rate, nun, "; ".join(notes)))

    # ---------------- output
    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    issues.sort(key=lambda x: order[x[0]])
    print(f"# Data profile: `{a.data}`")
    print(f"- Rows: {total:,}" + (f" (profiled a sample of {n:,})" if n < total else "") + f"; columns: {df.shape[1]}")
    if a.key:
        print(f"- Expected key: {', '.join(a.key)}")
    if a.target:
        print(f"- Target: `{a.target}`" + (f" (rate {y.mean():.2%})" if y is not None else " (not binary; missingness check skipped)"))
    cnt = {k: sum(i[0] == k for i in issues) for k in order}
    print(f"- **Issues: {cnt['HIGH']} high, {cnt['MED']} medium, {cnt['LOW']} low**\n")
    print("## Issues (fix or explain before analysis)")
    print("| Severity | Column | Issue | Recommended action |\n|---|---|---|---|")
    for sev, col, issue, act in issues:
        print(f"| {sev} | `{col}` | {issue} | {act} |")
    print("\n## Column profile")
    print("| Column | Type | Null % | Distinct | Notes |\n|---|---|---|---|---|")
    for c, k, nr, nu, notes in prof:
        print(f"| `{c}` | {k} | {nr:.1%} | {nu:,} | {notes} |")
    print("\n## Not checked automatically (confirm with the data owner)")
    print("- The grain (one row = ?), and whether totals reconcile to a trusted source")
    print("- Point-in-time availability of each feature relative to the prediction moment")
    print("- Definition or tracking changes during the window; population exclusions (survivorship)")


if __name__ == "__main__":
    main()
