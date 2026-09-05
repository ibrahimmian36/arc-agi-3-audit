"""The Dafny model carries no escape hatch and verifies with at least one obligation."""
import re
import subprocess

import pytest
from conftest import require_dafny, require_oracle
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "model" / "scoring.dfy"
LOG = ROOT / "artifacts" / "oracle" / "check_scoring.log"


def test_no_escape_constructs():
    text = MODEL.read_text()
    for pat in ("assume", "{:axiom", "{:verify false", "{:extern", "expect "):
        assert pat not in text, pat


@pytest.fixture(autouse=True)
def _tools_present():
    require_dafny(); require_oracle()


def test_check_model_passes_and_verified_count_positive():
    p = subprocess.run(["bash", str(ROOT / "scripts" / "check_model.sh")], capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stdout[-2000:]
    log = LOG.read_text()
    m = re.search(r"VERIFY_SUMMARY: verified=(\d+) errors=(\d+)", log)
    assert m and int(m.group(1)) > 0 and int(m.group(2)) == 0, log
    assert re.search(r"TIMEOUTS: 0", log), "a timed-out obligation is unknown, not discharged"
    assert "MODEL CHECK: PASS" in log
