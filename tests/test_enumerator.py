"""Edge cases for the state-graph enumerator and the trace recorder.

Fast paths run on the toolkit's own fixture game bt11 (5 levels, two actions);
only the cap tests touch ls20, and they stop almost immediately by construction.
"""
import gzip
import json
import sys
from pathlib import Path

import pytest
from conftest import FIXTURE_ENVS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import state_graph as SG  # noqa: E402
from arcengine import ActionInput, GameAction  # noqa: E402


@pytest.fixture
def fixture_actions():
    """bt11 advertises actions 3 and 4 only."""
    old = SG.ACTIONS
    SG.ACTIONS = [3, 4]
    yield
    SG.ACTIONS = old


def enum_fixture(tmp_path, **kw):
    kw.setdefault("max_states", 5000)
    kw.setdefault("max_seconds", 120)
    kw.setdefault("edges_path", tmp_path / "e.jsonl.gz")
    kw.setdefault("environments_dir", FIXTURE_ENVS)
    return SG.enumerate_level("bt11", 0, **kw)


def test_fixture_level_is_winnable_in_four_actions(tmp_path, fixture_actions):
    r = enum_fixture(tmp_path)
    assert r["win_reachable"] and r["shortest_win_depth"] == 4
    assert r["shortest_win_path"] == [3, 3, 3, 3]
    assert not r["truncated"] and r["truncated_reason"] is None


def test_reset_probe_returns_to_start_on_the_fixture(tmp_path, fixture_actions):
    r = enum_fixture(tmp_path, max_reset_checks=200)
    assert r["reset_checked"] > 0
    assert r["reset_returns_to_start"] == r["reset_checked"]
    assert r["reset_mismatches"] == []


def test_no_double_advance_on_the_fixture(tmp_path, fixture_actions):
    assert enum_fixture(tmp_path)["double_advance_actions"] == 0


def test_node_ids_are_dense_and_edges_reference_known_nodes(tmp_path, fixture_actions):
    """Node ids are 0..states-1 and every edge references ids in that range: a
    dangling id would mean the deduplication table and the edge stream disagree.
    (bt11's level 1 is a tree, so no path re-converges there; the ls20 levels
    exercise the merging case with edges far exceeding states.)"""
    r = enum_fixture(tmp_path)
    with gzip.open(tmp_path / "e.jsonl.gz", "rt") as fh:
        ids = {v for line in fh for v in (json.loads(line)["i"], json.loads(line)["j"])}
    assert max(ids) < r["states"] and min(ids) >= 0
    assert r["edges"] >= r["states"] - 1


def test_edges_file_is_streamable_and_well_formed(tmp_path, fixture_actions):
    r = enum_fixture(tmp_path)
    n = 0
    with gzip.open(tmp_path / "e.jsonl.gz", "rt") as fh:
        for line in fh:
            e = json.loads(line)
            assert set(e) == {"i", "j", "a", "s", "t"}
            assert e["a"] in SG.ACTIONS and len(e["s"]) == 10 and len(e["t"]) == 10
            n += 1
    assert n == r["edges"]


def test_peak_memory_is_reported_and_small(tmp_path, fixture_actions):
    r = enum_fixture(tmp_path)
    assert r["peak_rss_mb"] > 0 and r["peak_rss_mb"] < r["max_rss_mb_cap"]


@pytest.mark.parametrize("kw,reason", [
    (dict(max_states=10), "max_states"),
    (dict(max_seconds=0.0), "max_seconds"),
    (dict(max_rss_mb=1.0), "max_rss"),
])
def test_each_cap_stops_cleanly_with_its_own_reason(tmp_path, fixture_actions, kw, reason):
    r = enum_fixture(tmp_path, **kw)
    assert r["truncated"] is True and r["truncated_reason"] == reason
    # A truncated run must not claim a probability it cannot know.
    assert r["p_win_random_policy"] is None


def test_terminal_states_are_absorbing_and_not_expanded(tmp_path, fixture_actions):
    """No edge leaves a WIN or GAME_OVER node: the enumerator stops there."""
    enum_fixture(tmp_path)
    terminal = set()
    src = set()
    with gzip.open(tmp_path / "e.jsonl.gz", "rt") as fh:
        for line in fh:
            e = json.loads(line)
            src.add(e["i"])
            if e["t"][7] != 0:
                terminal.add(e["j"])
    assert not (terminal & src), sorted(terminal & src)[:5]


def test_action_outside_the_available_set_changes_nothing(fixture_actions):
    """bt11 advertises [3, 4]; ACTION1 is accepted and leaves the state alone.
    This is the behaviour the model encodes by making Step total in the action."""
    _, g = SG.make_game("bt11", 0, FIXTURE_ENVS)
    SG.register_module(g)
    before = SG.state_key(g)
    g.perform_action(ActionInput(id=GameAction.from_id(1)), raw=True)
    assert SG.state_key(g) == before


def test_actions_after_win_and_after_game_over_are_inert(fixture_actions):
    _, g = SG.make_game("bt11", 0, FIXTURE_ENVS)
    SG.register_module(g)
    for _ in range(4 + 8 + 16 + 20 + 24):
        g.perform_action(ActionInput(id=GameAction.ACTION3), raw=True)
    assert SG.status(g, 0) == "WIN"
    after_win = SG.state_key(g)
    g.perform_action(ActionInput(id=GameAction.ACTION3), raw=True)
    assert SG.state_key(g) == after_win

    _, g2 = SG.make_game("bt11", 0, FIXTURE_ENVS)
    SG.register_module(g2)
    for _ in range(4):
        g2.perform_action(ActionInput(id=GameAction.ACTION4), raw=True)
    assert SG.status(g2, 0) == "GAME_OVER"
    over = SG.state_key(g2)
    g2.perform_action(ActionInput(id=GameAction.ACTION4), raw=True)
    assert SG.state_key(g2) == over


def test_empty_and_single_action_traces(tmp_path):
    import env_probe
    rec = env_probe.record_traces("bt11", 0, [[], [3]], tmp_path / "t.jsonl.gz", FIXTURE_ENVS)
    assert rec["traces"] == 2 and rec["steps"] == 1


def test_enumeration_is_byte_identical_on_rerun(tmp_path, fixture_actions):
    a = enum_fixture(tmp_path, edges_path=tmp_path / "a.gz")
    b = enum_fixture(tmp_path, edges_path=tmp_path / "b.gz")
    for k in a:
        if k.startswith(("peak_rss", "rss_at_start")):
            continue
        assert a[k] == b[k], k
    assert (tmp_path / "a.gz").read_bytes() == (tmp_path / "b.gz").read_bytes()


def test_numpy_scalar_attributes_are_hashed_by_value(fixture_actions):
    """A numpy scalar stored on the game must change the state key. Hashing it
    by type name would merge states that differ only in it, which hides
    transitions -- the dangerous direction. A reproducibility check reported
    exactly this gap for int8."""
    import numpy as np
    _, g = SG.make_game("bt11", 0, FIXTURE_ENVS)
    SG.register_module(g)
    g._probe = np.int8(1)
    k1 = SG.state_key(g)
    g._probe = np.int8(2)
    k2 = SG.state_key(g)
    assert k1 != k2, "a numpy scalar attribute did not affect the state key"
    assert "int8" not in SG.UNHANDLED
    g._probe = np.float32(1.5)
    assert SG.state_key(g) not in (k1, k2)


def test_unhandled_types_are_reported_not_swallowed(tmp_path, fixture_actions):
    """Anything the canonicaliser cannot read by value is recorded, so an
    under-fine key is visible in the artefact instead of silent."""
    r = enum_fixture(tmp_path)
    assert "unhandled_types" in r and isinstance(r["unhandled_types"], list)
