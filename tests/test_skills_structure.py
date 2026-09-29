"""Every skill follows the Agent Skills spec; duplicated scripts stay identical; no destructive git advice."""
import re
import subprocess
import sys

import pytest

from conftest import ROOT, SKILLS

yaml = pytest.importorskip("yaml")
SKILL_DIRS = sorted(p for p in SKILLS.iterdir() if p.is_dir())


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no YAML frontmatter"
    return yaml.safe_load(m.group(1)), text


def test_expected_skills():
    assert [p.name for p in SKILL_DIRS] == ["ds-auto-research", "ds-experiment-mode", "enterprise-data-science"]


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda p: p.name)
def test_frontmatter_spec(skill):
    fm, text = frontmatter(skill / "SKILL.md")
    assert fm["name"] == skill.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fm["name"]) and len(fm["name"]) <= 64
    assert 1 <= len(fm["description"]) <= 1024
    assert len(fm.get("compatibility", "")) <= 500
    assert fm.get("license") == "MIT"
    assert text.count("\n") < 500, "keep SKILL.md under 500 lines"


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda p: p.name)
def test_referenced_files_exist(skill):
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    for ref in set(re.findall(r"`((?:scripts|references|assets)/[\w.\-]+)`", text)):
        assert (skill / ref).exists(), f"{skill.name}/SKILL.md references missing {ref}"


def test_shared_scripts_identical():
    core = SKILLS / "enterprise-data-science" / "scripts"
    exp = SKILLS / "ds-experiment-mode" / "scripts"
    res = SKILLS / "ds-auto-research" / "scripts"
    for name in ("leakage_scan.py", "eval_report.py"):
        assert (core / name).read_bytes() == (exp / name).read_bytes(), f"{name} copies diverged"
    assert (exp / "labbook.py").read_bytes() == (res / "labbook.py").read_bytes()
    assert (SKILLS / "ds-experiment-mode/assets/program_template.md").read_bytes() == \
        (SKILLS / "ds-auto-research/assets/program_template.md").read_bytes()


def test_no_destructive_git_advice():
    bad = re.compile(r"reset --hard|git clean -f|checkout -- \.|push --force|push -f")
    prohibit = re.compile(r"never|Never|don't|Don't|not suggest")
    for f in list(SKILLS.rglob("*.md")) + list(SKILLS.rglob("*.py")):
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if bad.search(line):
                context = " ".join(lines[max(0, i - 1):i + 1])  # prohibitions may wrap onto the previous line
                assert prohibit.search(context), f"{f}:{i + 1} recommends: {line.strip()}"


@pytest.mark.parametrize("script", sorted(SKILLS.rglob("scripts/*.py")), ids=lambda p: f"{p.parent.parent.name}/{p.name}")
def test_script_help(script):
    r = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
