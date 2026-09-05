"""What the forced resets cost a policy that actually plays.

The denial is established: a RESET the harness issues after a game over consumes
the agent's per-level budget, and on a real level at its real budget it can fail
a level the same policy otherwise completes. That demonstration used a contrived
play. This asks a different question, of a policy that simply plays: how much of
its budget goes to actions it did not choose, and does that ever change what it
achieved?

The policy is a seeded pseudorandom sequence over the environment's advertised
simple actions. It is not a model and is not a proxy for one; it is a real
policy, which is enough to turn an existence claim into a measurement. Each seed
is run twice against the same environment at the same real budget: once as
shipped, once with the forced reset not incrementing the budget counter. Because
the sequence is fixed in advance, the two runs choose exactly the same actions,
and the only difference between them is the charged reset.

A blind policy rarely finishes a level, so it may rarely be near the boundary
where the reset decides an outcome. If the outcome-difference count comes back
zero, that is the result, and it says the mechanism's practical bite depends on
an agent good enough to finish close to its budget.

Coverage: the six public environments whose advertised action space can be
played blind. The other nineteen are click-based and out of this instrument's
reach; nothing here is a claim about them.

Every statement is about the CLIENT. How the server treats any of this is not
observable to us and is not claimed.

Scope: public environments already fetched to environment_files/, run OFFLINE.
No network, no API key, no model call.

Usage: random_agent_tax.py [--games ...] [--seeds 3] [--smoke]
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import random
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "arc-agi-3-benchmarking"))
sys.path.insert(0, str(ROOT / "scripts"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402
from benchmarking.runtime_models import ModelResponse, NormalizedUsage  # noqa: E402
from death_cost import COMPLEX, GRID_MAX, advertised_actions  # noqa: E402
from harness_probe import MULT, make_agent  # noqa: E402

ENVDIR = ROOT / "environment_files"
API = ROOT / "artifacts" / "api" / "games.json"
CENSUS = ROOT / "artifacts" / "sweep"
RSS_CAP_MB = 900.0

# Kept for the tests that assert the earlier six-environment coverage; the sweep
# now asks each environment what it advertises rather than relying on this.
BLIND = {"ls20": [1, 2, 3, 4], "tr87": [1, 2, 3, 4], "tu93": [1, 2, 3, 4],
         "g50t": [1, 2, 3, 4, 5], "re86": [1, 2, 3, 4, 5], "wa30": [1, 2, 3, 4, 5]}


def peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


def script_for(game: str, baselines: list[int], seed: int,
               actions: list[int] | None = None) -> list[str]:
    """A fixed pseudorandom sequence, long enough that it cannot be exhausted.

    Chosen actions can never exceed the sum of the per-level budgets, because a
    forced reset consumes budget without consuming script. So a script of that
    length always outlives the run, and the stub's exhaustion error can never
    stand in for a real exit reason.
    """
    total = sum(math.ceil(b * MULT) for b in baselines)
    acts = actions if actions is not None else BLIND[game]
    rng = random.Random(f"{game}:{seed}")
    out = []
    for _ in range(total + 8):
        a = rng.choice(acts)
        if a in COMPLEX:
            # A click carries coordinates. They travel in the script entry so the
            # sequence is fixed in advance and both runs of the pair issue the
            # identical click.
            out.append(f"ACTION{a}:{rng.randint(0, GRID_MAX)},{rng.randint(0, GRID_MAX)}")
        else:
            out.append(f"ACTION{a}")
    return out


def run(game_id: str, script: list[str], count_forced: bool) -> dict:
    lg = logging.getLogger("tax"); lg.setLevel(logging.CRITICAL)
    for name in ("benchmarking", "arc_agi.scorecard"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(ENVDIR),
                 recordings_dir=str(ROOT / "artifacts" / "recordings"), logger=lg)
    card_id = arc.create_scorecard(tags=["audit-tax"])
    env = arc.make(game_id, scorecard_id=card_id, save_recording=False)
    baselines = list(env.info.baseline_actions or [])
    agent = make_agent(env, env.info.game_id, baselines, list(script))

    # The harness's own agent attaches coordinates with set_data (agent.py:386)
    # and the wrapper then sends action.action_data (agent.py:574). Do exactly
    # that rather than a private imitation of it. GameAction members are shared,
    # so the data is set immediately before each use.
    clicks = {"issued": 0}

    def scripted(actions):
        if not agent._script:
            raise RuntimeError("script exhausted")
        entry = agent._script.pop(0)
        agent._executed_from_script.append(entry)
        name, _, coords = entry.partition(":")
        action = GameAction.from_name(name)
        if coords:
            x, y = (int(v) for v in coords.split(","))
            action.set_data({"x": x, "y": y})
            clicks["issued"] += 1
        return ModelResponse(output_text=entry, usage=NormalizedUsage()), action, 0, []
    agent._request_with_retries = scripted

    forced_per_level: dict[int, int] = {}
    real_record = agent._record_forced_action_observation

    def spy_record(frames, latest_frame, forced_action):
        lvl = latest_frame.levels_completed
        forced_per_level[lvl] = forced_per_level.get(lvl, 0) + 1
        before = agent._level_action_counter
        real_record(frames, latest_frame, forced_action)
        if not count_forced:
            agent._level_action_counter = before
    agent._record_forced_action_observation = spy_record

    t0 = time.time()
    error = None
    try:
        agent.main()
    except RuntimeError as e:
        error = f"{e} (probe stub, not the harness)"
    seconds = time.time() - t0

    card = json.loads(
        arc.scorecard_manager.scorecards[card_id].cards[env.info.game_id].model_dump_json())
    scored = arc.get_scorecard(card_id)
    envscore = json.loads(scored.model_dump_json())["environments"][0] if scored and scored.environments else None
    budgets = [math.ceil(b * MULT) for b in baselines]
    return dict(count_forced=count_forced, baselines=baselines, budgets=budgets,
                max_actions=sum(budgets),
                forced_per_level={str(k): v for k, v in sorted(forced_per_level.items())},
                forced_total=sum(forced_per_level.values()),
                card_actions=card["actions"], card_resets=card["resets"],
                levels_completed=card["levels_completed"],
                executed_from_script=len(agent._executed_from_script),
                clicks_issued=clicks["issued"],
                executed=list(agent._executed_from_script),
                exit_reason=agent.exit_reason.name if agent.exit_reason else None,
                environment_score=(round(envscore["score"], 9) if envscore else None),
                seconds=round(seconds, 2), error=error)


def pair(game: str, game_id: str, baselines: list[int], seed: int,
         actions: list[int]) -> dict:
    script = script_for(game, baselines, seed, actions)
    shipped = run(game_id, script, True)
    free = run(game_id, script, False)
    # The two runs do NOT execute the same NUMBER of actions, and should not:
    # the uncharged run is not billed for the reset, so it earns one more action
    # per forced reset before the budget stops it. What must hold is that they
    # choose the SAME actions as far as both go -- the shorter is a prefix of the
    # longer -- since only then is the charged reset the sole difference.
    a_exec, b_exec = shipped["executed"], free["executed"]
    k = min(len(a_exec), len(b_exec))
    same_choices = a_exec[:k] == b_exec[:k]
    extra_actions_when_uncharged = len(b_exec) - len(a_exec)
    budgets = shipped["budgets"]
    tax = []
    for lvl, n in shipped["forced_per_level"].items():
        i = int(lvl)
        if i < len(budgets):
            tax.append(dict(level=i, forced=n, budget=budgets[i],
                            share_of_budget=round(n / budgets[i], 9)))
    return dict(game=game, seed=seed, advertised_actions=actions,
                shipped=shipped, uncharged=free,
                same_chosen_actions=same_choices,
                extra_actions_when_uncharged=extra_actions_when_uncharged,
                forced_share_of_counted=round(
                    shipped["forced_total"] / max(1, shipped["forced_total"] + len(a_exec)), 9),
                level_tax=tax,
                forced_share_of_max_actions=round(
                    shipped["forced_total"] / shipped["max_actions"], 9),
                levels_differ=[i for i, (a, b) in enumerate(
                    zip(shipped["levels_completed"], free["levels_completed"])) if a != b],
                exit_differs=shipped["exit_reason"] != free["exit_reason"],
                score_differs=shipped["environment_score"] != free["environment_score"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", nargs="+", default=None,
                    help="default: every public environment")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--smoke", action="store_true",
                    help="one environment, one seed, then report the rate and stop")
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "tax")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    api = {g["game_id"][:4]: (g["game_id"], g["baseline_actions"])
           for g in json.loads(API.read_text())}
    all_games = a.games if a.games else sorted(api)
    games = all_games[:1] if a.smoke else all_games
    seeds = range(1) if a.smoke else range(a.seeds)

    rows, lines = [], []
    t0 = time.time()
    for game in games:
        game_id, baselines = api[game]
        try:
            actions = advertised_actions(game, 1)
        except Exception as e:                       # noqa: BLE001
            lines.append(f"SKIP {game} {type(e).__name__}: {e}")
            continue
        for seed in seeds:
            p = pair(game, game_id, baselines, seed, actions)
            rows.append(p)
            s, f = p["shipped"], p["uncharged"]
            lines.append(
                f"RUN {game} seed={seed} max_actions={s['max_actions']} "
                f"chosen={s['executed_from_script']} forced={s['forced_total']} "
                f"forced_share_of_counted={p['forced_share_of_counted']} "
                f"extra_when_uncharged={p['extra_actions_when_uncharged']} "
                f"shipped_levels={sum(1 for x in s['levels_completed'] if x)} "
                f"uncharged_levels={sum(1 for x in f['levels_completed'] if x)} "
                f"levels_differ={p['levels_differ']} exit_differs={p['exit_differs']} "
                f"same_chosen_actions={p['same_chosen_actions']} "
                f"clicks={s['clicks_issued']} "
                f"exit={s['exit_reason']} seconds={s['seconds']}")

    shares = sorted(r["forced_share_of_counted"] for r in rows)
    lvl_shares = sorted(t["share_of_budget"] for r in rows for t in r["level_tax"])
    n = len(shares)
    med = lambda xs: (xs[len(xs)//2] if len(xs) % 2 else (xs[len(xs)//2-1]+xs[len(xs)//2])/2) if xs else None
    outcome_changes = sum(1 for r in rows if r["levels_differ"])
    elapsed = time.time() - t0
    rss = peak_rss_mb()
    lines.append(
        f"TAX runs={n} games={len(games)} seeds={len(list(seeds))} "
        f"median_forced_share_of_counted={med(shares)} "
        f"max_forced_share_of_counted={shares[-1] if shares else None} "
        f"levels_with_a_forced_reset={len(lvl_shares)} "
        f"median_level_share={med(lvl_shares)} "
        f"max_level_share={lvl_shares[-1] if lvl_shares else None}")
    lines.append(
        f"ENVS games={len(games)} measured={len({r['game'] for r in rows})} "
        f"skipped={len(games) - len({r['game'] for r in rows})}")
    lines.append(
        f"OUTCOME runs={n} runs_where_a_level_differs={outcome_changes} "
        f"runs_where_exit_differs={sum(1 for r in rows if r['exit_differs'])} "
        f"total_extra_actions_when_uncharged={sum(r['extra_actions_when_uncharged'] for r in rows)} "
        f"all_pairs_same_chosen_actions={all(r['same_chosen_actions'] for r in rows)}")
    lines.append(
        f"SUMMARY elapsed_seconds={round(elapsed,1)} "
        f"peak_rss_mb={round(rss,1)} peak_rss_mb_under_{int(RSS_CAP_MB)}={rss < RSS_CAP_MB}"
        + (" MODE=smoke" if a.smoke else ""))
    name = "tax_smoke" if a.smoke else "tax"
    (a.out / f"{name}.log").write_text("\n".join(lines) + "\n")
    for r in rows:
        r["shipped"].pop("executed", None)
        r["uncharged"].pop("executed", None)
    (a.out / f"{name}.json").write_text(json.dumps(dict(runs=rows), indent=1, sort_keys=True) + "\n")
    print("\n".join(lines))
    return 0 if rss < RSS_CAP_MB else 1


if __name__ == "__main__":
    raise SystemExit(main())
