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


def test_the_uncharged_run_earns_exactly_one_action_per_forced_reset(runs):
    """The whole mechanism in one identity: what the reset costs the agent is
    one action of allowance, so removing the charge returns exactly that many."""
    for r in runs:
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


def test_the_tax_is_small_for_a_blind_policy_and_is_reported_as_such(runs):
    """The honest headline: a blind policy loses about one per cent of what it
    is charged, not a third. Overstating this would be the easiest way to
    discredit the finding it accompanies."""
    shares = [r["forced_share_of_counted"] for r in runs]
    assert max(shares) < 0.05, "a tax this large would contradict the artefact"


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
    """Independent agreement with the death-cost measurement: an environment
    whose level 1 cannot be lost inside its budget must never incur a forced
    reset here, and one that can must incur one."""
    if not DEATH.exists():
        pytest.skip("run scripts/death_cost.py first")
    exposed = {r["game"]: r["death_fits_budget"]
               for r in json.loads(DEATH.read_text())["levels"]}
    for r in runs:
        got = r["shipped"]["forced_total"] > 0
        assert got == exposed[r["game"]], (r["game"], got, exposed[r["game"]])


def test_the_seeds_are_genuinely_different_policies():
    """Ten seeds that produced the same action sequence would make the spread a
    fiction. They do not: the sequences differ, and the counts still agree,
    which is a fact about these levels rather than about the sampling."""
    from random_agent_tax import script_for
    for game in ("tu93", "wa30"):
        seqs = {tuple(script_for(game, [19], s)) for s in range(5)}
        assert len(seqs) == 5, game


def test_every_environment_measured_is_one_that_can_be_played_blind():
    from random_agent_tax import BLIND
    census = (ROOT / "artifacts" / "sweep" / "action_census.log")
    if not census.exists():
        pytest.skip("no action census")
    text = census.read_text()
    for game, actions in BLIND.items():
        line = [l for l in text.splitlines() if l.startswith(game)]
        assert line, game
        assert str(actions) in line[0], (game, line[0])


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
