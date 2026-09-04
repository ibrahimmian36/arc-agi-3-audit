"""Harness cutoff probes H1-H6 (plus H1b) run to completion, never execute more actions on a
level than the documented 5x budget, and are byte-identical on re-run."""
import json

import pytest
from conftest import FIXTURE_ENVS
from harness_probe import probes, run_probe


@pytest.fixture(scope="module")
def results():
    return {p["id"]: (run_probe(FIXTURE_ENVS, "bt11", p), run_probe(FIXTURE_ENVS, "bt11", p)) for p in probes()}


def test_all_probes_terminate_with_a_reason(results):
    for pid, (r, _) in results.items():
        h = r["harness"]
        if h["error"]:
            # AGENT_ERROR here is the probe stub running out of script, not a harness failure.
            assert h["error"].startswith("script exhausted") and h["exit_reason"] == "AGENT_ERROR", (pid, h)
        else:
            assert h["exit_reason"] in ("ACTION_BUDGET", "GAME_WIN"), (pid, h)


def test_no_level_exceeds_documented_budget(results):
    for pid, (r, _) in results.items():
        assert not r["any_level_over_budget"], (pid, r["per_level_executed"])


def test_byte_identity(results):
    for pid, (a, b) in results.items():
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), pid
