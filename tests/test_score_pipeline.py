"""Edge cases for the scoring pipeline probes.

These exercise the bookkeeping that feeds the scoring formula: how a play
becomes per-level action counts, and how environment scores are aggregated. A
defect here changes a reported number even when the formula is right.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "artifacts" / "pipeline"
sys.path.insert(0, str(ROOT / "scripts"))

import score_pipeline_probe as SP  # noqa: E402

B5 = [10, 10, 10, 10, 10]


def test_harness_reproduces_the_toolkits_own_asserted_expectations():
    """vendor/ARC-AGI/tests/test_scorecard.py asserts that six levels each
    completed at the baseline score 100. If our planting harness cannot
    reproduce what the authors assert, nothing built on it counts."""
    r = SP.score({"aa00": [SP.linear_play([10] * 6)]}, {"aa00": [10] * 6})
    assert r["environments"]["aa00"] == pytest.approx(100.0)
    # and the partial progressions the same test walks through
    for k in range(1, 7):
        rk = SP.score({"aa00": [SP.linear_play([10] * k, win=(k == 6))]}, {"aa00": [10] * 6})
        expected = sum(range(1, k + 1)) / 21 * 100
        assert rk["environments"]["aa00"] == pytest.approx(expected, abs=1e-3), k


def test_an_empty_scorecard_scores_zero_and_does_not_divide_by_zero():
    r = SP.score({}, {})
    assert r["total"] == 0.0 and r["environments"] == {}


def test_a_play_with_no_actions_and_a_play_that_never_completes_a_level():
    assert SP.score({"aa00": [[]]}, {"aa00": B5})["environments"]["aa00"] == 0.0
    never = [dict(action=SP.MOVE, levels=0) for _ in range(30)]
    assert SP.score({"aa00": [never]}, {"aa00": B5})["environments"]["aa00"] == 0.0


def test_completing_every_level_at_the_baseline_scores_one_hundred():
    assert SP.score({"aa00": [SP.linear_play([10] * 5)]}, {"aa00": B5})["environments"]["aa00"] \
        == pytest.approx(100.0)


def test_fewer_baselines_than_levels_played_is_reported_not_scored():
    """The scorer refuses rather than guessing when the baseline list is shorter
    than the levels the play recorded."""
    r = SP.score({"aa00": [SP.linear_play([10] * 5)]}, {"aa00": [10, 10]})
    assert r["environments"]["aa00"] == 0.0


def test_more_baselines_than_levels_reached_caps_at_the_completed_share():
    r = SP.score({"aa00": [SP.linear_play([10, 10], win=False)]}, {"aa00": [10] * 8})
    assert r["environments"]["aa00"] == pytest.approx(3 / 36 * 100, abs=1e-6)


def test_a_level_reset_is_charged_to_the_agents_action_count():
    """This is the behaviour, whatever one thinks of it: a RESET increments the
    action count and lands on the level it happened on, so it lowers that
    level's efficiency score."""
    clean = SP.score({"aa00": [SP.linear_play([10] * 5)]}, {"aa00": B5})["environments"]["aa00"]
    with_resets = SP.score({"aa00": [SP.linear_play([10] * 5, resets_before_level={1: 1, 2: 1, 3: 1, 4: 1})]},
                           {"aa00": B5})["environments"]["aa00"]
    assert clean == pytest.approx(100.0)
    assert with_resets < clean
    assert with_resets == pytest.approx(83.801652893, abs=1e-6)


def test_aggregation_divides_by_environments_played_not_by_the_set():
    """Three environments played, each perfect. The toolkit reports the mean
    over the three; the report defines the total as the mean over the set."""
    games = ("aa00", "bb00", "cc00")
    r = SP.score({g: [SP.linear_play([10] * 5)] for g in games}, {g: B5 for g in games})
    assert r["total"] == pytest.approx(100.0)
    documented_over_135 = sum(r["environments"].values()) / 135
    assert documented_over_135 == pytest.approx(100 * 3 / 135, abs=1e-6)
    assert r["total"] / documented_over_135 == pytest.approx(45.0, abs=1e-6)


def test_aggregation_agrees_when_the_whole_set_is_played():
    """The difference is exactly the partial-coverage case, which is why an
    official run over the full set is not exposed to it."""
    games = ("aa00", "bb00")
    r = SP.score({g: [SP.linear_play([10] * 5)] for g in games}, {g: B5 for g in games})
    assert r["total"] == pytest.approx(sum(r["environments"].values()) / len(games))


def test_reported_score_and_levels_completed_can_come_from_different_plays():
    """One play is more efficient but reaches less far; the other reaches
    further. The environment's reported score is the maximum over plays and its
    reported levels-completed is also a maximum, taken independently."""
    r = SP.score({"aa00": [SP.linear_play([5, 5], win=False), SP.linear_play([40] * 5)]},
                 {"aa00": B5})
    env = r["per_environment"]["aa00"]
    best_score = max(run["score"] for run in env["runs"])
    from_that_run = [run for run in env["runs"] if run["score"] == best_score][0]
    assert r["environments"]["aa00"] == pytest.approx(best_score)
    assert env["levels_completed"] > from_that_run["levels_completed"], \
        "the reported level count came from the same run as the reported score"


def test_probe_artefacts_are_reproducible(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    SP.main(["--out", str(a)]); SP.main(["--out", str(b)])
    assert (a / "pipeline.json").read_bytes() == (b / "pipeline.json").read_bytes()
    assert (a / "pipeline.log").read_bytes() == (b / "pipeline.log").read_bytes()


def test_committed_probe_summary_matches_the_script():
    d = json.loads((PIPE / "pipeline.json").read_text())
    q2 = [r for r in d if r["id"] == "Q2"][0]
    assert q2["toolkit_total"] == pytest.approx(100.0)
    assert q2["documented_total"] == pytest.approx(2.222222222, abs=1e-6)
    assert q2["environments_played"] == 3 and q2["set_size"] == 135
