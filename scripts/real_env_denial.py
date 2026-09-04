"""The forced-reset denial on a real benchmark level, at its real budget.

Phase 10 showed that a RESET the harness issues after a game over consumes the
agent's per-level action budget, and that at some budgets it is what fails a
level the agent would otherwise have completed. That demonstration used the
toolkit's fixture game and a budget we chose. The obvious objection is that a
test fixture is not the benchmark.

This probe answers it on a real public environment, at the budget the harness
derives from that environment's real published human baseline, which we do not
supply and do not override.

For each level it:

  1. finds a LOSING LINE, the shortest action sequence from the level's start
     state that reaches GAME_OVER, by breadth-first search over the shipped
     game under hard caps;
  2. finds a FILLER action that leaves the state unchanged, so budget can be
     spent without winning, losing or advancing the level;
  3. builds a policy that dies a chosen number of times, spends filler, then
     plays the verified winning witness, with the CHOSEN actions summing to a
     target;
  4. runs that policy twice through the harness's own control loop, differing
     in exactly one respect: whether the forced reset increments the budget
     counter.

The second run is a measurement device for isolating one variable. It is not a
proposal, and no claim is made that the shipped code should behave that way.

Every statement is about the CLIENT. Whether the server charges such a reset, or
enforces the budget the same way, is not observable to us and is not claimed.

Scope: the public environments already fetched to environment_files/, run
OFFLINE. No network, no API key, no semi-private or private environment.

Usage: real_env_denial.py [--games ls20 tu93] [--out artifacts/realdenial]
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import random
import resource
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "arc-agi-3-benchmarking"))
sys.path.insert(0, str(ROOT / "scripts"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from benchmarking.base import ExitReason  # noqa: E402
from harness_probe import MULT, make_agent  # noqa: E402
from arcengine import ActionInput, GameAction  # noqa: E402
from state_graph import fast_copy, make_game, state_key, status  # noqa: E402

ENVDIR = ROOT / "environment_files"


def act(g, a: int) -> None:
    """Apply one action to the shipped game, exactly as the enumerator does."""
    g.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)

MINACT = ROOT / "artifacts" / "minactions"
API = ROOT / "artifacts" / "api" / "games.json"
RSS_CAP_MB = 800.0


def peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


# ── finding the lines on the shipped game ────────────────────────────────────

def find_lines(game: str, level: int, max_states: int, max_rss_mb: float) -> dict:
    """Shortest losing line, and a filler action, found by search not assumption."""
    full_id, g0 = make_game(game, level - 1, ENVDIR)
    actions = [1, 2, 3, 4]
    start_key = state_key(g0)

    # A way to spend budget without winning, losing or advancing: the shortest
    # action cycle that returns the level to its start state. A single action
    # rarely qualifies -- these games count steps -- so search short sequences.
    filler_cycle = None
    frontier = [((), g0)]
    for depth in range(1, 5):
        nxt = []
        for path, g in frontier:
            for a in actions:
                h = fast_copy(g)
                act(h, a)
                if status(h, level - 1) != "PLAY":
                    continue
                q = path + (a,)
                if state_key(h) == start_key:
                    filler_cycle = list(q)
                    break
                nxt.append((q, h))
            if filler_cycle:
                break
        if filler_cycle:
            break
        frontier = nxt
    filler = filler_cycle[0] if (filler_cycle and len(filler_cycle) == 1) else None

    seen = {start_key: ()}
    q = deque([(g0, ())])
    losing, explored = None, 0
    while q and losing is None:
        g, path = q.popleft()
        explored += 1
        if explored % 2000 == 0 and peak_rss_mb() > max_rss_mb:
            raise MemoryError(f"search exceeded {max_rss_mb} MB")
        if len(seen) > max_states:
            break
        for a in actions:
            h = fast_copy(g)
            act(h, a)
            st = status(h, level - 1)
            if st == "GAME_OVER":
                losing = path + (a,)
                break
            if st != "PLAY":
                continue
            k = state_key(h)
            if k in seen:
                continue
            seen[k] = path + (a,)
            q.append((h, path + (a,)))
    return dict(game=full_id, level=level, filler_action=filler,
                filler_cycle=filler_cycle,
                filler_cycle_length=(len(filler_cycle) if filler_cycle else None),
                losing_line=list(losing) if losing else None,
                losing_line_length=(len(losing) if losing else None),
                states_explored=explored, states_seen=len(seen),
                search_complete=losing is not None)


def reachability(game: str, level: int, max_states: int, max_rss_mb: float) -> dict:
    """Can the agent reach GAME_OVER at all within its own action budget?

    The denial needs a game over: no death, no forced reset, no exposure. So the
    first question about any real level is whether the shortest losing line fits
    inside the budget the level's published baseline implies. Where it does not,
    the level is immune to the mechanism, and saying so is as much a result as
    finding a level that is exposed.
    """
    art = json.loads((MINACT / f"{game}_L{level}.json").read_text())
    baseline = art["baseline"]
    budget = math.ceil(baseline * MULT)
    lines = find_lines(game, level, max_states, max_rss_mb)
    ll = lines["losing_line_length"]
    return dict(game=lines["game"], level=level, baseline=baseline, budget=budget,
                optimum=art.get("optimum"), losing_line_length=ll,
                filler_action=lines["filler_action"],
                filler_cycle_length=lines["filler_cycle_length"],
                states_seen=lines["states_seen"],
                search_found_a_loss=lines["search_complete"],
                death_fits_budget=(ll is not None and ll < budget),
                deaths_affordable=(budget // ll if ll else 0))


def replay(game: str, level: int, script: list[int]) -> dict:
    """Replay a sequence on the shipped game and report where it ends."""
    _, g = make_game(game, level - 1, ENVDIR)
    st = "PLAY"
    for a in script:
        act(g, a)
        st = status(g, level - 1)
        if st != "PLAY":
            break
    return dict(final_status=st, steps=len(script))


# ── driving the harness at the real budget ───────────────────────────────────

def run(game_id: str, script: list[str], count_forced: bool) -> dict:
    lg = logging.getLogger("realdenial"); lg.setLevel(logging.CRITICAL)
    for name in ("benchmarking", "arc_agi.scorecard"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(ENVDIR),
                 recordings_dir=str(ROOT / "artifacts" / "recordings"), logger=lg)
    card_id = arc.create_scorecard(tags=["audit-realdenial"])
    env = arc.make(game_id, scorecard_id=card_id, save_recording=False)
    baselines = list(env.info.baseline_actions or [])
    # The budget is the harness's own, derived from the published baseline.
    agent = make_agent(env, env.info.game_id, baselines, script)

    forced = {"n": 0}
    real_record = agent._record_forced_action_observation

    def spy_record(frames, latest_frame, forced_action):
        forced["n"] += 1
        before = agent._level_action_counter
        real_record(frames, latest_frame, forced_action)
        if not count_forced:
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
    return dict(count_forced=count_forced, baselines=baselines,
                budgets=list(agent._level_action_budgets),
                level1_budget=agent._level_action_budgets[0] if agent._level_action_budgets else None,
                forced_resets=forced["n"], card_actions=card["actions"],
                card_resets=card["resets"], levels_completed=card["levels_completed"],
                exit_reason=agent.exit_reason.name if agent.exit_reason else None,
                environment_score=(round(envscore["score"], 9) if envscore else None),
                error=error)


def build_script(lines: dict, witness: list[int], deaths: int, chosen_target: int,
                 filler: int) -> list[str] | None:
    """deaths x losing line, then filler, then the winning witness."""
    losing = lines["losing_line"]
    fixed = deaths * len(losing) + len(witness)
    pad = chosen_target - fixed
    if pad < 0 or filler is None:
        return None
    seq = list(losing) * deaths + [filler] * pad + list(witness)
    assert len(seq) == chosen_target
    return [f"ACTION{a}" for a in seq]


def denial_pair(game_id: str, script: list[str]) -> dict:
    shipped = run(game_id, script, True)
    counter = run(game_id, script, False)
    denied = (shipped["levels_completed"] < counter["levels_completed"]
              and shipped["exit_reason"] == ExitReason.ACTION_BUDGET.name
              and shipped["forced_resets"] > 0)
    return dict(chosen=len(script), shipped=shipped, counterfactual=counter,
                denied_by_forced_reset=denied)


def find_detour(game: str, level: int, prefix: list[int], witness: list[int],
                pad: int, tries: int = 64, seed: int = 0) -> list[int] | None:
    """A pad-length detour that still leaves the witness winning.

    These games count steps, so no action sequence returns the level to its
    exact start state and there is no filler in the usual sense. What there is
    is slack: the agent can wander and still win, as long as it does not run out
    of the level's own steps. We search for such a wander and VERIFY it by
    replaying the whole line on the shipped game.
    """
    if pad < 0:
        return None
    if pad == 0:
        return []
    rng = random.Random(seed)
    cands = [[a, b] * (pad // 2) + ([a] if pad % 2 else [])
             for a in (1, 2, 3, 4) for b in (1, 2, 3, 4)]
    cands += [[rng.choice((1, 2, 3, 4)) for _ in range(pad)] for _ in range(tries)]
    for c in cands:
        if len(c) != pad:
            continue
        st = replay(game, level, prefix + c + witness)["final_status"]
        if st == "WIN":
            return c
    return None


def study(game: str, level: int, deaths: int, seed: int = 0) -> dict:
    """The denial on a real level, at the budget its real baseline implies."""
    art = json.loads((MINACT / f"{game}_L{level}.json").read_text())
    witness, baseline = art["witness"], art["baseline"]
    budget = math.ceil(baseline * MULT)
    dc = {r["game"]: r for r in
          json.loads((ROOT / "artifacts" / "deathcost" / "deathcost.json").read_text())["levels"]}
    losing = dc[game]["losing_line"]
    if losing is None:
        return dict(game=game, level=level, skipped="no losing line is known")
    game_id = dc[game]["game_id"]

    checks = dict(
        losing_replays_to_game_over=replay(game, level, losing)["final_status"],
        witness_replays_to_win=replay(game, level, witness)["final_status"])

    pairs = []
    for chosen in range(budget - deaths - 1, budget + 1):
        pad = chosen - deaths * len(losing) - len(witness)
        detour = find_detour(game, level, [], witness, pad, seed=seed)
        if detour is None:
            continue
        seq = losing * deaths + detour + witness
        assert len(seq) == chosen
        script = [f"ACTION{a}" for a in seq]
        p = denial_pair(game_id, script)
        p.update(deaths=deaths, chosen_target=chosen, budget=budget,
                 pad=pad, losing_line_length=len(losing), witness_length=len(witness))
        p["predicted_shipped_completes"] = (chosen + deaths) <= budget
        p["predicted_counterfactual_completes"] = chosen <= budget
        p["prediction_holds"] = (
            (p["shipped"]["levels_completed"][0] >= 1) == p["predicted_shipped_completes"]
            and (p["counterfactual"]["levels_completed"][0] >= 1) == p["predicted_counterfactual_completes"])
        pairs.append(p)

    hits = [p["chosen_target"] for p in pairs if p["denied_by_forced_reset"]]
    return dict(game=game_id, short=game, level=level, baseline=baseline, budget=budget,
                deaths=deaths, losing_line_length=len(losing), witness_length=len(witness),
                checks=checks, pairs=pairs,
                denial_chosen_totals=hits, window_width=len(hits),
                predicted_width=deaths, window_holds=len(hits) == deaths,
                all_predictions_hold=all(p["prediction_holds"] for p in pairs))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", nargs="+", default=["tu93"])
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--deaths", type=int, default=1)
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "realdenial")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    api = {g["game_id"]: g["baseline_actions"] for g in json.loads(API.read_text())}
    results, lines_out = [], []
    for game in a.games:
        r = study(game, a.level, a.deaths)
        if r.get("skipped"):
            lines_out.append(f"SKIP {game} L{a.level} {r['skipped']}")
            continue
        r["baseline_matches_api"] = api.get(r["game"], [None])[a.level - 1] == r["baseline"]
        results.append(r)
        lines_out.append(
            f"SETUP {r['short']} L{a.level} baseline={r['baseline']} budget={r['budget']} "
            f"losing_line={r['losing_line_length']} witness={r['witness_length']} "
            f"losing_replays={r['checks']['losing_replays_to_game_over']} "
            f"witness_replays={r['checks']['witness_replays_to_win']} "
            f"baseline_matches_api={r['baseline_matches_api']}")
        for p in r["pairs"]:
            sh, c = p["shipped"], p["counterfactual"]
            lines_out.append(
                f"PAIR {r['short']} L{a.level} deaths={p['deaths']} chosen={p['chosen_target']} "
                f"budget={p['budget']} | shipped: counted={sh['card_actions'][0]} "
                f"levels={sh['levels_completed'][0]} exit={sh['exit_reason']} "
                f"score={sh['environment_score']} | counterfactual: "
                f"levels={c['levels_completed'][0]} exit={c['exit_reason']} "
                f"score={c['environment_score']} | denied={p['denied_by_forced_reset']} "
                f"prediction_holds={p['prediction_holds']}")
        lines_out.append(
            f"WINDOW {r['short']} L{a.level} deaths={r['deaths']} "
            f"denial_chosen_totals={r['denial_chosen_totals']} width={r['window_width']} "
            f"predicted={r['predicted_width']} holds={r['window_holds']} "
            f"all_predictions_hold={r['all_predictions_hold']}")

    rss = peak_rss_mb()
    denials = sum(1 for r in results for p in r["pairs"] if p["denied_by_forced_reset"])
    lines_out.append(
        f"SUMMARY games={len(results)} denials={denials} "
        f"all_windows_hold={all(r['window_holds'] for r in results)} "
        f"all_baselines_match_api={all(r['baseline_matches_api'] for r in results)} "
        f"peak_rss_mb_under_{int(RSS_CAP_MB)}={rss < RSS_CAP_MB}")
    (a.out / "realdenial.log").write_text("\n".join(lines_out) + "\n")
    (a.out / "realdenial.json").write_text(
        json.dumps(dict(results=results), indent=1, sort_keys=True) + "\n")
    print("\n".join(lines_out))
    return 0 if rss < RSS_CAP_MB else 1


if __name__ == "__main__":
    raise SystemExit(main())
