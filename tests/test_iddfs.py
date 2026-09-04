"""Soundness of the depth-limited and iterative-deepening searches.

The lower bound this audit reports rests entirely on one claim: a completed
search to depth D has visited every state within D actions, so finding no win
proves no solution that short exists. A wrong pruning rule turns that into an
accusation that a published number is impossible, so these are the tests that
matter most in the project.
"""
import sys
from pathlib import Path

import pytest
from conftest import FIXTURE_ENVS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import state_graph as SG  # noqa: E402
from arcengine import ActionInput, GameAction  # noqa: E402


def search(mode, depth, game="bt11", actions=(3, 4), **kw):
    kw.setdefault("max_states", 200_000)
    kw.setdefault("max_seconds", 120)
    kw.setdefault("max_rss_mb", 3000)
    return SG.enumerate_level(game, 0, environments_dir=FIXTURE_ENVS, edges_path=None,
                              check_reset=False, search=mode, max_depth=depth,
                              actions=list(actions), **kw)


@pytest.mark.parametrize("mode", ["dldfs", "iddfs"])
def test_a_limit_equal_to_the_optimum_still_finds_it(mode):
    """The boundary the whole check turns on. A baseline equal to the optimum
    must read as consistent, not as impossible."""
    assert search(mode, 4)["shortest_win_depth"] == 4


@pytest.mark.parametrize("mode", ["dldfs", "iddfs"])
def test_a_limit_one_below_the_optimum_proves_a_bound(mode):
    r = search(mode, 3)
    assert r["shortest_win_depth"] is None
    assert r["explored_to_depth"] == 3
    assert r["min_actions_lower_bound"] == 4
    assert r["win_reachable"] is None, "a depth-bounded search must not report unwinnable"
    assert r["win_established"] is False


@pytest.mark.parametrize("mode", ["dldfs", "iddfs"])
def test_a_limit_of_zero_expands_nothing(mode):
    r = search(mode, 0)
    assert r["states"] == 1 and r["explored_to_depth"] == 0
    assert r["min_actions_lower_bound"] == 1


@pytest.mark.parametrize("mode", ["dldfs", "iddfs"])
def test_the_bound_never_exceeds_the_true_optimum(mode):
    for d in range(0, 4):
        lb = search(mode, d)["min_actions_lower_bound"]
        if lb is not None:
            assert lb <= 4, (mode, d, lb)


def test_all_three_searches_agree_on_the_optimum():
    """Breadth-first, depth-limited and iterative deepening explore in entirely
    different orders. Agreement on the optimum is the strongest evidence
    available that the pruning rule preserves completeness."""
    depths = {m: search(m, 10)["shortest_win_depth"] for m in ("bfs", "dldfs", "iddfs")}
    assert set(depths.values()) == {4}, depths


def test_a_state_reachable_at_two_depths_is_re_expanded_when_reached_shallower():
    """The case a naive visited set gets wrong. bt11's level 1 grid lets the
    same position be reached by different routes of different lengths, so if
    pruning ignored depth the optimum found would be too large."""
    r = search("dldfs", 10)
    assert r["shortest_win_depth"] == 4
    # A search whose map ignored depth would still terminate, but could not
    # guarantee the minimum; check the witness really is minimal by confirming
    # no shorter one exists.
    assert search("dldfs", 3)["shortest_win_depth"] is None


@pytest.mark.parametrize("mode", ["dldfs", "iddfs"])
def test_the_witness_is_as_long_as_the_optimum_and_actually_wins(mode):
    """The witness is reconstructed separately from the search tree; assigning
    it into the tree-path variable was silently overwritten and produced a
    23-action witness for an optimum of 13."""
    r = search(mode, 10)
    path = r["shortest_win_path"]
    assert len(path) == r["shortest_win_depth"]
    _, g = SG.make_game("bt11", 0, FIXTURE_ENVS)
    SG.register_module(g)
    before = g._score
    for a in path:
        g.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)
    assert g._score > before


@pytest.mark.parametrize("mode,kw,reason", [
    ("dldfs", dict(max_states=5), "max_states"),
    ("iddfs", dict(max_states=5), "max_states"),
    # The clock and memory checks run every `progress_every` expansions because
    # both calls are far more expensive than a length comparison, so the fixture
    # finishes before the first check. Tighten the interval to exercise them.
    ("dldfs", dict(max_seconds=0.0, progress_every=1), "max_seconds"),
    ("iddfs", dict(max_rss_mb=1.0, progress_every=1), "max_rss"),
])
def test_a_capped_search_reports_no_bound_it_did_not_prove(mode, kw, reason):
    r = search(mode, 100, **kw)
    assert r["truncated_reason"] == reason
    if r["min_actions_lower_bound"] is not None:
        assert r["min_actions_lower_bound"] == r["explored_to_depth"] + 1
        assert r["min_actions_lower_bound"] <= 4


def test_iterative_deepening_can_bank_an_intermediate_depth():
    """A single pass to a deep limit is all or nothing: it either completes that
    limit or proves nothing beyond the root. Deepening one step at a time keeps
    whatever it completed, which is what makes a capped run useful. On tr87 a
    single pass to depth 54 spent its whole budget and completed nothing."""
    single = search("dldfs", 100)
    assert single["explored_to_depth"] in (0, 100), "a single pass banks only its own limit"
    iterative = search("iddfs", 100)
    assert iterative["shortest_win_depth"] == 4, "deepening stops at the first win"


def test_memory_is_bounded_by_the_path_not_by_a_layer():
    r = search("iddfs", 10)
    assert r["max_stack"] <= 11
