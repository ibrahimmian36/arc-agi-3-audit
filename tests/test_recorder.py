"""Machinery checks M1-M8 (docs/PREREGISTRATION.md §2) on the toolkit's own
fixture game bt11. Assertions encode the engine semantics as read from
arcengine 0.9.3; a failure is left failing and documented."""
import json

import pytest
from conftest import FIXTURE_ENVS
from record_trace import run_script

SOLVE1 = ["ACTION3"] * 4
SOLVE_ALL = ["ACTION3"] * (4 + 8 + 16 + 20 + 24)


def run(actions, seed=0):
    return run_script(FIXTURE_ENVS, "bt11", actions, seed)


def test_m1_recorder_parity():
    r = run(["ACTION3", "ACTION3", "RESET"] + SOLVE1 + ["ACTION3", "ACTION3", "RESET"] + ["ACTION3"] * 8 + ["ACTION4"] * 6)
    assert r["ours"]["non_reset_actions"] == 22 and r["ours"]["resets"] == 2
    assert r["parity"]["counts_agree"], r["parity"]
    assert r["card"]["resets"] == [2]


def test_m2_reset_before_any_action_is_full():
    r = run(["RESET", "RESET"])
    assert r["steps"][1]["full_reset"] is True and r["steps"][2]["full_reset"] is True


def test_m3_level_reset_retains_progress():
    r = run(SOLVE1 + ["ACTION3", "ACTION3", "RESET"])
    last = r["steps"][-1]
    assert last["levels_completed"] == 1 and last["full_reset"] is False
    assert r["card"]["resets"] == [1] and r["card"]["levels_completed"] == [1]


def test_m4_reset_after_win_starts_new_play():
    r = run(SOLVE_ALL + ["RESET"])
    assert r["steps"][-2]["state"] == "WIN"
    assert r["steps"][-1]["full_reset"] is True and r["steps"][-1]["levels_completed"] == 0
    assert r["card"]["total_plays"] == 2


def test_m5_game_over_then_reset_is_level_reset():
    r = run(SOLVE1 + ["ACTION4"] * 8 + ["RESET"])  # level 2 is 16x16: losing takes 8 actions
    assert r["steps"][-2]["state"] == "GAME_OVER"
    last = r["steps"][-1]
    assert last["state"] == "NOT_FINISHED" and last["levels_completed"] == 1 and last["full_reset"] is False


def test_m6_unavailable_action_is_accepted_and_counted():
    r = run(["ACTION1", "ACTION2", "ACTION5"])
    assert all(s["state"] == "NOT_FINISHED" and s["levels_completed"] == 0 for s in r["steps"][1:])
    assert r["card"]["actions"] == [3]


def test_m7_never_solves_scores_zero():
    r = run((["ACTION4"] * 3 + ["RESET"]) * 7 + ["ACTION4", "ACTION4"])
    assert r["environment_score"]["score"] == 0.0
    assert r["card"]["levels_completed"] == [0]


def test_m8_byte_identity():
    script = ["ACTION3", "ACTION3", "RESET"] + SOLVE1 + ["ACTION4"] * 3
    a = json.dumps(run(script), sort_keys=True); b = json.dumps(run(script), sort_keys=True)
    assert a == b
