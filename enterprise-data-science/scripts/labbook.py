#!/usr/bin/env python3
"""Lab notebook for autonomous work: Experiment Mode and Auto-Research Mode.

It keeps compact, persistent state so an agent can run for hours without re-reading its
whole history. Each iteration, run `state` (about 30 lines), act, then `log` or `hyp resolve`.

Protections built in:
  * Locked files (eval code, holdout, data prep) are SHA-256 fingerprinted at init.
    Any change is reported loudly, because an agent that "improves" the metric by editing
    the evaluator has improved nothing.
  * A noise-aware keep rule: an improvement must beat max(min_delta, combined seed std).
  * Simplicity pressure: more complexity must earn 2x the noise threshold, while a
    simpler change is kept if it is no worse than noise.
  * Guardrails (e.g. latency_ms<=50, fairness_gap<=0.05) must be reported and must pass.
  * Budgets (runs, hours) and plateau detection (no keep in `patience` runs).
  * The holdout may be scored once, after the search is frozen.

Commands
  init     --objective --metric --direction {max,min} [--min-delta] [--budget-runs]
           [--budget-hours] [--patience] [--guardrail "name<=v" ...] [--lock PATH ...]
           [--holdout PATH] [--mode {experiment,research}]
  log      --desc --metric [--std] [--status ok|crash|timeout] [--commit] [--parent]
           [--complexity simpler|same|more] [--extra k=v ...] [--minutes] [--tags]
           [--decision keep|discard --reason "..."]   (manual override, recorded as such)
  idea     add TEXT [--priority 1-5] [--source URL/ref] | list | done ID [--run RID] | drop ID
  hyp      add TEXT --prediction "..." --test "..." [--prior high|med|low] [--impact high|med|low]
           | resolve ID --verdict supported|refuted|inconclusive --evidence "..." | list
  note     TEXT
  state    [--last N]      compact summary to read at the start of every iteration
  verify                   re-check locked-file fingerprints
  holdout  --metric V [--extra k=v ...]   one-time final holdout score
  report                   full Markdown report

The notebook is stored at ./labbook.json (override with --book or the LABBOOK env var),
and results.tsv is mirrored next to it for humans.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8")

GUARD_RE = re.compile(r"^\s*([A-Za-z_][\w.]*)\s*(<=|>=|<|>|==)\s*(-?[\d.eE+-]+)\s*$")
OPS = {"<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b,
       ">": lambda a, b: a > b, "==": lambda a, b: a == b}


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def sha256(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    if os.path.isdir(path):
        for root, _, files in sorted(os.walk(path)):
            for f in sorted(files):
                p = os.path.join(root, f)
                h.update(os.path.relpath(p, path).encode())
                with open(p, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
    else:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


def book_path(a):
    return a.book or os.environ.get("LABBOOK", "labbook.json")


def load(a):
    p = book_path(a)
    if not os.path.exists(p):
        sys.exit(f"No lab book at {p}. Run `labbook.py init ...` first.")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save(a, b):
    p = book_path(a)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(b, fh, indent=1)
    os.replace(tmp, p)
    tsv = os.path.join(os.path.dirname(os.path.abspath(p)), "results.tsv")
    with open(tsv, "w", encoding="utf-8") as fh:
        fh.write("run\tts\tcommit\tmetric\tstd\tstatus\tdecision\tcomplexity\tdesc\n")
        for r in b["runs"]:
            fh.write(f"{r['id']}\t{r['ts']}\t{r.get('commit') or ''}\t{fmt(r.get('metric'))}\t"
                     f"{fmt(r.get('std'))}\t{r['status']}\t{r['decision']}\t{r.get('complexity', '')}\t"
                     f"{r['desc'].replace(chr(9), ' ')}\n")


def fmt(x, d=5):
    if x is None:
        return ""
    return f"{x:.{d}g}" if isinstance(x, (int, float)) else str(x)


def parse_extras(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            sys.exit(f"--extra expects key=value, got {it!r}")
        k, v = it.split("=", 1)
        try:
            out[k] = float(v)
        except ValueError:
            out[k] = v
    return out


def best_run(b):
    return next((r for r in b["runs"] if r["id"] == b.get("best")), None)


def lock_status(b):
    bad = []
    for lk in b["config"]["locks"]:
        cur = sha256(lk["path"])
        if cur != lk["sha256"]:
            bad.append((lk["path"], "missing" if cur is None else "modified"))
    return bad


def lock_warning(b):
    bad = lock_status(b)
    if bad:
        lines = ["", "!!! LOCKED FILES CHANGED — results since the change are NOT comparable !!!"]
        lines += [f"    {p}: {s}" for p, s in bad]
        lines += ["    Restore them (git checkout -- <file>) before continuing. Never edit the evaluator."]
        return "\n".join(lines)
    return ""


def budget_status(b):
    c = b["config"]
    n = len(b["runs"])
    hours = (dt.datetime.now() - dt.datetime.fromisoformat(c["created"])).total_seconds() / 3600
    msgs = []
    exhausted = False
    if c.get("budget_runs"):
        msgs.append(f"runs {n}/{c['budget_runs']}")
        exhausted |= n >= c["budget_runs"]
    if c.get("budget_hours"):
        msgs.append(f"hours {hours:.1f}/{c['budget_hours']}")
        exhausted |= hours >= c["budget_hours"]
    return ", ".join(msgs) or f"runs {n} (no budget set)", exhausted


def since_last_keep(b):
    k = 0
    for r in reversed(b["runs"]):
        if r["decision"] in ("keep", "baseline"):
            break
        k += 1
    return k


# ------------------------------------------------------------------ commands
def cmd_init(a):
    p = book_path(a)
    if os.path.exists(p) and not a.force:
        sys.exit(f"{p} already exists. Use --force to overwrite, or --book to start another notebook.")
    guards = []
    for g in a.guardrail or []:
        m = GUARD_RE.match(g)
        if not m:
            sys.exit(f"Bad guardrail {g!r}; use e.g. 'latency_ms<=50'")
        guards.append({"name": m.group(1), "op": m.group(2), "value": float(m.group(3))})
    locks = []
    for path in (a.lock or []) + ([a.holdout] if a.holdout else []):
        h = sha256(path)
        if h is None:
            sys.exit(f"Cannot lock {path}: not found")
        locks.append({"path": os.path.abspath(path), "sha256": h})
    b = {
        "config": {
            "mode": a.mode, "objective": a.objective, "metric": a.metric, "direction": a.direction,
            "min_delta": a.min_delta, "budget_runs": a.budget_runs, "budget_hours": a.budget_hours,
            "patience": a.patience, "guardrails": guards, "locks": locks,
            "holdout": {"path": os.path.abspath(a.holdout) if a.holdout else None, "used": False, "result": None} if a.holdout else None,
            "created": now(),
        },
        "runs": [], "ideas": [], "hyps": [], "notes": [], "best": None,
    }
    save(a, b)
    print(f"Initialized {p} ({a.mode} mode). Objective: {a.objective}")
    print(f"Metric: {a.metric} ({a.direction}), min_delta={a.min_delta}, guardrails={[g['name'] + g['op'] + str(g['value']) for g in guards]}")
    print(f"Locked {len(locks)} file(s). Next: log a baseline run (ideally 3 seeds, with --std).")


def cmd_log(a):
    b = load(a)
    c = b["config"]
    sign = 1 if c["direction"] == "max" else -1
    extras = parse_extras(a.extra)
    rid = f"r{len(b['runs']) + 1:03d}"
    run = {"id": rid, "ts": now(), "desc": a.desc, "metric": a.metric, "std": a.std, "status": a.status,
           "commit": a.commit, "parent": a.parent or b.get("best"), "complexity": a.complexity,
           "extras": extras, "minutes": a.minutes, "tags": a.tags.split(",") if a.tags else []}
    best = best_run(b)
    reason = ""
    locks_bad = lock_status(b)

    if a.status != "ok" or a.metric is None:
        decision, reason = "crash", f"status={a.status}"
    elif locks_bad:
        decision, reason = "discard", "locked files changed; result not comparable"
    else:
        failed = []
        for g in c["guardrails"]:
            v = extras.get(g["name"])
            if not isinstance(v, (int, float)):
                failed.append(f"{g['name']} not reported")
            elif not OPS[g["op"]](v, g["value"]):
                failed.append(f"{g['name']}={v:g} violates {g['op']}{g['value']:g}")
        if failed:
            decision, reason = "discard", "guardrail: " + "; ".join(failed)
        elif best is None:
            decision, reason = "baseline", "first valid run"
        else:
            delta = (a.metric - best["metric"]) * sign
            stds = [s for s in (a.std, best.get("std")) if s]
            noise = math.sqrt(sum(s * s for s in stds)) if stds else 0.0
            thr = max(c["min_delta"], noise)
            if a.complexity == "simpler":
                ok, need = delta >= -thr, f">= -{thr:.4g} (simpler: may tie)"
            elif a.complexity == "more":
                ok, need = delta > 2 * thr, f"> {2 * thr:.4g} (more complex: needs 2x noise)"
            else:
                ok, need = delta > thr, f"> {thr:.4g}"
            decision = "keep" if ok else "discard"
            reason = f"Δ={delta:+.4g} vs best {best['id']} ({fmt(best['metric'])}); needed {need}"
    if a.decision:
        if not a.reason:
            sys.exit("--decision override requires --reason")
        reason = f"OVERRIDE {decision}->{a.decision}: {a.reason} | auto: {reason}"
        decision = a.decision
    run["decision"], run["reason"] = decision, reason
    b["runs"].append(run)
    if decision in ("keep", "baseline"):
        b["best"] = rid
    save(a, b)

    best = best_run(b)
    print(f"{rid}: {decision.upper()} — {reason}")
    if decision in ("keep", "baseline"):
        print(f"  New best {rid} = {fmt(a.metric)}. Keep this commit and build on it.")
    elif best:
        if best.get("commit"):
            print(f"  Revert to best ({best['id']}, {fmt(best['metric'])}): `git reset --hard {best['commit']}`")
        else:
            print(f"  Revert to the state of best run {best['id']} ({fmt(best['metric'])}). "
                  "Tip: pass --commit <sha> when logging so reverts are one git command.")
    bs, exhausted = budget_status(b)
    print(f"  Budget: {bs}")
    stall = since_last_keep(b)
    if exhausted:
        print("  BUDGET EXHAUSTED → stop searching, run the confirmation step, score the holdout once, write the report.")
    elif stall >= c["patience"]:
        print(f"  PLATEAU: {stall} runs without a keep → change strategy (see experiment-mode.md §Plateau) or stop.")
    w = lock_warning(b)
    if w:
        print(w)


def cmd_idea(a):
    b = load(a)
    if a.action == "add":
        iid = f"i{len(b['ideas']) + 1:03d}"
        b["ideas"].append({"id": iid, "text": a.text, "priority": a.priority, "source": a.source,
                           "status": "open", "ts": now(), "run": None})
        print(f"{iid} added (priority {a.priority})")
    elif a.action in ("done", "drop"):
        it = next((i for i in b["ideas"] if i["id"] == a.text), None)
        if not it:
            sys.exit(f"No idea {a.text}")
        it["status"] = "done" if a.action == "done" else "dropped"
        it["run"] = a.run
        print(f"{it['id']} → {it['status']}")
    else:
        for i in sorted(b["ideas"], key=lambda i: (i["status"] != "open", -i["priority"])):
            print(f"{i['id']} [{i['status']}] p{i['priority']} {i['text']}" + (f"  ({i['source']})" if i.get("source") else ""))
        return
    save(a, b)


def cmd_hyp(a):
    b = load(a)
    if a.action == "add":
        if not (a.prediction and a.test):
            sys.exit("hyp add needs --prediction (what you'd see if true) and --test (how to check)")
        hid = f"h{len(b['hyps']) + 1:03d}"
        b["hyps"].append({"id": hid, "text": a.text, "prediction": a.prediction, "test": a.test,
                          "prior": a.prior, "impact": a.impact, "parent": a.parent, "status": "open",
                          "evidence": None, "ts": now()})
        print(f"{hid} added")
    elif a.action == "resolve":
        h = next((h for h in b["hyps"] if h["id"] == a.text), None)
        if not h:
            sys.exit(f"No hypothesis {a.text}")
        if not (a.verdict and a.evidence):
            sys.exit("resolve needs --verdict and --evidence")
        h.update(status=a.verdict, evidence=a.evidence, resolved=now())
        print(f"{h['id']} → {a.verdict}")
    else:
        for h in b["hyps"]:
            print(f"{h['id']} [{h['status']}] prior={h['prior']} impact={h['impact']} {h['text']}")
            print(f"    predicts: {h['prediction']} | test: {h['test']}" + (f" | evidence: {h['evidence']}" if h['evidence'] else ""))
        return
    save(a, b)


def cmd_note(a):
    b = load(a)
    b["notes"].append({"ts": now(), "text": a.text})
    save(a, b)
    print("noted")


def cmd_state(a):
    b = load(a)
    c = b["config"]
    best = best_run(b)
    bs, exhausted = budget_status(b)
    runs = b["runs"]
    print(f"# Lab state ({c['mode']} mode) — {c['objective']}")
    print(f"Metric **{c['metric']}** ({c['direction']}) · min_delta {c['min_delta']} · budget {bs}"
          + (" · **EXHAUSTED**" if exhausted else ""))
    if c["guardrails"]:
        print("Guardrails: " + ", ".join(f"{g['name']}{g['op']}{g['value']:g}" for g in c["guardrails"]))
    if best:
        print(f"Best: **{best['id']} = {fmt(best['metric'])}**" + (f" ± {fmt(best['std'])}" if best.get("std") else "")
              + f" — {best['desc']}" + (f" (commit {best['commit']})" if best.get("commit") else ""))
        base = next((r for r in runs if r["decision"] == "baseline"), None)
        if base and base is not best:
            gain = (best["metric"] - base["metric"]) * (1 if c["direction"] == "max" else -1)
            print(f"Gain over baseline {base['id']}: {gain:+.4g}")
    counts = {k: sum(r["decision"] == k for r in runs) for k in ("keep", "discard", "crash")}
    print(f"Runs: {len(runs)} (keep {counts['keep']}, discard {counts['discard']}, crash {counts['crash']}); "
          f"since last keep: {since_last_keep(b)} (patience {c['patience']})")
    if runs:
        print(f"\nLast {min(a.last, len(runs))} runs:")
        for r in runs[-a.last:]:
            print(f"  {r['id']} {r['decision']:<8} {fmt(r.get('metric')):>9}  {r['desc'][:70]}")
    tried = [r["desc"][:60] for r in runs if r["decision"] in ("discard", "crash")][-12:]
    if tried:
        print("\nTried and rejected (don't repeat without a new angle): " + " | ".join(tried))
    open_ideas = sorted([i for i in b["ideas"] if i["status"] == "open"], key=lambda i: -i["priority"])[:6]
    if open_ideas:
        print("\nTop open ideas: " + " | ".join(f"{i['id']} p{i['priority']} {i['text'][:60]}" for i in open_ideas))
    hyps = b["hyps"]
    if hyps:
        st = {k: sum(h["status"] == k for h in hyps) for k in ("open", "supported", "refuted", "inconclusive")}
        print(f"\nHypotheses: {st}")
        rank = {"high": 3, "med": 2, "low": 1}
        for h in sorted([h for h in hyps if h["status"] == "open"],
                        key=lambda h: -(rank.get(h["prior"], 2) * rank.get(h["impact"], 2)))[:5]:
            print(f"  open {h['id']} ({h['prior']}/{h['impact']}): {h['text'][:80]}")
        for h in [h for h in hyps if h["status"] == "supported"][-4:]:
            print(f"  ✔ {h['id']}: {h['text'][:60]} — {str(h['evidence'])[:80]}")
    if b["notes"]:
        print("\nLatest notes: " + " | ".join(n["text"][:80] for n in b["notes"][-3:]))
    ho = c.get("holdout")
    if ho:
        print(f"\nHoldout: {'USED → ' + fmt(ho['result']['metric']) if ho['used'] else 'untouched (score once, at the end)'}")
    w = lock_warning(b)
    print(w if w else "\nLocks: OK")


def cmd_verify(a):
    b = load(a)
    w = lock_warning(b)
    print(w if w else f"All {len(b['config']['locks'])} locked file(s) unchanged.")
    sys.exit(1 if w else 0)


def cmd_holdout(a):
    b = load(a)
    ho = b["config"].get("holdout")
    if not ho:
        sys.exit("No holdout configured at init.")
    if lock_status(b):
        sys.exit(lock_warning(b))
    if a.force and not a.reason:
        sys.exit("--force requires --reason (it is recorded in the report).")
    if ho["used"] and not a.force:
        sys.exit(f"Holdout already used ({fmt(ho['result']['metric'])} at {ho['result']['ts']}). Re-scoring it turns it into a "
                 "validation set. Use --force --reason only with a documented justification.")
    best = best_run(b)
    ho.update(used=True, result={"metric": a.metric, "extras": parse_extras(a.extra), "ts": now(),
                                 "best_run": best["id"] if best else None,
                                 "forced_reason": a.reason if a.force else None})
    save(a, b)
    if best:
        gap = (a.metric - best["metric"]) * (1 if b["config"]["direction"] == "max" else -1)
        print(f"Holdout {b['config']['metric']} = {fmt(a.metric)} vs validation {fmt(best['metric'])} (gap {gap:+.4g}).")
        thr = max(b["config"]["min_delta"], best.get("std") or 0) * 3
        if gap < -thr:
            print("Holdout is materially worse than validation → likely overfit to the validation set through "
                  "many comparisons, or distribution shift. Report the holdout number, not the validation number.")
        else:
            print("Holdout is consistent with validation.")


def cmd_report(a):
    b = load(a)
    c = b["config"]
    best = best_run(b)
    print(f"# Lab report — {c['objective']}\n")
    print(f"- Mode: {c['mode']} · Metric: {c['metric']} ({c['direction']}) · Started {c['created']}")
    print(f"- Budget used: {budget_status(b)[0]}")
    if best:
        print(f"- **Best: {best['id']} = {fmt(best['metric'])}** — {best['desc']}")
    ho = c.get("holdout")
    if ho and ho["used"]:
        print(f"- **Holdout (scored once): {fmt(ho['result']['metric'])}**")
    w = lock_warning(b)
    print(f"- Locked-file integrity: {'FAILED' + w if w else 'OK'}\n")
    keeps = [r for r in b["runs"] if r["decision"] in ("baseline", "keep")]
    if keeps:
        print("## Improvement path")
        print("| Run | Metric | Change |\n|---|---|---|")
        for r in keeps:
            print(f"| {r['id']} | {fmt(r['metric'])} | {r['desc']} |")
    if b["runs"]:
        print("\n## All runs")
        print("| Run | Decision | Metric | Std | Complexity | Description | Reason |\n|---|---|---|---|---|---|---|")
        for r in b["runs"]:
            print(f"| {r['id']} | {r['decision']} | {fmt(r.get('metric'))} | {fmt(r.get('std'))} | {r.get('complexity', '')} | "
                  f"{r['desc']} | {r['reason']} |")
    if b["hyps"]:
        print("\n## Hypotheses")
        print("| ID | Status | Hypothesis | Prediction | Evidence |\n|---|---|---|---|---|")
        for h in b["hyps"]:
            print(f"| {h['id']} | {h['status']} | {h['text']} | {h['prediction']} | {h['evidence'] or ''} |")
    if b["ideas"]:
        print("\n## Idea backlog")
        for i in b["ideas"]:
            print(f"- {i['id']} [{i['status']}] p{i['priority']} {i['text']}" + (f" — {i['source']}" if i.get("source") else ""))
    if b["notes"]:
        print("\n## Notes")
        for n in b["notes"]:
            print(f"- {n['ts']}: {n['text']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", help="path to labbook.json (default ./labbook.json or $LABBOOK)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--objective", required=True)
    p.add_argument("--metric", required=True)
    p.add_argument("--direction", choices=["max", "min"], required=True)
    p.add_argument("--mode", choices=["experiment", "research"], default="experiment")
    p.add_argument("--min-delta", type=float, default=0.0, help="smallest improvement worth keeping (set from seed noise)")
    p.add_argument("--budget-runs", type=int)
    p.add_argument("--budget-hours", type=float)
    p.add_argument("--patience", type=int, default=10)
    p.add_argument("--guardrail", action="append")
    p.add_argument("--lock", action="append", help="file/dir that must not change (eval code, data prep)")
    p.add_argument("--holdout", help="holdout file/dir (locked, scored once)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("log")
    p.add_argument("--desc", required=True)
    p.add_argument("--metric", type=float)
    p.add_argument("--std", type=float, help="std across seeds/folds for this run")
    p.add_argument("--status", choices=["ok", "crash", "timeout"], default="ok")
    p.add_argument("--commit")
    p.add_argument("--parent")
    p.add_argument("--complexity", choices=["simpler", "same", "more"], default="same")
    p.add_argument("--extra", nargs="*", help="key=value (guardrail metrics, secondary metrics)")
    p.add_argument("--minutes", type=float)
    p.add_argument("--tags")
    p.add_argument("--decision", choices=["keep", "discard"], help="manual override (needs --reason)")
    p.add_argument("--reason")
    p.set_defaults(fn=cmd_log)

    p = sub.add_parser("idea")
    p.add_argument("action", choices=["add", "list", "done", "drop"])
    p.add_argument("text", nargs="?")
    p.add_argument("--priority", type=int, default=3)
    p.add_argument("--source")
    p.add_argument("--run")
    p.set_defaults(fn=cmd_idea)

    p = sub.add_parser("hyp")
    p.add_argument("action", choices=["add", "resolve", "list"])
    p.add_argument("text", nargs="?")
    p.add_argument("--prediction")
    p.add_argument("--test")
    p.add_argument("--prior", choices=["high", "med", "low"], default="med")
    p.add_argument("--impact", choices=["high", "med", "low"], default="med")
    p.add_argument("--parent")
    p.add_argument("--verdict", choices=["supported", "refuted", "inconclusive"])
    p.add_argument("--evidence")
    p.set_defaults(fn=cmd_hyp)

    p = sub.add_parser("note")
    p.add_argument("text")
    p.set_defaults(fn=cmd_note)

    p = sub.add_parser("state")
    p.add_argument("--last", type=int, default=8)
    p.set_defaults(fn=cmd_state)

    p = sub.add_parser("verify")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("holdout")
    p.add_argument("--metric", type=float, required=True)
    p.add_argument("--extra", nargs="*")
    p.add_argument("--force", action="store_true")
    p.add_argument("--reason")
    p.set_defaults(fn=cmd_holdout)

    p = sub.add_parser("report")
    p.set_defaults(fn=cmd_report)

    a = ap.parse_args()
    if a.cmd in ("idea", "hyp") and a.action != "list" and not a.text:
        sys.exit(f"{a.cmd} {a.action} needs TEXT/ID")
    a.fn(a)


if __name__ == "__main__":
    main()
