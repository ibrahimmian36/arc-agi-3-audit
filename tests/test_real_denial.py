"""The forced-reset mechanism measured on real benchmark levels.

Two artefacts are under test. `deathcost` asks whether an agent can be lost
inside the budget its published baseline implies, which is the precondition for
the mechanism to bite at all. `realdenial` runs the denial itself on a real
environment at that real budget.

The tests must accept an immune level as readily as an exposed one: a level
whose shortest losing line exceeds its whole budget cannot exhibit this, and
that is a result, not a failure.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

DEATH = ROOT / "artifacts" / "deathcost" / "deathcost.json"
ART = ROOT / "artifacts" / "realdenial" / "realdenial.json"


@pytest.fixture(scope="module")
def death() -> list:
    if not DEATH.exists():
        pytest.skip("run scripts/death_cost.py first")
    return json.loads(DEATH.read_text())["levels"]


@pytest.fixture(scope="module")
def denial() -> list:
    if not ART.exists():
        pytest.skip("run scripts/real_env_denial.py first")
    return json.loads(ART.read_text())["results"]


# ── the precondition: can the agent be lost inside its budget? ───────────────

def test_every_budget_is_the_harness_rule_over_the_published_baseline(death):
    """We must never supply a budget; it has to follow from the real baseline."""
    for r in death:
        if r.get("error"):
            continue
        assert r["budget"] == math.ceil(r["baseline"] * 5.0), r


def test_baselines_match_the_fetched_api_response(death):
    api = {g["game_id"]: g["baseline_actions"]
           for g in json.loads((ROOT / "artifacts" / "api" / "games.json").read_text())}
    for r in death:
        if r.get("error"):
            continue
        assert api[r["game_id"]][r["level"] - 1] == r["baseline"], r


def test_every_losing_line_is_verified_by_replay(death):
    """A losing line is a witness, and a witness that is not replayed is a claim."""
    for r in death:
        if r.get("error") or r.get("shortest_observed_loss") is None:
            continue
        assert r["witness_replays_to_game_over"] is True, r
        assert len(r["losing_line"]) == r["shortest_observed_loss"], r


def test_exposure_is_the_stated_comparison_and_nothing_more(death):
    for r in death:
        if r.get("error"):
            continue
        b = r.get("shortest_observed_loss")
        assert r["death_fits_budget"] == (b is not None and b < r["budget"]), r


def test_a_level_with_no_observed_loss_is_not_called_immune(death):
    """Random play failing to die proves nothing. The field must stay false, and
    the honest reading is `not established`, never `cannot be lost`."""
    for r in death:
        if r.get("error"):
            continue
        if r.get("shortest_observed_loss") is None:
            assert r["death_fits_budget"] is False
            assert r["deaths_affordable"] == 0


def test_both_outcomes_are_present_so_the_measure_discriminates(death):
    exposed = [r for r in death if r.get("death_fits_budget")]
    other = [r for r in death if not r.get("error") and not r.get("death_fits_budget")]
    assert exposed and other, "a measure that returns one answer everywhere measures nothing"


def test_the_random_bound_never_beats_the_exhaustive_one(death):
    """ls20 level 1 was also searched exhaustively: the shortest losing line is
    129. Random play can never find a shorter one than the true shortest, so a
    bound below 129 would mean one of the two instruments is wrong."""
    ls20 = [r for r in death if r["game"] == "ls20" and r["level"] == 1]
    assert ls20, "ls20 level 1 missing"
    assert ls20[0]["shortest_observed_loss"] >= 129


# ── the denial itself, on a real level at its real budget ────────────────────

def test_a_real_level_is_denied_by_a_reset_the_agent_did_not_choose(denial):
    hits = [(r, p) for r in denial for p in r["pairs"] if p["denied_by_forced_reset"]]
    assert hits, "no denial on a real level; the fixture result would stand alone"
    for r, p in hits:
        s, c = p["shipped"], p["counterfactual"]
        assert s["exit_reason"] == "ACTION_BUDGET"
        assert s["levels_completed"][0] == 0 and c["levels_completed"][0] >= 1
        assert s["environment_score"] == 0.0 and c["environment_score"] > 0.0
        # the budget is the harness's own, from the published baseline
        assert p["budget"] == s["level1_budget"] == math.ceil(r["baseline"] * 5.0)


def test_the_real_pair_differs_only_in_the_charged_reset(denial):
    for r in denial:
        for p in r["pairs"]:
            s, c = p["shipped"], p["counterfactual"]
            assert s["count_forced"] is True and c["count_forced"] is False
            assert s["forced_resets"] == c["forced_resets"] == p["deaths"]
            assert s["budgets"] == c["budgets"]
            assert s["card_resets"] == c["card_resets"]


def test_the_boundary_is_exhibited_on_the_real_level(denial):
    """Below the window both complete; at it only the counterfactual does."""
    for r in denial:
        lo = min(r["denial_chosen_totals"])
        below = [p for p in r["pairs"] if p["chosen_target"] < lo]
        assert below, "the sweep must bracket the window from below"
        for p in below:
            assert p["shipped"]["levels_completed"][0] >= 1
            assert p["counterfactual"]["levels_completed"][0] >= 1


def test_window_width_equals_the_deaths_on_the_real_level(denial):
    for r in denial:
        assert r["window_width"] == r["deaths"] == r["predicted_width"], r
        assert r["window_holds"] is True
        assert r["all_predictions_hold"] is True


def test_the_lines_used_in_the_real_run_were_replay_verified(denial):
    for r in denial:
        assert r["checks"]["losing_replays_to_game_over"] == "GAME_OVER"
        assert r["checks"]["witness_replays_to_win"] == "WIN"


# ── discipline ──────────────────────────────────────────────────────────────

def test_no_claim_about_the_server_in_either_probe_source():
    """Each probe must carry the disclaimer and must never assert what the
    server does. The banned forms are assertive ones: a disclaimer necessarily
    mentions the server, so banning the noun would flag the disclaimer itself."""
    for name in ("real_env_denial.py", "death_cost.py"):
        src = (ROOT / "scripts" / name).read_text().lower()
        assert "not observable" in src and "not claimed" in src, name
        for bad in ("the server does charge", "the server counts", "the server enforces",
                    "leaderboard is wrong", "official scores are", "models are scored wrongly"):
            assert bad not in src, (name, bad)


def test_neither_probe_can_reach_the_network_or_the_private_sets():
    """Checked by what the source can DO, not by which words it uses: both
    files declare the scope boundary in prose, so a phrase search would flag the
    declaration itself."""
    import ast
    for name in ("real_env_denial.py", "death_cost.py"):
        path = ROOT / "scripts" / name
        tree = ast.parse(path.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for net in ("requests", "urllib", "http", "socket", "httpx", "aiohttp"):
            assert net not in imported, (name, net)
        # No literal URL anywhere, in code or docstring.
        for s_node in ast.walk(tree):
            if isinstance(s_node, ast.Constant) and isinstance(s_node.value, str):
                assert "http://" not in s_node.value and "https://" not in s_node.value, name
        # Only the public environments directory is ever opened.
        src = path.read_text()
        assert "environment_files" in src
        for bad in ("semi_private", "semiprivate_dir", "private_environments"):
            assert bad not in src, (name, bad)


def test_the_real_environment_score_re_derives_from_the_published_rule(denial):
    """An independent derivation of the counterfactual's score, from the level
    weights and the published baseline, without going through the scorer.

    It also shows the reset is charged twice over: even where it does not deny
    the level, the scorecard counts it, so the winning run is scored on 96
    actions rather than the 95 the agent chose.
    """
    api = {g["game_id"]: g["baseline_actions"]
           for g in json.loads((ROOT / "artifacts" / "api" / "games.json").read_text())}
    for r in denial:
        for p in r["pairs"]:
            c = p["counterfactual"]
            if c["levels_completed"][0] < 1:
                continue
            baselines = api[r["game"]]
            weights = sum(range(1, len(baselines) + 1))
            counted = c["card_actions"][0]
            assert counted == p["chosen_target"] + p["deaths"], (
                "the scorecard must charge the forced reset even when the level completes")
            level_score = min(115.0, (baselines[0] / counted) ** 2 * 100.0)
            assert c["environment_score"] == pytest.approx(level_score / weights, abs=1e-9), p
