"""profile_data.py must catch all 12 planted defects on pandas 2.x and 3.x."""
import sys

import pytest

from conftest import CORE_SCRIPTS, FIXTURES

sys.path.insert(0, str(CORE_SCRIPTS))
import profile_data  # noqa: E402


@pytest.fixture(scope="module")
def report(request):
    from conftest import run_script
    r = run_script(CORE_SCRIPTS / "profile_data.py", "--data", FIXTURES / "customers.csv", "--key", "customer_id",
                   "--target", "churned", "--time-col", "signup_date", "--today", "2026-09-28")
    return r.stdout


@pytest.mark.parametrize("col,needle", [
    ("region", "literal 'NA'"),                     # 1 NA = North America trap
    ("country", "case/whitespace variants"),        # 2
    ("income", "sentinel values -999"),             # 3
    ("signup_date", "placeholder dates"),           # 4
    ("signup_date", "future dates"),                # 5
    ("amount", "numeric values stored as text"),    # 6
    ("last_nps", "missingness predicts the target"),  # 7
    ("contact_email", "PII"),                       # 8
    ("phone", "PII"),                               # 8
    ("customer_id", "duplicate business keys"),     # 9
    ("(table)", "exact duplicate rows"),            # 10
    ("source_system", "constant column"),           # 11
    ("status", "case/whitespace variants"),         # 12
])
def test_planted_issue_detected(report, col, needle):
    lines = [l for l in report.splitlines() if l.startswith("|") and f"`{col}`" in l]
    assert any(needle in l for l in lines), f"missing {needle!r} for {col}:\n" + "\n".join(lines)


def test_no_false_positive_pii_on_dates(report):
    for l in report.splitlines():
        if "`signup_date`" in l:
            assert "look like phone" not in l


@pytest.mark.parametrize("name,expected", [
    ("cancellation_reason_code", False), ("contact_email", True), ("customerEmail", True),
    ("FirstName", True), ("zipper_count", False), ("latency_ms", False), ("user_name", True),
])
def test_pii_name_tokens(name, expected):
    assert profile_data.pii_name(name) is expected


def test_is_text_handles_string_dtypes():
    import pandas as pd
    assert profile_data.is_text(pd.Series(["a", "b"], dtype=object))
    assert profile_data.is_text(pd.Series(["a", "b"], dtype="string"))
    assert not profile_data.is_text(pd.Series([1, 2]))
    assert not profile_data.is_text(pd.Series([True, False]))
    assert not profile_data.is_text(pd.Series(["a", "b"], dtype="category"))
