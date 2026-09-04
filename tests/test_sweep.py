"""Edge cases for the action census and the breadth sweep.

Everything here runs on saved fixtures or the toolkit's own fixture game; the
sweep itself is never re-run by the suite.
"""
import json
import sys
from pathlib import Path

import pytest
from conftest import FIXTURE_ENVS

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / "artifacts" / "sweep"
sys.path.insert(0, str(ROOT / "scripts"))

import state_graph as SG  # noqa: E402
import sweep as SW  # noqa: E402


def test_census_covers_every_fetched_environment():
    rows = json.loads((SWEEP / "action_census.json").read_text())
    assert len(rows) == 25
    for r in rows:
        assert r["actions"], r["game"]
        assert r["enumerable"] == (not r["complex_actions"])
        # A click action means 64*64 targets, so the branching factor must reflect it.
        if r["complex_actions"]:
            assert r["branching_factor"] >= 4096 and r["reason"]
        else:
            assert r["branching_factor"] == len(r["actions"])


def test_census_marks_the_click_environments_unenumerable():
    rows = json.loads((SWEEP / "action_census.json").read_text())
    enumerable = sorted(r["game"] for r in rows if r["enumerable"])
    assert enumerable == ["g50t", "ls20", "re86", "tr87", "tu93", "wa30"]


def test_a_truncated_run_never_claims_a_result_it_cannot_know():
    """The dangerous failure mode: a capped run that found no win must not read
    as 'this level is unwinnable', and must not report a probability. bt11's
    level 1 is won in four actions, so the cap has to bite before that."""
    SG.ACTIONS = [3, 4]
    try:
        r = SG.enumerate_level("bt11", 0, max_states=3, max_seconds=120, max_rss_mb=3000,
                               environments_dir=FIXTURE_ENVS, edges_path=None, search="dfs")
    finally:
        SG.ACTIONS = [1, 2, 3, 4]
    assert r["truncated"] and r["truncated_reason"] == "max_states"
    assert r["win_reachable"] is None, "a capped run must not report unwinnable"
    assert r["win_established"] is False
    assert r["p_win_random_policy"] is None


def test_a_win_found_before_the_cap_is_still_established():
    """The complement: truncation does not erase a win that was actually seen."""
    SG.ACTIONS = [3, 4]
    try:
        r = SG.enumerate_level("bt11", 0, max_states=10, max_seconds=120, max_rss_mb=3000,
                               environments_dir=FIXTURE_ENVS, edges_path=None, search="dfs")
    finally:
        SG.ACTIONS = [1, 2, 3, 4]
    assert r["truncated"] and r["win_established"] is True and r["win_reachable"] is True
    # but a probability over an incomplete graph is still refused
    assert r["p_win_random_policy"] is None


def test_dfs_and_bfs_reach_the_same_states_and_edges():
    """Two different search orders over the same transition function must find
    the same reachable set; a difference means the enumerator, not the game."""
    SG.ACTIONS = [3, 4]
    try:
        b = SG.enumerate_level("bt11", 0, 5000, 120, 3000, environments_dir=FIXTURE_ENVS,
                               edges_path=None, search="bfs")
        d = SG.enumerate_level("bt11", 0, 5000, 120, 3000, environments_dir=FIXTURE_ENVS,
                               edges_path=None, search="dfs")
    finally:
        SG.ACTIONS = [1, 2, 3, 4]
    assert b["states"] == d["states"] and b["edges"] == d["edges"]
    assert b["win_reachable"] == d["win_reachable"]
    assert b["p_win_random_policy"] == pytest.approx(d["p_win_random_policy"])
    assert b["double_advance_actions"] == d["double_advance_actions"]
    # DFS must not claim a shortest path it did not search for.
    assert b["shortest_win_depth"] == 4 and d["shortest_win_depth"] is None
    assert d["first_win_depth"] is not None


def test_dfs_memory_is_bounded_by_depth_not_by_layer_width():
    SG.ACTIONS = [3, 4]
    try:
        d = SG.enumerate_level("bt11", 0, 5000, 120, 3000, environments_dir=FIXTURE_ENVS,
                               edges_path=None, search="dfs")
    finally:
        SG.ACTIONS = [1, 2, 3, 4]
    assert d["max_stack"] <= d["states"]


def test_a_game_whose_actions_are_not_one_to_four(tmp_path):
    """bt11 advertises [3, 4]; passing the game's own set must be respected."""
    r = SG.enumerate_level("bt11", 0, 5000, 120, 3000, environments_dir=FIXTURE_ENVS,
                           edges_path=None, search="dfs", actions=[3, 4])
    assert r["actions"] == [3, 4]
    SG.ACTIONS = [1, 2, 3, 4]


def test_result_validation_rejects_corrupt_and_incomplete_files(tmp_path):
    """A result file that is unreadable or missing fields must be re-run, not
    silently trusted as a completed environment."""
    good = tmp_path / "good.json"
    good.write_text(json.dumps(dict(states=1, edges=1, win_reachable=True, truncated=False,
                                    reset_checked=1, reset_returns_to_start=1, double_advance_actions=0)))
    assert SW.valid_result(good) is not None
    bad = tmp_path / "bad.json"; bad.write_text("{not json")
    assert SW.valid_result(bad) is None
    partial = tmp_path / "partial.json"; partial.write_text(json.dumps(dict(states=1)))
    assert SW.valid_result(partial) is None
    assert SW.valid_result(tmp_path / "absent.json") is None


def test_sweep_summary_is_consistent_with_its_per_environment_results():
    s = json.loads((SWEEP / "summary_L1.json").read_text())
    census = {r["game"] for r in json.loads((SWEEP / "action_census.json").read_text())}
    assert {r["game"] for r in s["rows"]} == census
    for r in s["rows"]:
        if r["status"] != "complete":
            continue
        d = json.loads((SWEEP / f"{r['game']}_L1.json").read_text())
        assert d["states"] == r["states"] and d["edges"] == r["edges"]
        assert d["win_reachable"] == r["win_reachable"]
    # Nothing may be reported unwinnable unless its enumeration actually completed.
    for g in s["flags"]["unwinnable_complete"]:
        d = json.loads((SWEEP / f"{g}_L1.json").read_text())
        assert not d["truncated"] and d["win_established"] is True


# --- the detectors must be able to fire, or the sweep's negatives mean nothing ---

def _fixture_game():
    g = SG.make_game("bt11", 0, FIXTURE_ENVS)[1]
    SG.register_module(g)
    return g


def test_reset_probe_can_actually_report_a_mismatch(monkeypatch):
    """Break RESET deliberately: the probe must notice. A 500/500 result across
    the sweep is only evidence if a 499/500 were possible."""
    import arcengine.base_game as BG
    monkeypatch.setattr(BG.ARCBaseGame, "handle_reset", lambda self: None)
    SG.ACTIONS = [3, 4]
    try:
        r = SG.enumerate_level("bt11", 0, 400, 60, 3000, environments_dir=FIXTURE_ENVS,
                               edges_path=None, search="dfs", max_reset_checks=50)
    finally:
        SG.ACTIONS = [1, 2, 3, 4]
    assert r["reset_checked"] > 0
    assert r["reset_returns_to_start"] < r["reset_checked"], "a broken RESET went unnoticed"
    assert r["reset_mismatches"], "a mismatch was counted but not recorded"


def test_double_advance_detector_can_actually_fire(monkeypatch):
    """Make one action complete two levels: the detector must catch it. The
    sweep reporting zero everywhere is only evidence if a non-zero were
    reachable by the same code path."""
    import arcengine.base_game as BG
    real = BG.ARCBaseGame.next_level
    def double(self):
        real(self)
        if self._score < len(self._levels):
            real(self)
    monkeypatch.setattr(BG.ARCBaseGame, "next_level", double)
    SG.ACTIONS = [3, 4]
    try:
        r = SG.enumerate_level("bt11", 0, 3000, 60, 3000, environments_dir=FIXTURE_ENVS,
                               edges_path=None, search="dfs")
    finally:
        SG.ACTIONS = [1, 2, 3, 4]
    assert r["double_advance_actions"] > 0, "a two-level jump in one action went unnoticed"
    ex = r["double_advance_examples"][0]
    assert ex["to_levels"] - ex["from_levels"] >= 2
