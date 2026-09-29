#!/usr/bin/env python3
"""A/B test math: power, MDE, sample ratio mismatch, and result analysis.

Subcommands
  power    Sample size per arm for a target minimum detectable effect (MDE).
  mde      Minimum detectable effect for a given sample size per arm.
  srm      Sample ratio mismatch chi-square test.
  analyze  Absolute and relative lift with confidence intervals from summary stats.

Examples
  python experiment.py power --baseline 0.041 --mde-rel 0.05
  python experiment.py power --metric mean --baseline 52.3 --sd 110 --mde-abs 1.5
  python experiment.py mde --baseline 0.041 --n-per-arm 60000
  python experiment.py srm --counts 50410 49120 [--ratios 0.5 0.5]
  python experiment.py analyze --metric proportion --control 2050 50000 --treatment 2230 50100
  python experiment.py analyze --metric mean --control 52.3 110 50000 --treatment 53.9 112 50100

All tests are two-sided. With more than one treatment arm, divide alpha by the number of
comparisons (Bonferroni) or use a proper multiple-comparison procedure.
"""
import argparse
import math
import sys

from scipy import stats

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8")


def z(q):
    return stats.norm.ppf(q)


def fmt_pct(x, d=2):
    return f"{x * 100:.{d}f}%"


# ---------------------------------------------------------------- power / mde
def n_proportion(p1, p2, alpha, power):
    za, zb = z(1 - alpha / 2), z(power)
    pbar = (p1 + p2) / 2
    num = (za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return math.ceil(num / (p2 - p1) ** 2)


def n_mean(sd, delta, alpha, power):
    za, zb = z(1 - alpha / 2), z(power)
    return math.ceil(2 * (za + zb) ** 2 * sd ** 2 / delta ** 2)


def cmd_power(a):
    if (a.mde_abs is None) == (a.mde_rel is None):
        sys.exit("Give exactly one of --mde-abs or --mde-rel")
    delta = a.mde_abs if a.mde_abs is not None else a.baseline * a.mde_rel
    if a.metric == "proportion":
        if not 0 < a.baseline < 1:
            sys.exit("--baseline must be a rate in (0, 1) for proportion metrics")
        p2 = a.baseline + delta
        if not 0 < p2 < 1:
            sys.exit("baseline + MDE falls outside (0, 1)")
        n = n_proportion(a.baseline, p2, a.alpha, a.power)
        desc = f"{fmt_pct(a.baseline)} -> {fmt_pct(p2)} (abs {delta * 100:+.3f}pp, rel {delta / a.baseline:+.1%})"
    else:
        if a.sd is None:
            sys.exit("--sd is required for mean metrics")
        n = n_mean(a.sd, delta, a.alpha, a.power)
        desc = f"{a.baseline:g} -> {a.baseline + delta:g} (abs {delta:+g}, rel {delta / a.baseline:+.1%}), sd={a.sd:g}"
    total = n * a.arms
    print("## Sample size")
    print(f"- Metric: {a.metric}; effect: {desc}")
    print(f"- alpha={a.alpha} (two-sided), power={a.power}")
    print(f"- **n per arm: {n:,}**  (total across {a.arms} arms: {total:,})")
    if a.daily_traffic:
        days = math.ceil(total / a.daily_traffic)
        weeks = max(1, math.ceil(days / 7))
        print(f"- At {a.daily_traffic:,} eligible units/day: ~{days} days; "
              f"run at least {weeks} full week(s) to cover weekly cycles")
    if a.metric == "mean" and a.sd > 2 * abs(a.baseline):
        print("- Note: sd is large relative to the mean (heavy tail?). Consider CUPED, "
              "pre-registered winsorization, or a less noisy proxy metric.")


def cmd_mde(a):
    za, zb = z(1 - a.alpha / 2), z(a.power)
    if a.metric == "proportion":
        # iterate: variance depends on p2
        d = (za + zb) * math.sqrt(2 * a.baseline * (1 - a.baseline) / a.n_per_arm)
        for _ in range(50):
            p2 = a.baseline + d
            d = (za * math.sqrt(2 * ((a.baseline + p2) / 2) * (1 - (a.baseline + p2) / 2))
                 + zb * math.sqrt(a.baseline * (1 - a.baseline) + p2 * (1 - p2))) / math.sqrt(a.n_per_arm)
        print("## Minimum detectable effect")
        print(f"- Baseline {fmt_pct(a.baseline)}, n per arm {a.n_per_arm:,}, alpha={a.alpha}, power={a.power}")
        print(f"- **MDE: {d * 100:+.3f}pp absolute ({d / a.baseline:+.1%} relative)**")
    else:
        if a.sd is None:
            sys.exit("--sd is required for mean metrics")
        d = (za + zb) * a.sd * math.sqrt(2 / a.n_per_arm)
        print("## Minimum detectable effect")
        print(f"- Baseline {a.baseline:g}, sd {a.sd:g}, n per arm {a.n_per_arm:,}")
        print(f"- **MDE: {d:+.4g} absolute ({d / a.baseline:+.1%} relative)**")


# ---------------------------------------------------------------- srm
def cmd_srm(a):
    counts = a.counts
    ratios = a.ratios or [1 / len(counts)] * len(counts)
    if len(ratios) != len(counts):
        sys.exit("--ratios must have the same length as --counts")
    s = sum(ratios)
    total = sum(counts)
    expected = [total * r / s for r in ratios]
    chi2, p = stats.chisquare(counts, expected)
    print("## Sample ratio mismatch check")
    print("| Arm | Observed | Expected | Share |")
    print("|---|---|---|---|")
    for i, (o, e) in enumerate(zip(counts, expected)):
        print(f"| {i} | {o:,} | {e:,.0f} | {o / total:.4%} |")
    print(f"\nchi2={chi2:.2f}, p={p:.2e}")
    if p < a.threshold:
        print(f"\n**SRM DETECTED (p < {a.threshold}).** Assignment or logging is broken. "
              "Do not interpret results until the cause is found (bot filtering, redirects, "
              "crashes or latency in one arm, caching, trigger logic).")
    else:
        print(f"\nNo SRM detected at p < {a.threshold}.")


# ---------------------------------------------------------------- analyze
def cmd_analyze(a):
    alpha = a.alpha
    zc = z(1 - alpha / 2)
    if a.metric == "proportion":
        (xc, nc), (xt, nt) = a.control, a.treatment
        xc, nc, xt, nt = int(xc), int(nc), int(xt), int(nt)
        pc, pt = xc / nc, xt / nt
        vc, vt = pc * (1 - pc) / nc, pt * (1 - pt) / nt
        diff = pt - pc
        se = math.sqrt(vc + vt)
        ppool = (xc + xt) / (nc + nt)
        se0 = math.sqrt(ppool * (1 - ppool) * (1 / nc + 1 / nt))
        zstat = diff / se0
        p = 2 * (1 - stats.norm.cdf(abs(zstat)))
        mc, mt = pc, pt
        label = lambda v: fmt_pct(v, 3)
        dlabel = lambda v: f"{v * 100:+.3f}pp"
    else:
        (mc, sdc, nc), (mt, sdt, nt) = a.control, a.treatment
        nc, nt = int(nc), int(nt)
        vc, vt = sdc ** 2 / nc, sdt ** 2 / nt
        diff = mt - mc
        se = math.sqrt(vc + vt)
        _, p = stats.ttest_ind_from_stats(mt, sdt, nt, mc, sdc, nc, equal_var=False)
        label = lambda v: f"{v:.4g}"
        dlabel = lambda v: f"{v:+.4g}"
    lo, hi = diff - zc * se, diff + zc * se
    # relative lift via delta method on ratio mt/mc
    r = mt / mc
    se_r = math.sqrt(vt / mc ** 2 + (mt ** 2) * vc / mc ** 4)
    rlo, rhi = r - 1 - zc * se_r, r - 1 + zc * se_r
    conf = int(round((1 - alpha) * 100))
    print("## Experiment result")
    print("| Arm | n | Metric |")
    print("|---|---|---|")
    print(f"| Control | {nc:,} | {label(mc)} |")
    print(f"| Treatment | {nt:,} | {label(mt)} |")
    print(f"\n- Absolute lift: **{dlabel(diff)}** ({conf}% CI {dlabel(lo)} to {dlabel(hi)})")
    print(f"- Relative lift: **{r - 1:+.2%}** ({conf}% CI {rlo:+.2%} to {rhi:+.2%})")
    print(f"- p-value (two-sided): {p:.4g}")
    sig = p < alpha
    print(f"- {'Statistically detectable' if sig else 'Not statistically detectable'} at alpha={alpha}.")
    print("\nBefore acting: confirm SRM passed, guardrails did not degrade, the analysis unit "
          "matches the randomization unit, and this was the pre-registered primary metric.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("power", help="sample size per arm")
    p.add_argument("--metric", choices=["proportion", "mean"], default="proportion")
    p.add_argument("--baseline", type=float, required=True, help="control rate (proportion) or mean")
    p.add_argument("--sd", type=float, help="standard deviation (mean metrics)")
    p.add_argument("--mde-abs", type=float, help="absolute MDE (e.g. 0.002 = 0.2pp)")
    p.add_argument("--mde-rel", type=float, help="relative MDE (e.g. 0.05 = 5%%)")
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--power", type=float, default=0.8)
    p.add_argument("--arms", type=int, default=2)
    p.add_argument("--daily-traffic", type=int, help="eligible units per day, to estimate duration")
    p.set_defaults(fn=cmd_power)

    p = sub.add_parser("mde", help="minimum detectable effect for a sample size")
    p.add_argument("--metric", choices=["proportion", "mean"], default="proportion")
    p.add_argument("--baseline", type=float, required=True)
    p.add_argument("--sd", type=float)
    p.add_argument("--n-per-arm", type=int, required=True)
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--power", type=float, default=0.8)
    p.set_defaults(fn=cmd_mde)

    p = sub.add_parser("srm", help="sample ratio mismatch test")
    p.add_argument("--counts", type=int, nargs="+", required=True)
    p.add_argument("--ratios", type=float, nargs="+", help="designed allocation (default equal)")
    p.add_argument("--threshold", type=float, default=0.001)
    p.set_defaults(fn=cmd_srm)

    p = sub.add_parser("analyze", help="lift and CI from summary stats")
    p.add_argument("--metric", choices=["proportion", "mean"], default="proportion")
    p.add_argument("--control", type=float, nargs="+", required=True,
                   help="proportion: conversions n | mean: mean sd n")
    p.add_argument("--treatment", type=float, nargs="+", required=True)
    p.add_argument("--alpha", type=float, default=0.05)
    p.set_defaults(fn=cmd_analyze)

    a = ap.parse_args()
    if a.cmd == "analyze":
        need = 2 if a.metric == "proportion" else 3
        if len(a.control) != need or len(a.treatment) != need:
            sys.exit(f"{a.metric} needs {need} values per arm")
    a.fn(a)


if __name__ == "__main__":
    main()
