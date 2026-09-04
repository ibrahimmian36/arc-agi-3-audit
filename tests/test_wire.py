"""What the client puts on the wire, and what the local scorer charges for it.

Every assertion here is about the CLIENT. The server's treatment of any action
is not observable to this audit and is not asserted anywhere.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WIRE = ROOT / "artifacts" / "wire"
sys.path.insert(0, str(ROOT / "scripts"))

import wire_probe as WP  # noqa: E402


def test_the_ledger_reconciles_with_both_counters():
    """on_wire = construction + forced + chosen, and the harness's own counter
    equals forced + chosen. A difference the probe cannot explain would mean the
    ledger is wrong, not the harness."""
    r = WP.run(WP.LOSE_L1 * 3 + WP.SOLVE_L1)
    c = r["counts"]
    assert c["on_wire"] == c["construction"] + c["forced"] + c["chosen"]
    assert r["harness_action_counter"] == c["forced"] + c["chosen"]
    assert c["on_wire"] == r["harness_action_counter"] + 1


def test_the_construction_reset_is_on_the_wire_but_counted_by_neither():
    r = WP.run(WP.SOLVE_L1)
    assert r["counts"]["construction"] == 1
    assert r["counts"]["on_wire"] == 5
    assert r["harness_action_counter"] == 4
    assert r["card_actions"] == [4]


def test_a_forced_reset_is_counted_and_charged_to_the_level():
    """The harness resets after a game over. That reset is counted by the
    harness and charged by the local scorer to the level in progress."""
    clean = WP.run(WP.SOLVE_L1)
    once = WP.run(WP.LOSE_L1 + WP.SOLVE_L1)
    assert clean["counts"]["forced"] == 0
    assert once["counts"]["forced"] == 1
    assert once["counts"]["chosen"] == 8, "the agent chose eight actions"
    assert once["harness_action_counter"] == 9, "and was counted nine"
    assert once["card_resets"] == [1]
    assert once["level_actions"][0] == 9


def test_the_cost_of_forced_resets_scales_with_deaths():
    thrice = WP.run(WP.LOSE_L1 * 3 + WP.SOLVE_L1)
    assert thrice["counts"]["chosen"] == 16 and thrice["counts"]["forced"] == 3
    assert thrice["level_actions"][0] == 19
    # What the same play would score if the forced resets were not charged.
    baseline = 4
    charged = (baseline / 19) ** 2 * 100 / 15
    uncharged = (baseline / 16) ** 2 * 100 / 15
    assert thrice["environment_score"] == pytest.approx(charged, abs=1e-6)
    assert uncharged > thrice["environment_score"]


def test_a_level_advancing_on_the_last_permitted_action_is_not_cut_off():
    r = WP.run(WP.SOLVE_L1, budgets=[4, 40, 80, 100, 120])
    assert r["card_levels_completed"] == [1]
    assert r["environment_score"] == pytest.approx(100 / 15, abs=1e-6)


def test_a_budget_of_one_stops_after_one_action():
    r = WP.run(WP.SOLVE_L1, budgets=[1, 40, 80, 100, 120])
    assert r["harness_action_counter"] == 1 and r["exit_reason"] == "ACTION_BUDGET"
    assert r["environment_score"] == 0.0


def test_forced_resets_can_consume_a_small_budget():
    r = WP.run(WP.LOSE_L1 * 3 + WP.SOLVE_L1, budgets=[6, 40, 80, 100, 120])
    assert r["counts"]["forced"] >= 1
    assert r["exit_reason"] == "ACTION_BUDGET"


def test_a_game_over_on_the_last_permitted_action_exits_on_budget():
    r = WP.run(WP.LOSE_L1 + WP.SOLVE_L1, budgets=[4, 40, 80, 100, 120])
    assert r["exit_reason"] == "ACTION_BUDGET" and r["environment_score"] == 0.0


def test_a_retried_model_call_never_reaches_the_environment():
    """Measured two ways: the harness's retry loop contains no call that reaches
    the environment, and across every probe the number of environment calls
    equals the number of actions the harness counted."""
    iso = WP.retry_isolation()
    assert iso["isolated"] and iso["calls_reaching_the_environment"] == []
    for p in WP.probes():
        r = WP.run(p["script"], budgets=p.get("budgets"))
        assert r["take_action_calls"] == r["harness_action_counter"], p["id"]


def test_probe_artefacts_are_reproducible(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    WP.main(["--out", str(a)]); WP.main(["--out", str(b)])
    assert (a / "wire.json").read_bytes() == (b / "wire.json").read_bytes()
    assert (a / "wire.log").read_bytes() == (b / "wire.log").read_bytes()


def test_committed_artefact_matches_the_script():
    d = json.loads((WIRE / "wire.json").read_text())
    w3 = [r for r in d["probes"] if r["id"] == "W3"][0]
    assert w3["counts"]["forced"] == 3 and w3["counts"]["chosen"] == 16
    assert w3["harness_action_counter"] == 19
    assert d["retry"]["isolated"] is True
