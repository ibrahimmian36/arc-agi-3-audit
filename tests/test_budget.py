"""The forced-reset budget denial, and the tax on the real public levels.

The claim under test is narrow and must stay narrow: on the CLIENT, a reset the
harness issues after a game over consumes the agent's per-level action budget,
and there are budgets at which that is what fails the level. Nothing here is a
claim about the server.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

budget_probe = pytest.importorskip("budget_probe")

ART = ROOT / "artifacts" / "budget" / "budget.json"


@pytest.fixture(scope="module")
def art() -> dict:
    if not ART.exists():
        pytest.skip("run scripts/budget_probe.py first")
    return json.loads(ART.read_text())


def test_a_level_is_denied_by_a_reset_the_agent_did_not_choose(art):
    """The headline: same policy, same budget, opposite outcome."""
    denials = [p for p in art["pairs"] if p["denied_by_forced_reset"]]
    assert denials, "no denial regime found; F12 would be a cost, not a denial"
    for p in denials:
        s, c = p["shipped"], p["counterfactual"]
        assert s["exit_reason"] == "ACTION_BUDGET"
        assert s["levels_completed"] == [0]
        assert c["levels_completed"] == [1]
        assert s["environment_score"] == 0.0
        assert c["environment_score"] > 0.0
        # The runs must differ in one respect only.
        assert s["forced_resets"] == c["forced_resets"] > 0
        assert s["budget"] == c["budget"]


def test_the_pair_differs_only_in_whether_the_forced_reset_is_counted(art):
    """Guard against a comparison that is not apples to apples."""
    for p in art["pairs"]:
        s, c = p["shipped"], p["counterfactual"]
        assert s["count_forced"] is True and c["count_forced"] is False
        assert s["forced_resets"] == c["forced_resets"]
        # The forced reset still reaches the environment in both runs.
        assert s["card_resets"] == c["card_resets"]


def test_boundary_of_the_denial_regime(art):
    """Below the window both fail; above it both win. Only inside does it decide."""
    pairs = {p["budget"]: p for p in art["pairs"]}
    lo = min(p["budget"] for p in art["pairs"] if p["denied_by_forced_reset"])
    hi = max(p["budget"] for p in art["pairs"] if p["denied_by_forced_reset"])
    below, above = pairs.get(lo - 1), pairs.get(hi + 1)
    assert below is not None and above is not None, "the sweep must bracket the window"
    assert below["shipped"]["levels_completed"] == below["counterfactual"]["levels_completed"] == [0]
    assert above["shipped"]["levels_completed"] == above["counterfactual"]["levels_completed"] == [1]


def test_denial_window_is_as_wide_as_the_number_of_game_overs(art):
    """The preregistered prediction. Not a knife edge: it grows with every death."""
    assert art["windows"], "no windows recorded"
    for w in art["windows"]:
        assert w["window_width"] == w["deaths"] == w["predicted_width"], w
        assert w["prediction_holds"] is True
    assert [w["deaths"] for w in art["windows"]] == [0, 1, 2, 3]
    # A run that never dies is never affected: the mechanism needs a game over.
    zero = [w for w in art["windows"] if w["deaths"] == 0][0]
    assert zero["denial_budgets"] == []


def test_effective_budget_is_the_stated_budget_minus_the_deaths(art):
    """The general statement the window result implies."""
    for w in art["windows"]:
        if w["deaths"] == 0:
            continue
        # The smallest budget on which the shipped run still completes the level
        # is the chosen actions plus one per game over.
        assert min(w["denial_budgets"]) == w["chosen_actions"]
        assert max(w["denial_budgets"]) + 1 == w["chosen_actions"] + w["deaths"]


def test_tax_is_computed_over_the_real_public_set(art):
    tax = art["tax"]
    assert tax["environments"] == 25
    assert tax["levels"] == 183
    games = json.loads((ROOT / "artifacts" / "api" / "games.json").read_text())
    assert tax["levels"] == sum(len(g["baseline_actions"]) for g in games)


def test_tax_arithmetic_matches_the_verified_scoring_rule(art):
    """Every row re-derived from its baseline, independently of the probe."""
    for r in art["tax"]["rows"]:
        b = r["baseline"]
        assert r["budget"] == math.ceil(b * 5.0)
        assert r["share_of_budget"] == pytest.approx(1.0 / r["budget"])
        perfect = min(115.0, (b / b) ** 2 * 100.0)
        after = min(115.0, (b / (b + 1)) ** 2 * 100.0)
        assert r["score_perfect"] == pytest.approx(perfect)
        assert r["score_after_one_forced_reset"] == pytest.approx(after)
        assert r["fall"] == pytest.approx(perfect - after)


def test_the_worst_level_is_the_one_with_the_smallest_baseline(art):
    """Sanity: the tax bites hardest where the baseline is smallest."""
    rows = art["tax"]["rows"]
    worst = art["tax"]["worst"]
    assert worst["baseline"] == min(r["baseline"] for r in rows)
    assert worst["fall"] == max(r["fall"] for r in rows)


def test_no_claim_about_the_server_in_the_probe_source():
    src = (ROOT / "scripts" / "budget_probe.py").read_text().lower()
    assert "not observable" in src and "not claimed" in src
    for bad in ("the server charges", "leaderboard is wrong", "official scores are"):
        assert bad not in src
