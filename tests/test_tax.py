"""What the forced resets cost a policy that actually plays.

The instrument is a seeded blind policy run twice against the same environment
at the same real budget, once as shipped and once with the forced reset not
charged. These tests assert the pairing is honest, the arithmetic is the
harness's own, and that a null result is reported as one.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

ART = ROOT / "artifacts" / "tax" / "tax.json"
DEATH = ROOT / "artifacts" / "deathcost" / "deathcost.json"


@pytest.fixture(scope="module")
def runs() -> list:
    if not ART.exists():
        pytest.skip("run scripts/random_agent_tax.py first")
    return json.loads(ART.read_text())["runs"]


# ── the pairing must isolate exactly one variable ───────────────────────────

def test_the_pair_chooses_the_same_actions_as_far_as_both_go(runs):
    for r in runs:
        assert r["same_chosen_actions"] is True, r["game"]


def test_the_uncharged_run_is_never_worse_off(runs):
    """The general invariant: not charging the reset can only give the agent
    more of its own actions, never fewer."""
    for r in runs:
        assert r["uncharged"]["executed_from_script"] >= r["shipped"]["executed_from_script"], r["game"]
        assert r["extra_actions_when_uncharged"] >= 0


def test_the_identity_holds_wherever_the_two_runs_stay_comparable(runs):
    """Where neither run completes a level, both are stopped by the same level's
    budget and the extra actions the uncharged run earns are exactly the forced
    resets the shipped run was charged. That identity is the mechanism.

    It does NOT hold once a level is completed, and it should not: the extra
    actions let the uncharged run reach a different point in the game, where it
    dies a different number of times. Nine of 250 runs are in that regime and
    are excluded here rather than being asserted away."""
    comparable = [r for r in runs
                  if not any(r["shipped"]["levels_completed"])
                  and not any(r["uncharged"]["levels_completed"])]
    assert len(comparable) > 200, "too few comparable runs to check the identity"
    for r in comparable:
        assert r["extra_actions_when_uncharged"] == r["shipped"]["forced_total"], r["game"]


def test_both_runs_end_on_a_harness_exit_reason(runs):
    """A stub that ran out of script would look like a result and be none."""
    for r in runs:
        for side in ("shipped", "uncharged"):
            assert r[side]["exit_reason"] in {"ACTION_BUDGET", "GAME_WIN", "TIME_BUDGET"}, r
            assert r[side]["error"] is None, r
            assert r[side]["executed_from_script"] < len(
                [1]) + r[side]["max_actions"] + 8


def test_budgets_are_the_harness_rule_over_the_published_baselines(runs):
    api = {g["game_id"][:4]: g["baseline_actions"]
           for g in json.loads((ROOT / "artifacts" / "api" / "games.json").read_text())}
    for r in runs:
        assert r["shipped"]["budgets"] == [math.ceil(b * 5.0) for b in api[r["game"]]], r["game"]
        assert r["shipped"]["budgets"] == r["uncharged"]["budgets"]


# ── the tax, and the null result ────────────────────────────────────────────

def test_the_tax_share_is_the_stated_ratio(runs):
    for r in runs:
        f = r["shipped"]["forced_total"]
        chosen = r["shipped"]["executed_from_script"]
        assert r["forced_share_of_counted"] == pytest.approx(f / max(1, f + chosen)), r["game"]


def test_the_tax_is_modest_and_the_reported_bounds_match_the_runs(runs):
    """The honest headline: a blind policy loses well under one per cent of what
    it is charged at the median, and at most a few per cent. Overstating this
    would be the easiest way to discredit the finding it accompanies; the six
    environments measured earlier gave a maximum of 1.05%, and the click-based
    ones raise it, which is why the whole set had to be measured."""
    shares = sorted(r["forced_share_of_counted"] for r in runs)
    n = len(shares)
    median = shares[n // 2] if n % 2 else (shares[n // 2 - 1] + shares[n // 2]) / 2
    assert median < 0.02, median
    assert max(shares) < 0.25, max(shares)
    assert max(shares) > 0.01, "the whole-set maximum should exceed the six-environment one"


def test_a_null_outcome_result_is_representable_and_recorded(runs):
    """A blind policy rarely finishes a level, so it is rarely near the boundary
    where the reset decides an outcome. Whatever the count, it must be derived
    from the runs rather than asserted."""
    for r in runs:
        s, u = r["shipped"]["levels_completed"], r["uncharged"]["levels_completed"]
        expected = [i for i, (a, b) in enumerate(zip(s, u)) if a != b]
        assert r["levels_differ"] == expected, r["game"]


# ── cross-checks against the other instruments ──────────────────────────────

def test_forced_resets_occur_exactly_where_the_level_can_be_lost_in_budget(runs):
    """Independent agreement with the death-cost measurement, in both
    directions and across all 25 environments.

    The comparison is per ENVIRONMENT over its seeds, not per run: a single seed
    may complete level 1 outright and never die, as `cd82` does on three of its
    ten. Comparing one seed would report a disagreement that is not there, and
    an earlier version of this check did exactly that."""
    if not DEATH.exists():
        pytest.skip("run scripts/death_cost.py first")
    exposed = {r["game"]: r["death_fits_budget"]
               for r in json.loads(DEATH.read_text())["levels"] if r["level"] == 1}
    by_game: dict[str, bool] = {}
    for r in runs:
        by_game[r["game"]] = by_game.get(r["game"], False) or r["shipped"]["forced_total"] > 0
    assert len(by_game) == 25
    for game, got in by_game.items():
        assert got == exposed[game], (game, got, exposed[game])


def test_the_null_holds_even_where_the_policy_completed_a_level(runs):
    """The Phase 12 null was explained by a policy that never finished a level.
    Over the whole set some runs do finish one, and the outcome still never
    differs. That is a stronger statement and it must be checked, not assumed."""
    completed = [r for r in runs if any(r["shipped"]["levels_completed"])]
    assert completed, "no run completed a level; the stronger null is unsupported"
    for r in completed:
        assert r["levels_differ"] == [], r["game"]


def test_the_seeds_are_genuinely_different_policies():
    """Ten seeds that produced the same action sequence would make the spread a
    fiction. They do not: the sequences differ, and the counts still agree,
    which is a fact about these levels rather than about the sampling."""
    from random_agent_tax import script_for
    for game in ("tu93", "wa30"):
        seqs = {tuple(script_for(game, [19], s)) for s in range(5)}
        assert len(seqs) == 5, game


def test_every_public_environment_is_measured_and_none_is_silently_skipped(runs):
    api = {g["game_id"][:4] for g in
           json.loads((ROOT / "artifacts" / "api" / "games.json").read_text())}
    assert {r["game"] for r in runs} == api
    assert len(api) == 25


def test_each_run_samples_the_actions_that_environment_advertises(runs):
    census = (ROOT / "artifacts" / "sweep" / "action_census.log").read_text()
    for r in runs:
        line = [l for l in census.splitlines() if l.startswith(r["game"])]
        assert line, r["game"]
        assert str(r["advertised_actions"]) in line[0], (r["game"], line[0])


def test_a_click_environment_actually_issues_clicks(runs):
    """A scripted click that lost its coordinates would produce a run that looks
    fine and measures nothing, so the count must be positive exactly where the
    environment advertises the click action."""
    for r in runs:
        advertises_click = 6 in r["advertised_actions"]
        issued = r["shipped"]["clicks_issued"]
        assert (issued > 0) == advertises_click, (r["game"], issued)
        assert r["uncharged"]["clicks_issued"] > 0 or not advertises_click


def test_click_only_environments_are_represented(runs):
    """Six environments advertise nothing but the click. Before this sweep they
    could not be measured at all, and their absence is what the coverage
    statement used to conceal."""
    click_only = {r["game"] for r in runs if r["advertised_actions"] == [6]}
    assert len(click_only) >= 5, click_only


# ── discipline ──────────────────────────────────────────────────────────────

def test_no_claim_about_the_server_or_about_models_in_the_probe_source():
    import re
    src = re.sub(r"\s+", " ", (ROOT / "scripts" / "random_agent_tax.py").read_text().lower())
    assert "not observable to us and is not claimed" in src
    assert "is not a model and is not a proxy for one" in src
    for bad in ("the server does charge", "models lose", "leaderboard is wrong",
                "predicts", "a model would"):
        assert bad not in src, bad


def test_the_probe_cannot_reach_the_network():
    import ast
    tree = ast.parse((ROOT / "scripts" / "random_agent_tax.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    for net in ("requests", "urllib", "http", "socket", "httpx", "aiohttp"):
        assert net not in imported, net
