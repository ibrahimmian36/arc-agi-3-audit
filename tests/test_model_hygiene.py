"""The Dafny model carries no escape hatch and verifies with at least one obligation."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "model" / "scoring.dfy"
LOG = ROOT / "artifacts" / "oracle" / "check_model.log"


def test_no_escape_constructs():
    text = MODEL.read_text()
    for pat in ("assume", "{:axiom", "{:verify false", "{:extern", "expect "):
        assert pat not in text, pat


def test_check_model_passes_and_verified_count_positive():
    p = subprocess.run([str(ROOT / "scripts" / "check_model.sh")], capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stdout[-2000:]
    log = LOG.read_text()
    m = re.search(r"VERIFY_SUMMARY: verified=(\d+) errors=(\d+)", log)
    assert m and int(m.group(1)) > 0 and int(m.group(2)) == 0, log
    assert "MODEL CHECK: PASS" in log
