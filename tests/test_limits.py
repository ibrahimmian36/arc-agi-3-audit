"""Run-level policies on the official client.

Every assertion is about the CLIENT. No test opens a socket: the remote wrapper
is driven with a transport that records attempts and raises.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIM = ROOT / "artifacts" / "limits"
sys.path.insert(0, str(ROOT / "scripts"))

import limits_probe as LP  # noqa: E402
import wire_probe as WP  # noqa: E402


def test_every_shipped_configuration_sets_the_same_limits():
    """A cutoff that varied between entrants would matter more than the cutoff
    itself. None of the twelve shipped configurations overrides the runtime
    limit or the animation cap, and all set the same action multiplier."""
    t = LP.limits_table()
    assert t["configs"] == 12
    assert t["distinct_values"]["runtime_seconds"] == ["None"], "a config overrides the runtime limit"
    assert t["distinct_values"]["animation_frames"] == ["None"]
    assert t["distinct_values"]["action_multiplier"] == ["5.0"]
    assert t["base_runtime_seconds"] == 12 * 60 * 60


def test_the_wall_clock_cutoff_exists_and_ends_a_run():
    r = WP.run(WP.SOLVE_L1, runtime_seconds=0.0)
    assert r["exit_reason"] == "TIME_BUDGET"
    assert r["harness_action_counter"] == 0 and r["environment_score"] == 0.0


def test_a_negative_limit_is_treated_as_expired_not_as_unlimited():
    r = WP.run(WP.SOLVE_L1, runtime_seconds=-1.0)
    assert r["exit_reason"] == "TIME_BUDGET"


def test_an_ample_limit_does_not_interfere():
    r = WP.run(WP.SOLVE_L1, runtime_seconds=3600.0)
    assert r["exit_reason"] != "TIME_BUDGET"
    assert r["harness_action_counter"] == 4


@pytest.mark.parametrize("mode", ["connection_error", "timeout_after_send",
                                  "server_error", "empty_ok"])
def test_one_intended_action_is_sent_exactly_once(mode):
    """The classic way a client inflates its own action count is to resend after
    a lost response. This one does not: every failure mode makes exactly one
    attempt. Whether the server would deduplicate is not observable and is not
    asserted."""
    rows = {r["mode"]: r for r in LP.resend_probes()}
    assert rows[mode]["attempts"] == 1


def test_a_failed_request_returns_nothing_rather_than_retrying():
    rows = {r["mode"]: r for r in LP.resend_probes()}
    for mode in ("connection_error", "timeout_after_send", "server_error"):
        assert rows[mode]["returned_none"] is True, mode


@pytest.mark.parametrize("produced,cap,expected", [
    (1, 7, 1), (3, 7, 3), (7, 7, 7), (8, 7, 7), (20, 7, 7), (20, 1, 1),
])
def test_the_frame_subsample_shows_at_most_the_cap(produced, cap, expected):
    rows = {(r["produced"], r["cap"]): r for r in LP.frame_probes()}
    if (produced, cap) not in rows:
        pytest.skip("combination not probed")
    assert rows[(produced, cap)]["shown"] == expected


def test_the_frame_subsample_always_keeps_the_last_frame():
    """It subsamples evenly rather than truncating, so the settled frame is
    always shown. That is materially different from dropping the end of an
    animation, and the difference decides whether this is a finding."""
    assert all(r["keeps_last"] for r in LP.frame_probes())


def test_probe_artefacts_are_reproducible(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    LP.main(["--out", str(a)]); LP.main(["--out", str(b)])
    assert (a / "limits.json").read_bytes() == (b / "limits.json").read_bytes()
    assert (a / "limits.log").read_bytes() == (b / "limits.log").read_bytes()


def test_committed_artefact_matches_the_script():
    d = json.loads((LIM / "limits.json").read_text())
    assert d["limits"]["configs"] == 12
    assert max(r["attempts"] for r in d["resend"]) == 1
    assert all(r["keeps_last"] for r in d["frames"])
