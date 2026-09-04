"""Edge cases for the depth-bounded search and the baseline lower-bound check.

The whole claim of this phase rests on one property: a breadth-first search that
has fully expanded every state at depth d has PROVED no win exists in d actions
or fewer. These tests exercise that property and the ways it can be lost.
"""
import json
import sys
from pathlib import Path

import pytest
from conftest import FIXTURE_ENVS

ROOT = Path(__file__).resolve().parents[1]
MA = ROOT / "artifacts" / "minactions"
sys.path.insert(0, str(ROOT / "scripts"))

import min_actions as MAM  # noqa: E402
import state_graph as SG  # noqa: E402


def bfs(**kw):
    kw.setdefault("game", "bt11")
    kw.setdefault("level_index", 0)
    kw.setdefault("max_states", 20000)
    kw.setdefault("max_seconds", 60)
    kw.setdefault("max_rss_mb", 3000)
    kw.setdefault("environments_dir", FIXTURE_ENVS)
    kw.setdefault("edges_path", None)
    kw.setdefault("check_reset", False)
    kw.setdefault("search", "bfs")
    kw.setdefault("actions", [3, 4])
    return SG.enumerate_level(**kw)


def test_fixture_optimum_is_four_actions():
    r = bfs()
    assert r["shortest_win_depth"] == 4
    assert r["shortest_win_path"] == [3, 3, 3, 3]


def test_depth_bound_equal_to_the_optimum_still_finds_it():
    """The boundary the whole check turns on: a bound of exactly the optimum
    must still reach it, or a baseline equal to the optimum would be misread as
    impossible."""
    r = bfs(max_depth=4)
    assert r["shortest_win_depth"] == 4


def test_depth_bound_below_the_optimum_proves_a_lower_bound_not_unwinnability():
    """Expanding layer d discovers every state at depth d + 1, so completing
    layers 0..d without a win proves no solution within d + 1 actions and puts
    the optimum at d + 2 or more. bt11's optimum is 4, and a bound of 3 here
    would be an off-by-one that understates the minimum -- which is the
    direction that could produce a false accusation."""
    r = bfs(max_depth=3)
    assert r["shortest_win_depth"] is None
    assert r["completed_depth"] == 2
    assert r["min_actions_lower_bound"] == 4
    assert r["truncated_reason"] == "max_depth"
    assert r["win_reachable"] is None, "a bounded search must not report unwinnable"


def test_the_lower_bound_never_exceeds_the_true_optimum():
    """The bound must be sound at every depth: for every bound below bt11's
    optimum of 4, the reported minimum must not claim more than 4."""
    for d in range(0, 4):
        r = bfs(max_depth=d)
        lb = r["min_actions_lower_bound"]
        if lb is not None:
            assert lb <= 4, (d, lb)


def test_zero_depth_bound_proves_nothing_beyond_the_start():
    r = bfs(max_depth=0)
    assert r["shortest_win_depth"] is None
    assert r["states"] == 1 and r["edges"] == 0
    assert r["min_actions_lower_bound"] in (None, 1)


@pytest.mark.parametrize("kw,reason", [
    (dict(max_states=5), "max_states"),
    (dict(max_seconds=0.0), "max_seconds"),
    (dict(max_rss_mb=1.0), "max_rss"),
])
def test_a_capped_search_never_reports_a_lower_bound_it_did_not_prove(kw, reason):
    """A cap that fires part-way through a layer means that layer was not fully
    expanded, so no bound follows from it. This is the failure mode that would
    turn a resource limit into a false accusation against a benchmark."""
    r = bfs(max_depth=100, **kw)
    assert r["truncated_reason"] == reason
    if r["shortest_win_depth"] is None:
        assert r["completed_depth"] < 100
    # Whatever bound is reported must be backed by a completed layer.
    if r["min_actions_lower_bound"] is not None:
        assert r["min_actions_lower_bound"] == r["completed_depth"] + 2
        assert r["min_actions_lower_bound"] <= 4, "the bound must never exceed the true optimum"


def test_verdicts_are_read_correctly_from_a_result():
    consistent = dict(shortest_win_depth=13, min_actions_lower_bound=None)
    assert MAM.verdict_of(consistent, 22)[0] == "consistent"
    assert MAM.verdict_of(dict(shortest_win_depth=18, min_actions_lower_bound=None), 19)[0] == "consistent"
    # Exactly equal is consistent, not impossible: a human may play optimally.
    assert MAM.verdict_of(dict(shortest_win_depth=19, min_actions_lower_bound=None), 19)[0] == "consistent"
    assert MAM.verdict_of(dict(shortest_win_depth=20, min_actions_lower_bound=None), 19)[0] == "IMPOSSIBLE"
    proved = dict(shortest_win_depth=None, min_actions_lower_bound=27, completed_depth=25)
    assert MAM.verdict_of(proved, 26)[0] == "IMPOSSIBLE"
    assert MAM.verdict_of(proved, 27)[0] == "not established", "a bound equal to the baseline is not a contradiction"
    assert MAM.verdict_of(proved, 30)[0] == "not established"
    capped = dict(shortest_win_depth=None, min_actions_lower_bound=None,
                  completed_depth=5, truncated_reason="max_states")
    assert MAM.verdict_of(capped, 26)[0] == "not established"
    assert MAM.verdict_of(capped, None)[0] == "no baseline"


def test_a_missing_or_short_baseline_list_is_handled():
    assert MAM.verdict_of(dict(shortest_win_depth=4), None)[0] == "no baseline"


def test_the_witness_actually_completes_the_level_in_the_shipped_game():
    """A claimed optimum is worthless unless the action sequence really wins.
    Replay it through the shipped game and check the level completes."""
    from arcengine import ActionInput, GameAction
    r = bfs()
    _, g = SG.make_game("bt11", 0, FIXTURE_ENVS)
    SG.register_module(g)
    before = g._score
    for a in r["shortest_win_path"]:
        g.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)
    assert g._score == before + 1, "the witness did not complete the level"


def test_reported_optima_replay_in_the_shipped_game():
    """Same check against every optimum this phase actually published."""
    from arcengine import ActionInput, GameAction
    for p in sorted(MA.glob("*_L*.json")):
        d = json.loads(p.read_text())
        if not d.get("witness"):
            continue
        game = d["game"].split("-")[0]
        _, g = SG.make_game(game, d["level"] - 1)
        SG.register_module(g)
        before = g._score
        for a in d["witness"]:
            g.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)
        assert g._score > before, f"{game} L{d['level']} witness did not complete the level"
        assert len(d["witness"]) == d["optimum"]


def test_no_impossible_verdict_rests_on_a_capped_search():
    s = MA / "summary.json"
    if not s.exists():
        pytest.skip("sweep not run")
    for r in json.loads(s.read_text())["rows"]:
        if r["verdict"] != "IMPOSSIBLE":
            continue
        d = json.loads((MA / f"{r['game'].split('-')[0]}_L{r['level']}.json").read_text())
        assert d["optimum"] is not None or d["min_actions_lower_bound"] is not None
        assert d["truncated_reason"] in (None, "max_depth"), \
            "an IMPOSSIBLE verdict must not come from a resource cap"
