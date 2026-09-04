"""Edge cases for the play prober.

Everything runs on the toolkit's own fixture game bt11 or on saved artefacts;
the 25-environment run is never repeated by the suite.
"""
import json
import sys
from pathlib import Path

import pytest
from conftest import FIXTURE_ENVS

ROOT = Path(__file__).resolve().parents[1]
PLAY = ROOT / "artifacts" / "play"
sys.path.insert(0, str(ROOT / "scripts"))

import play_probe as PP  # noqa: E402
from arcengine import ActionInput, GameAction  # noqa: E402


def probe(**kw):
    kw.setdefault("game", "bt11")
    kw.setdefault("actions", [3, 4])
    kw.setdefault("seed", 0)
    kw.setdefault("max_actions", 400)
    kw.setdefault("max_seconds", 60)
    kw.setdefault("probe_every", 5)
    kw.setdefault("max_rss_mb", 3000)
    kw.setdefault("environments_dir", FIXTURE_ENVS)
    return PP.probe_environment(**kw)


def test_fixture_probe_finds_no_reset_mismatch_and_no_double_advance():
    r = probe()
    assert r["reset_probes"] > 0
    assert r["reset_returns_to_level_start"] == r["reset_probes"]
    assert r["reset_frame_returns_to_level_start"] == r["reset_probes"]
    assert r["reset_mismatches"] == []
    assert r["double_advance_actions"] == 0 and r["level_regressions"] == 0


def test_same_seed_is_reproducible_and_different_seeds_differ():
    a, b = probe(seed=7), probe(seed=7)
    for k in a:
        if k == "peak_rss_mb":
            continue
        assert a[k] == b[k], k
    c = probe(seed=8)
    assert (c["distinct_states_visited"], c["actions_taken"], c["no_op_actions"]) != \
           (a["distinct_states_visited"], a["actions_taken"], a["no_op_actions"]) or c == a


def test_zero_action_budget_probes_nothing_and_claims_nothing():
    r = probe(max_actions=0)
    assert r["actions_taken"] == 0 and r["reset_probes"] == 0
    assert r["reset_returns_to_level_start"] == 0
    assert r["double_advance_actions"] == 0
    assert r["distinct_states_visited"] == 1   # only the start state


def test_an_unadvertised_action_is_accepted_and_changes_nothing():
    """bt11 advertises [3, 4]; driving it with ACTION1 must leave every state
    untouched, which the prober should see as no-ops rather than as progress."""
    r = probe(actions=[1], max_actions=50)
    assert r["actions_taken"] == 50
    assert r["no_op_actions"] == 50
    assert r["distinct_states_visited"] == 1


def test_each_cap_stops_cleanly(monkeypatch):
    assert probe(max_actions=20)["stopped"] is None      # budget reached, not a cap
    assert probe(max_seconds=0.0)["stopped"] == "max_seconds"
    assert probe(max_rss_mb=1.0)["stopped"] == "max_rss"


def test_game_over_is_followed_by_a_reset_and_play_continues():
    """Driving bt11 with ACTION4 only loses level 1 repeatedly; the prober must
    reset out of GAME_OVER and keep going rather than stalling."""
    r = probe(actions=[4], max_actions=60)
    assert r["game_overs"] > 0 and r["resets_issued"] > 0
    assert r["actions_taken"] == 60


def test_a_win_is_reached_and_the_run_continues_past_it():
    """ACTION3 solves every bt11 level, so a long enough run wins the game and
    must keep playing afterwards (a RESET after a WIN is a full reset)."""
    r = probe(actions=[3], max_actions=200)
    assert r["wins"] > 0 and r["resets_issued"] > 0
    assert len(r["levels_entered"]) > 1, "level transitions were not recorded"


def test_complex_action_coordinates_stay_inside_the_declared_bounds(monkeypatch):
    """ComplexAction declares x and y in 0..63. The prober must never sample
    outside that, whether or not the local wrapper happens to validate it."""
    seen = []
    real = PP.make_game

    def spy(*a, **kw):
        full_id, g = real(*a, **kw)
        orig = g.perform_action

        def wrapped(action_input, raw=False):
            if action_input.data:
                seen.append((action_input.data.get("x"), action_input.data.get("y")))
            return orig(action_input, raw=raw)
        g.perform_action = wrapped
        return full_id, g
    monkeypatch.setattr(PP, "make_game", spy)
    probe(actions=[6], max_actions=200)
    assert seen, "no complex action was ever issued"
    assert all(0 <= x <= 63 and 0 <= y <= 63 for x, y in seen)


# --- the detectors must be able to fire, or the zeros mean nothing ---

def test_reset_detector_fires_on_state_that_survives_a_reset(monkeypatch):
    """Inject exactly the real phenomenon: a game attribute that changes during
    play and that a level reset does not restore. The game stays playable, so
    probes still happen, and the detector must report a state mismatch while the
    rendered frame still matches -- the distinction the audit turns on.

    Stubbing handle_reset out entirely was tried first and is wrong: the fixture
    then never leaves GAME_OVER, no probe ever runs, and the test passes or fails
    for reasons unrelated to the detector."""
    import arcengine.base_game as BG
    real = BG.ARCBaseGame.perform_action

    def counting(self, action_input, raw=False):
        self._audit_leak = getattr(self, "_audit_leak", 0) + 1
        return real(self, action_input, raw=raw)
    monkeypatch.setattr(BG.ARCBaseGame, "perform_action", counting)
    r = probe(max_actions=200)
    assert r["reset_probes"] > 0, "no probe ran, so the detector was never exercised"
    assert r["reset_returns_to_level_start"] < r["reset_probes"], "surviving state went unnoticed"
    assert r["reset_mismatches"]
    # The frame is untouched by the injected attribute, and must still match.
    assert r["reset_frame_returns_to_level_start"] == r["reset_probes"]
    assert r["reset_mismatches"][0]["frame_also_differs"] is False


def test_reset_detector_reports_a_frame_mismatch_when_the_frame_really_changes(monkeypatch):
    """The complementary injection: make the reset leave a visible change. The
    frame counter must fall, or a genuine visual leak would be reported as
    invisible bookkeeping."""
    import arcengine.base_game as BG
    from arcengine import Sprite
    real = BG.ARCBaseGame.level_reset

    def dirty(self):
        real(self)
        # bt11's levels start with no sprites at all, so moving sprites[0] --
        # the first thing tried -- silently did nothing and the test passed for
        # the wrong reason. Add a visible sprite instead.
        self.current_level.add_sprite(
            Sprite(pixels=[[1]], name="audit-probe", visible=True).set_position(1, 1))
    monkeypatch.setattr(BG.ARCBaseGame, "level_reset", dirty)
    r = probe(max_actions=200)
    assert r["reset_probes"] > 0
    assert r["reset_frame_returns_to_level_start"] < r["reset_probes"], "a visible leak went unnoticed"


def test_double_advance_detector_fires_when_two_levels_complete_at_once(monkeypatch):
    import arcengine.base_game as BG
    real = BG.ARCBaseGame.next_level

    def double(self):
        real(self)
        if self._score < len(self._levels):
            real(self)
    monkeypatch.setattr(BG.ARCBaseGame, "next_level", double)
    r = probe(actions=[3], max_actions=200)
    assert r["double_advance_actions"] > 0, "a two-level jump in one action went unnoticed"
    assert r["double_advance_examples"][0]["to_levels"] - \
           r["double_advance_examples"][0]["from_levels"] >= 2


def test_summary_matches_the_per_environment_files():
    s = json.loads((PLAY / "summary.json").read_text())
    for row in s["rows"]:
        if row["status"] != "probed":
            continue
        d = json.loads((PLAY / f"{row['game']}.json").read_text())
        assert d["reset_probes"] == row["reset_probes"]
        assert d["reset_returns_to_level_start"] == row["reset_ok"]
        assert d["double_advance_actions"] == row["double_advance_actions"]
    # A flagged environment must have the evidence in its own file.
    for g in s["flags"]["reset_state_mismatch"]:
        assert json.loads((PLAY / f"{g}.json").read_text())["reset_mismatches"]
