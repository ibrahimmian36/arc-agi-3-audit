"""How cheaply can an agent die, against the budget it is given?

The forced-reset denial needs a game over: without one the harness issues no
reset, and there is no exposure. So the first question about any real level is
whether a losing line fits inside the budget its published human baseline
implies, `ceil(5 x baseline)`.

This measures an UPPER BOUND on the shortest losing line, by playing the shipped
environment from the level's start state and recording the action sequence at
the first GAME_OVER. Random play cannot beat the true shortest line, so a bound
below the budget PROVES the level can be lost inside its budget, and the
recorded line is a witness that is replayed to confirm it. A bound above the
budget proves nothing either way and is reported as not established, never as
immunity.

Every statement is about the CLIENT and about the shipped environments. How the
server treats any of this is not observable to us and is not claimed, and
nothing here is a claim about any published result.

Scope: the 25 public environments already fetched to environment_files/, run
OFFLINE. No network, no API key, no semi-private or private environment.

Usage: death_cost.py [--rollouts 40] [--out artifacts/deathcost]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import resource
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "vendor" / "arc-agi-3-benchmarking"))

from arcengine import ActionInput, GameAction  # noqa: E402
from state_graph import make_game, status  # noqa: E402

ENVDIR = ROOT / "environment_files"
API = ROOT / "artifacts" / "api" / "games.json"
MULT = 5.0
RSS_CAP_MB = 600.0


def peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


def act(g, a: int) -> None:
    g.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)


def rollout(game: str, level: int, cap: int, rng: random.Random,
            actions=(1, 2, 3, 4)) -> list[int] | None:
    """Play at random from the level's start until GAME_OVER or the cap."""
    _, g = make_game(game, level - 1, ENVDIR)
    seq = []
    for _ in range(cap):
        a = rng.choice(actions)
        act(g, a)
        seq.append(a)
        st = status(g, level - 1)
        if st == "GAME_OVER":
            return seq
        if st != "PLAY":
            return None          # a win, or a level advance: not a losing line
    return None


def replay_is_a_loss(game: str, level: int, seq: list[int]) -> bool:
    _, g = make_game(game, level - 1, ENVDIR)
    for i, a in enumerate(seq):
        act(g, a)
        st = status(g, level - 1)
        if st == "GAME_OVER":
            return i == len(seq) - 1     # ends exactly at the game over
        if st != "PLAY":
            return False
    return False


def study(game: str, level: int, baseline: int, rollouts: int, seed: int) -> dict:
    budget = math.ceil(baseline * MULT)
    cap = max(4 * budget, 200)
    rng = random.Random(seed)
    best = None
    found = 0
    for _ in range(rollouts):
        seq = rollout(game, level, cap, rng)
        if seq is None:
            continue
        found += 1
        if best is None or len(seq) < len(best):
            best = seq
    verified = replay_is_a_loss(game, level, best) if best else None
    bound = len(best) if best else None
    return dict(game=game, level=level, baseline=baseline, budget=budget,
                rollouts=rollouts, rollouts_that_died=found,
                shortest_observed_loss=bound,
                witness_replays_to_game_over=verified,
                losing_line=best,
                death_fits_budget=(bound is not None and bound < budget),
                deaths_affordable=(budget // bound if bound else 0),
                established=(bound is not None and bound < budget))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollouts", type=int, default=40)
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "deathcost")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    games = json.loads(API.read_text())
    rows, lines = [], []
    for g in games:
        short = g["game_id"][:4]
        baseline = g["baseline_actions"][a.level - 1]
        try:
            r = study(short, a.level, baseline, a.rollouts, a.seed)
        except Exception as e:                      # noqa: BLE001
            r = dict(game=short, level=a.level, baseline=baseline,
                     error=f"{type(e).__name__}: {e}")
        r["game_id"] = g["game_id"]
        rows.append(r)
        lines.append(
            f"DEATH {short} L{a.level} baseline={baseline} budget={r.get('budget')} "
            f"shortest_observed_loss={r.get('shortest_observed_loss')} "
            f"replays={r.get('witness_replays_to_game_over')} "
            f"fits_budget={r.get('death_fits_budget')} "
            f"deaths_affordable={r.get('deaths_affordable')} "
            f"died={r.get('rollouts_that_died')}/{a.rollouts}"
            + (f" error={r['error']}" if r.get("error") else ""))
    exposed = [r for r in rows if r.get("death_fits_budget")]
    rss = peak_rss_mb()
    lines.append(
        f"SUMMARY environments={len(rows)} level={a.level} "
        f"exposed={len(exposed)} not_established={len(rows) - len(exposed)} "
        f"all_witnesses_replay={all(r.get('witness_replays_to_game_over') is not False for r in rows)} "
        f"peak_rss_mb_under_{int(RSS_CAP_MB)}={rss < RSS_CAP_MB}")
    (a.out / "deathcost.log").write_text("\n".join(lines) + "\n")
    (a.out / "deathcost.json").write_text(json.dumps(dict(levels=rows), indent=1, sort_keys=True) + "\n")
    print("\n".join(lines))
    return 0 if rss < RSS_CAP_MB else 1


if __name__ == "__main__":
    raise SystemExit(main())
