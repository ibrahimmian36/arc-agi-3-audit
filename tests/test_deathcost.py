"""Can a level be lost inside its own budget, under actions it advertises?

This is the precondition for the forced-reset denial, and it is a one-sided
measurement: random play cannot beat the true shortest losing line, so a bound
below the budget proves the level can be lost inside it, while finding no bound
proves nothing at all. These tests exist to keep that reading honest and to
exercise the boundaries where it could be got wrong.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

ART = ROOT / "artifacts" / "deathcost" / "deathcost.json"
GRID_MAX = 63


@pytest.fixture(scope="module")
def levels() -> list:
    if not ART.exists():
        pytest.skip("run scripts/death_cost.py --all-levels first")
    return json.loads(ART.read_text())["levels"]


def test_every_level_of_every_public_environment_is_covered(levels):
    api = json.loads((ROOT / "artifacts" / "api" / "games.json").read_text())
    want = {(g["game_id"][:4], i + 1) for g in api
            for i in range(len(g["baseline_actions"]))}
    got = {(r["game"], r["level"]) for r in levels}
    assert got == want
    assert len(want) == 183


def test_budgets_follow_the_published_baseline(levels):
    api = {g["game_id"][:4]: g["baseline_actions"]
           for g in json.loads((ROOT / "artifacts" / "api" / "games.json").read_text())}
    for r in levels:
        if r.get("error"):
            continue
        assert r["baseline"] == api[r["game"]][r["level"] - 1]
        assert r["budget"] == math.ceil(r["baseline"] * 5.0)


# ── the correction this phase exists for ────────────────────────────────────

def test_no_losing_line_uses_an_action_the_environment_does_not_advertise(levels):
    """The defect in our own earlier measurement: it sampled actions 1-4 for
    every environment, including six that advertise only a click. A line of
    actions an agent is not told it may take is not a played loss."""
    for r in levels:
        if r.get("error") or not r.get("losing_line"):
            continue
        assert r["unadvertised_actions_in_line"] == 0, (r["game"], r["level"])
        adv = set(r["advertised_actions"])
        assert all(step[0] in adv for step in r["losing_line"]), (r["game"], r["level"])


def test_click_coordinates_stay_inside_the_declared_contract(levels):
    """ComplexAction declares x and y in 0..63; a probe outside that is testing
    something the environment never promised to accept."""
    for r in levels:
        for step in r.get("losing_line") or []:
            if len(step) == 3:
                assert 0 <= step[1] <= GRID_MAX and 0 <= step[2] <= GRID_MAX, r["game"]


def test_click_lines_are_recorded_with_their_coordinates(levels):
    """A click line replays only if the coordinates are kept. Any environment
    that advertises a click and produced a line must have recorded some."""
    for r in levels:
        line = r.get("losing_line")
        if not line or 6 not in set(r["advertised_actions"]):
            continue
        if any(step[0] == 6 for step in line):
            assert r["clicks_in_line"] == sum(1 for s in line if len(s) == 3) > 0


# ── the one-sided reading ───────────────────────────────────────────────────

def test_exposure_is_a_strict_comparison(levels):
    """A loss that takes the whole budget is not exposure: the agent has spent
    everything dying, and there is no budget left for the reset to deny."""
    for r in levels:
        if r.get("error"):
            continue
        b = r.get("shortest_observed_loss")
        assert r["death_fits_budget"] == (b is not None and b < r["budget"]), r["game"]
        if b is not None and b == r["budget"]:
            assert r["death_fits_budget"] is False


def test_a_level_with_no_observed_loss_is_never_called_immune(levels):
    for r in levels:
        if r.get("error") or r.get("shortest_observed_loss") is not None:
            continue
        assert r["death_fits_budget"] is False
        assert r["deaths_affordable"] == 0
        assert r["established"] is False


def test_why_each_rollout_ended_is_recorded_and_adds_up(levels):
    """`no death found` and `kept winning instead` are different facts, and a
    level that is never established deserves to say which happened."""
    for r in levels:
        if r.get("error"):
            continue
        o = r["rollout_outcomes"]
        assert set(o) == {"game_over", "left_play", "hit_cap"}
        assert sum(o.values()) == r["rollouts"]
        assert o["game_over"] == r["rollouts_that_died"]


def test_every_recorded_losing_line_replays_to_a_game_over(levels):
    for r in levels:
        if r.get("error") or not r.get("losing_line"):
            continue
        assert r["witness_replays_to_game_over"] is True, (r["game"], r["level"])
        assert len(r["losing_line"]) == r["shortest_observed_loss"]


def test_the_search_never_looks_past_the_budget(levels):
    """The cap is the budget, so a recorded loss can never exceed it. A longer
    line would mean the instrument answered a question nobody asked."""
    for r in levels:
        b = r.get("shortest_observed_loss")
        if b is not None:
            assert b <= r["budget"], (r["game"], r["level"])


def test_deaths_affordable_is_consistent_with_the_bound(levels):
    for r in levels:
        b = r.get("shortest_observed_loss")
        expected = (r["budget"] // b) if b else 0
        assert r["deaths_affordable"] == expected, (r["game"], r["level"])


def test_both_verdicts_occur_so_the_measure_discriminates(levels):
    yes = [r for r in levels if r.get("death_fits_budget")]
    no = [r for r in levels if not r.get("error") and not r.get("death_fits_budget")]
    assert yes and no
