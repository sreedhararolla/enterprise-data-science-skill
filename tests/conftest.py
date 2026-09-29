import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
CORE_SCRIPTS = SKILLS / "enterprise-data-science" / "scripts"
EXP_SCRIPTS = SKILLS / "ds-experiment-mode" / "scripts"
FIXTURES = ROOT / "benchmark" / "fixtures"


def run_script(path, *args, cwd=None, check=True):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONWARNINGS="ignore")
    r = subprocess.run([sys.executable, str(path), *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8", cwd=cwd, env=env, timeout=600)
    if check and r.returncode != 0:
        raise AssertionError(f"{path.name} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r


@pytest.fixture
def run():
    return run_script
