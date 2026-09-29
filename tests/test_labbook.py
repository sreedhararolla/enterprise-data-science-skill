"""labbook.py: keep/discard rules, guardrails, tamper detection, one-time holdout, safe git advice."""
from conftest import EXP_SCRIPTS

LB = EXP_SCRIPTS / "labbook.py"


def test_lifecycle(tmp_path, run):
    (tmp_path / "evaluate.py").write_bytes(b"print(1)\n")
    (tmp_path / "hold.csv").write_bytes(b"a\n1\n")
    run(LB, "init", "--objective", "t", "--metric", "auc", "--direction", "max", "--min-delta", "0.01",
        "--budget-runs", "6", "--patience", "2", "--guardrail", "latency_ms<=50",
        "--lock", "evaluate.py", "--holdout", "hold.csv", cwd=tmp_path)
    log = lambda *a: run(LB, "log", *a, cwd=tmp_path).stdout  # noqa: E731
    assert "BASELINE" in log("--desc", "base", "--metric", "0.80", "--std", "0.004", "--commit", "aaa1111",
                             "--extra", "latency_ms=5")
    out = log("--desc", "noise", "--metric", "0.805", "--std", "0.004", "--commit", "bbb2222", "--extra", "latency_ms=5")
    assert "DISCARD" in out and "git revert --no-edit bbb2222" in out
    assert "reset --hard" not in out
    assert "KEEP" in log("--desc", "real gain", "--metric", "0.83", "--std", "0.004", "--commit", "ccc3333",
                         "--extra", "latency_ms=5")
    assert "guardrail" in log("--desc", "slow", "--metric", "0.9", "--std", "0.004", "--extra", "latency_ms=90")
    assert "DISCARD" in log("--desc", "more complex small gain", "--metric", "0.842", "--std", "0.004",
                            "--complexity", "more", "--extra", "latency_ms=5")
    # tamper with the locked evaluator -> results discarded
    (tmp_path / "evaluate.py").write_bytes(b"print(2)\n")
    out = log("--desc", "after tamper", "--metric", "0.99", "--std", "0.001", "--extra", "latency_ms=1")
    assert "locked files changed" in out and "reset --hard" not in out and "checkout --" not in out
    (tmp_path / "evaluate.py").write_bytes(b"print(1)\n")
    # verify works from another working directory (absolute lock paths)
    sub = tmp_path / "sub"
    sub.mkdir()
    r = run(LB, "--book", tmp_path / "labbook.json", "verify", cwd=sub)
    assert "unchanged" in r.stdout
    # holdout exactly once; forcing requires a reason
    assert "Holdout auc" in run(LB, "holdout", "--metric", "0.82", cwd=tmp_path).stdout
    assert run(LB, "holdout", "--metric", "0.9", cwd=tmp_path, check=False).returncode != 0
    assert run(LB, "holdout", "--metric", "0.9", "--force", cwd=tmp_path, check=False).returncode != 0
    report = run(LB, "report", cwd=tmp_path).stdout
    assert "Improvement path" in report and "Locked-file integrity: OK" in report


def test_research_hypotheses(tmp_path, run):
    run(LB, "init", "--mode", "research", "--objective", "why", "--metric", "explained_share",
        "--direction", "max", cwd=tmp_path)
    run(LB, "hyp", "add", "price change drove churn", "--prediction", "concentrated in repriced plans",
        "--test", "churn by plan", "--prior", "high", "--impact", "high", cwd=tmp_path)
    run(LB, "hyp", "resolve", "h001", "--verdict", "supported", "--evidence", "+3.9pp vs +0.2pp", cwd=tmp_path)
    assert "supported" in run(LB, "state", cwd=tmp_path).stdout
