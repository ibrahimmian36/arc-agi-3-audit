"""Can a reset the agent never chose deny it a level it would have completed?

Finding F12 established that the benchmarking harness issues a RESET of its own
after a game over, and that the reset is counted. This probe asks the sharper
question: the harness also stops a level when the counted actions reach the
per-level budget (`math.ceil(baseline * 5.0)`), and the forced reset increments
that same counter (`benchmarking/agent.py:541`, reached from the early return at
line 626, checked against the budget at line 607). So a run can be cut off on an
action the agent did not choose.

Two things are measured, both offline.

S1  A PAIRED counterfactual on the toolkit's fixture game. The same scripted
    policy is run twice against the same game with the same budget. The runs
    differ in exactly one respect: in the counterfactual the forced reset does
    not increment the budget counter. If the shipped run is cut off with the
    level incomplete while the counterfactual completes it, then the forced
    reset -- not the agent's play -- is what failed the level.

    The counterfactual is a measurement device, not a proposal and not a claim
    about the shipped code. It exists to isolate one variable.

S2  The size of the tax on the REAL public set, from the baselines fetched from
    /api/games: what one forced reset costs each of the 183 public levels, as a
    share of that level's budget and as the fall in that level's score on an
    otherwise perfect completion.

Every statement here is about the CLIENT. The server's treatment of a reset is
not observable to us and is not claimed.

Scope: the public harness and toolkit at the pinned commits, run OFFLINE against
the toolkit's own fixture game and against already-fetched public metadata. No
network, no API key, no public environment is played.

Usage: budget_probe.py [--out artifacts/budget]
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import resource
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "arc-agi-3-benchmarking"))
sys.path.insert(0, str(ROOT / "scripts"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from benchmarking.base import ExitReason  # noqa: E402
from harness_probe import MULT, make_agent  # noqa: E402

FIXTURE = ROOT / "vendor" / "ARC-AGI" / "test_environment_files"
GAMES = ROOT / "artifacts" / "api" / "games.json"
SOLVE_L1 = ["ACTION3"] * 4   # bt11 level 1 is solved by four ACTION3
LOSE_L1 = ["ACTION4"] * 4    # and lost by four ACTION4
RSS_CAP_MB = 400.0


def peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


def run(script: list[str], budget: int, count_forced: bool) -> dict:
    """Drive the harness's real loop once.

    count_forced=True is the shipped behaviour. count_forced=False is the
    counterfactual: the forced reset still happens and still reaches the
    environment, it simply does not consume the agent's budget.
    """
    lg = logging.getLogger("budget"); lg.setLevel(logging.CRITICAL)
    for name in ("benchmarking", "arc_agi.scorecard"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(FIXTURE),
                 recordings_dir=str(ROOT / "artifacts" / "recordings"), logger=lg)
    card_id = arc.create_scorecard(tags=["audit-budget"])
    env = arc.make("bt11", scorecard_id=card_id, save_recording=False)

    agent = make_agent(env, env.info.game_id, list(env.info.baseline_actions or []), script)
    budgets = [budget] + [10_000] * 4
    agent._level_action_budgets = list(budgets)
    agent.MAX_ACTIONS = sum(budgets)

    forced = {"n": 0}
    real_record = agent._record_forced_action_observation

    def spy_record(frames, latest_frame, forced_action):
        forced["n"] += 1
        before = agent._level_action_counter
        real_record(frames, latest_frame, forced_action)
        if not count_forced:
            # Undo only the budget increment; the action still happens and is
            # still sent to the environment, exactly as shipped.
            agent._level_action_counter = before
    agent._record_forced_action_observation = spy_record

    error = None
    try:
        agent.main()
    except RuntimeError as e:
        error = f"{e} (probe stub, not the harness)"

    card = json.loads(
        arc.scorecard_manager.scorecards[card_id].cards[env.info.game_id].model_dump_json())
    scored = arc.get_scorecard(card_id)
    envscore = json.loads(scored.model_dump_json())["environments"][0] if scored and scored.environments else None
    return dict(budget=budget, count_forced=count_forced,
                forced_resets=forced["n"],
                harness_action_counter=agent.action_counter,
                level_action_counter=agent._level_action_counter,
                card_actions=card["actions"], card_resets=card["resets"],
                levels_completed=card["levels_completed"],
                exit_reason=agent.exit_reason.name if agent.exit_reason else None,
                environment_score=(round(envscore["score"], 9) if envscore else None),
                error=error)


def denial_pair(script: list[str], budget: int) -> dict:
    """Run the same policy twice and report whether the forced reset decided it."""
    shipped = run(script, budget, count_forced=True)
    counterfactual = run(script, budget, count_forced=False)
    denied = (shipped["levels_completed"] < counterfactual["levels_completed"]
              and shipped["exit_reason"] == ExitReason.ACTION_BUDGET.name
              and shipped["forced_resets"] > 0)
    return dict(budget=budget, shipped=shipped, counterfactual=counterfactual,
                denied_by_forced_reset=denied,
                score_shipped=shipped["environment_score"],
                score_counterfactual=counterfactual["environment_score"])


def sweep_budgets(script: list[str], lo: int, hi: int) -> list[dict]:
    """Every budget in a range, so the boundary of the regime is exhibited."""
    return [denial_pair(script, b) for b in range(lo, hi + 1)]


def denial_window(deaths: int) -> dict:
    """How many budgets does the forced reset decide, for an agent that dies `deaths` times?

    PREREGISTERED PREDICTION, written before this was run: the counterfactual
    completes the level as soon as the budget covers the CHOSEN actions, and the
    shipped harness needs the chosen actions plus one per game over, so the
    window of budgets on which the two disagree should be exactly `deaths` wide.
    If that holds, the exposure is not a knife edge: it grows with every death,
    and an agent that dies often is decided by forced resets over a wide range of
    budgets rather than at a single value.
    """
    script = LOSE_L1 * deaths + SOLVE_L1
    chosen = 4 * deaths + 4
    lo, hi = max(1, chosen - 2), chosen + deaths + 2
    pairs = [denial_pair(script, b) for b in range(lo, hi + 1)]
    hits = [p["budget"] for p in pairs if p["denied_by_forced_reset"]]
    return dict(deaths=deaths, chosen_actions=chosen, budgets_probed=[lo, hi],
                denial_budgets=hits, window_width=len(hits),
                predicted_width=deaths, prediction_holds=len(hits) == deaths)


def level_tax(games: list[dict]) -> dict:
    """What one forced reset costs each real public level.

    Two quantities per level, both under the verified client rule:
      share  one action as a fraction of that level's budget ceil(5*baseline)
      fall   the fall in that level's score, from a perfect completion in
             `baseline` actions to the same completion plus one forced reset,
             under score = min(115, (baseline/actions)^2 * 100)
    """
    def level_score(baseline: int, actions: int) -> float:
        return min(115.0, (baseline / actions) ** 2 * 100.0)

    rows = []
    for g in games:
        for idx, b in enumerate(g.get("baseline_actions") or []):
            budget = math.ceil(b * MULT)
            perfect = level_score(b, b)
            with_one = level_score(b, b + 1)
            rows.append(dict(game_id=g["game_id"], level=idx, baseline=b, budget=budget,
                             share_of_budget=1.0 / budget,
                             score_perfect=round(perfect, 9),
                             score_after_one_forced_reset=round(with_one, 9),
                             fall=round(perfect - with_one, 9)))
    rows.sort(key=lambda r: -r["fall"])
    falls = sorted(r["fall"] for r in rows)
    shares = sorted(r["share_of_budget"] for r in rows)
    n = len(rows)
    med = lambda xs: xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    return dict(levels=n, environments=len(games),
                worst=rows[0], best=rows[-1],
                median_fall=round(med(falls), 9),
                median_share_of_budget=round(med(shares), 9),
                max_share_of_budget=round(shares[-1], 9),
                deaths_to_exhaust_smallest_budget=min(r["budget"] for r in rows),
                rows=rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "budget")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    script = LOSE_L1 + SOLVE_L1          # die once, then solve: 8 chosen, 1 forced
    pairs = sweep_budgets(script, 6, 11)
    denials = [p for p in pairs if p["denied_by_forced_reset"]]

    windows = [denial_window(d) for d in (0, 1, 2, 3)]

    games = json.loads(GAMES.read_text())
    tax = level_tax(games)

    lines = []
    for p in pairs:
        s, c = p["shipped"], p["counterfactual"]
        lines.append(
            f"B{p['budget']:<3d} shipped: counted={s['card_actions']} levels={s['levels_completed']} "
            f"exit={s['exit_reason']} score={s['environment_score']} | "
            f"counterfactual: counted={c['card_actions']} levels={c['levels_completed']} "
            f"exit={c['exit_reason']} score={c['environment_score']} | "
            f"denied_by_forced_reset={p['denied_by_forced_reset']}")
    for win in windows:
        lines.append(
            f"WINDOW deaths={win['deaths']} chosen={win['chosen_actions']} "
            f"denial_budgets={win['denial_budgets']} width={win['window_width']} "
            f"predicted={win['predicted_width']} holds={win['prediction_holds']}")
    w = tax["worst"]
    lines.append(
        f"TAX levels={tax['levels']} environments={tax['environments']} "
        f"worst={w['game_id']}#{w['level']} baseline={w['baseline']} budget={w['budget']} "
        f"perfect={w['score_perfect']} after_one={w['score_after_one_forced_reset']} "
        f"fall={w['fall']} share={round(w['share_of_budget'], 9)} "
        f"median_fall={tax['median_fall']} median_share={tax['median_share_of_budget']} "
        f"max_share={tax['max_share_of_budget']} smallest_budget={tax['deaths_to_exhaust_smallest_budget']}")
    rss = peak_rss_mb()
    lines.append(
        f"SUMMARY pairs={len(pairs)} denials={len(denials)} "
        f"denial_budgets={[p['budget'] for p in denials]} "
        f"window_prediction_holds={all(w['prediction_holds'] for w in windows)} "
        f"peak_rss_mb_under_{int(RSS_CAP_MB)}={rss < RSS_CAP_MB}")

    (a.out / "budget.log").write_text("\n".join(lines) + "\n")
    (a.out / "budget.json").write_text(json.dumps(
        dict(pairs=pairs, windows=windows, tax=tax), indent=1, sort_keys=True) + "\n")
    print("\n".join(lines))
    return 0 if rss < RSS_CAP_MB else 1


if __name__ == "__main__":
    raise SystemExit(main())
