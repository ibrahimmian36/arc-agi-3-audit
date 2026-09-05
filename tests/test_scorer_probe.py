"""Scorer probes run, are byte-identical on re-run, and reproduce the toolkit's
own unit-test expectations where they overlap. Disagreements with the oracle are
findings (read in FINDINGS.md), not test failures."""
import json
from pathlib import Path

import pytest
from conftest import require_oracle
from scorer_probe import main as probe_main

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory):
    a = tmp_path_factory.mktemp("run_a"); b = tmp_path_factory.mktemp("run_b")
    probe_main(["--out", str(a)]); probe_main(["--out", str(b)])
    return a, b


@pytest.fixture(autouse=True)
def _oracle_present():
    require_oracle()


def test_byte_identical(two_runs):
    a, b = two_runs
    for name in ("fixtures.json", "probes.json", "probes.log"):
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_oracle_loaded_and_all_probes_present(two_runs):
    d = json.loads((two_runs[0] / "probes.json").read_text())
    assert d["summary"]["oracle_loaded"] is True, d["summary"]
    assert d["summary"]["probes"] == 14
    ids = {r["id"] for r in d["rows"]}
    assert ids == {"P1", "P2a", "P2b", "P2c", "P3a", "P3b", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"}


def test_shipped_matches_toolkit_own_expectations(two_runs):
    """vendor/ARC-AGI/tests/test_scorecard.py: exact baseline -> 100; a level 8
    actions vs baseline 10 is capped at 115; 1 of 6 levels at baseline -> 100/21."""
    d = {r["id"]: r for r in json.loads((two_runs[0] / "probes.json").read_text())["rows"]}
    assert d["P1"]["shipped"]["score"] == pytest.approx(100.0)
    assert d["P2a"]["shipped"]["best_run"]["level_scores"][0] == pytest.approx(115.0)
    assert d["P5"]["shipped"]["score"] == pytest.approx(100 / 15, abs=1e-6)  # 1-based weights (initial brief Lead 2)
