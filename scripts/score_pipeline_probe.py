"""Probe the scoring PIPELINE, not the scoring formula.

Phase 0 audited the level-score formula against its documented definition. This
probes what feeds it: the bookkeeping that turns a play into per-level action
counts, and the aggregation above it. A defect there changes a reported number
even when the formula is right.

Plays are driven through the toolkit's own path -- `Scorecard.update_scorecard`
with synthetic frames, exactly as the environment wrapper calls it -- so the
recorded action counts, reset counts and level boundaries are produced by the
shipped code and not by us.

Reject-only. Every result names the artefact it is about. The official
leaderboard is computed server-side and is NOT observable to us; nothing here is
a claim about it.

Scope: the public toolkit at the pinned commit. No environment, no network, no
API key.

Usage: score_pipeline_probe.py [--out artifacts/pipeline]
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from arc_agi.models import EnvironmentInfo  # noqa: E402
from arc_agi.scorecard import EnvironmentScorecard, Scorecard  # noqa: E402
from arcengine import ActionInput, FrameDataRaw, GameAction, GameState  # noqa: E402

RESET, MOVE = 0, 1


def frame(game_id: str, guid: str, action: int, levels: int, state: str, full_reset: bool) -> FrameDataRaw:
    f = FrameDataRaw()
    f.game_id = game_id
    f.guid = guid
    f.state = GameState[state]
    f.levels_completed = levels
    f.full_reset = full_reset
    f.action_input = ActionInput(id=GameAction.from_id(action))
    return f


def play(sc: Scorecard, game_id: str, guid: str, steps: list[dict]) -> None:
    """Drive one play through the shipped bookkeeping. Each step is one action
    and the state the environment reports afterwards."""
    for s in steps:
        sc.update_scorecard(guid, frame(game_id, guid, s["action"], s["levels"],
                                        s.get("state", "NOT_FINISHED"),
                                        s.get("full_reset", False)),
                            s.get("full_reset", False))


def start(sc: Scorecard, game_id: str, guid: str) -> None:
    """A play begins with the wrapper's own RESET, which is a full reset."""
    sc.update_scorecard(guid, frame(game_id, guid, RESET, 0, "NOT_FINISHED", True), True)


def linear_play(levels_actions: list[int], win: bool = True, resets_before_level: dict[int, int] | None = None,
                game_overs: dict[int, int] | None = None) -> list[dict]:
    """A play that completes each level in the given number of actions, with
    optional level RESETs and GAME_OVERs inserted before a level."""
    steps: list[dict] = []
    done = 0
    for i, n in enumerate(levels_actions):
        for _ in range((resets_before_level or {}).get(i, 0)):
            steps.append(dict(action=RESET, levels=done, state="NOT_FINISHED", full_reset=False))
        for _ in range((game_overs or {}).get(i, 0)):
            steps.append(dict(action=MOVE, levels=done, state="GAME_OVER"))
            steps.append(dict(action=RESET, levels=done, state="NOT_FINISHED", full_reset=False))
        for k in range(n):
            last = (k == n - 1)
            steps.append(dict(action=MOVE, levels=done + 1 if last else done,
                              state=("WIN" if (last and win and i == len(levels_actions) - 1)
                                     else "NOT_FINISHED")))
        done += 1
    return steps


def score(cards: dict[str, list[list[dict]]], baselines: dict[str, list[int]],
          all_environments: list[str] | None = None) -> dict:
    """Build a scorecard from plays and hand it to the shipped scorer."""
    sc = Scorecard(card_id="probe", api_key="")
    for game_id, plays in cards.items():
        for j, steps in enumerate(plays):
            guid = f"{game_id}-g{j}"
            start(sc, game_id, guid)
            play(sc, game_id, guid, steps)
    infos = [EnvironmentInfo(game_id=g, title=g.upper(), baseline_actions=b)
             for g, b in baselines.items()]
    out = EnvironmentScorecard.from_scorecard(sc, infos)
    d = json.loads(out.model_dump_json())
    envs = {e["id"]: e for e in d["environments"]}
    return dict(total=round(d["score"], 9), environments={k: round(v["score"], 9) for k, v in envs.items()},
                per_environment={k: dict(levels_completed=v["levels_completed"], actions=v["actions"],
                                         resets=v.get("resets"),
                                         runs=[dict(score=round(r["score"], 9),
                                                    level_actions=r.get("level_actions"),
                                                    level_scores=[round(x, 9) for x in (r.get("level_scores") or [])],
                                                    levels_completed=r["levels_completed"],
                                                    actions=r["actions"])
                                               for r in v["runs"]])
                                for k, v in envs.items()},
                cards={g: json.loads(c.model_dump_json()) for g, c in sc.cards.items()})


def probes() -> list[dict]:
    B5 = [10, 10, 10, 10, 10]
    return [
        dict(id="Q1", note="the toolkit's own test case: one environment, one play, six levels at baseline",
             cards={"aa00": [linear_play([10] * 6)]}, baselines={"aa00": [10] * 6},
             documented="100.0 for that environment"),
        dict(id="Q2", note="aggregation: 3 of 135 environments played, each perfect",
             cards={g: [linear_play([10] * 5)] for g in ("aa00", "bb00", "cc00")},
             baselines={g: B5 for g in ("aa00", "bb00", "cc00")},
             set_size=135,
             documented="sum of environment scores divided by the TOTAL number of environments (report v2 4.1)"),
        dict(id="Q3", note="aggregation: all environments in the set played",
             cards={g: [linear_play([10] * 5)] for g in ("aa00", "bb00")},
             baselines={g: B5 for g in ("aa00", "bb00")}, set_size=2,
             documented="same under both readings"),
        dict(id="Q4", note="one level RESET before each of levels 2..5",
             cards={"aa00": [linear_play([10] * 5, resets_before_level={1: 1, 2: 1, 3: 1, 4: 1})]},
             baselines={"aa00": B5},
             documented="a RESET is an action; whether it is charged to the level is unstated"),
        dict(id="Q5", note="a GAME_OVER and a RESET before level 3, then completion",
             cards={"aa00": [linear_play([10] * 5, game_overs={2: 1})]},
             baselines={"aa00": B5}, documented="unstated"),
        dict(id="Q6", note="two plays: the second completes more levels but less efficiently",
             cards={"aa00": [linear_play([10, 10], win=False), linear_play([10, 10, 40, 40, 40])]},
             baselines={"aa00": B5}, documented="average of the BEST score for the environment (docs)"),
        dict(id="Q7", note="two plays: the first is more efficient, the second reaches further",
             cards={"aa00": [linear_play([5, 5], win=False), linear_play([40] * 5)]},
             baselines={"aa00": B5}, documented="best score"),
        dict(id="Q8", note="a play that completes no level at all",
             cards={"aa00": [[dict(action=MOVE, levels=0) for _ in range(30)]]},
             baselines={"aa00": B5}, documented="0"),
        dict(id="Q9", note="an environment with a play of zero actions",
             cards={"aa00": [[]]}, baselines={"aa00": B5}, documented="0"),
        dict(id="Q10", note="more baselines than levels the play reached",
             cards={"aa00": [linear_play([10, 10], win=False)]}, baselines={"aa00": [10] * 8},
             documented="levels not reached score 0"),
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "pipeline")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    rows, lines = [], []
    for p in probes():
        r = score(p["cards"], p["baselines"])
        set_size = p.get("set_size")
        documented_total = (sum(r["environments"].values()) / set_size) if set_size else None
        row = dict(id=p["id"], note=p["note"], documented=p["documented"],
                   set_size=set_size, environments_played=len(r["environments"]),
                   toolkit_total=r["total"], documented_total=(round(documented_total, 9)
                                                               if documented_total is not None else None),
                   environment_scores=r["environments"], detail=r["per_environment"])
        rows.append(row)
        extra = ""
        if documented_total is not None:
            extra = (f" documented_total={row['documented_total']} "
                     f"ratio={round(r['total'] / documented_total, 3) if documented_total else 'n/a'}")
        lines.append(f"{p['id']:4s} played={row['environments_played']} set_size={set_size} "
                     f"toolkit_total={r['total']}{extra} env_scores={r['environments']} :: {p['note']}")
        print(lines[-1], flush=True)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1048576 if sys.platform == "darwin" else 1024)
    lines.append(f"SUMMARY probes={len(rows)} peak_rss_mb_under_500={peak < 500}")
    (a.out / "pipeline.json").write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")
    (a.out / "pipeline.log").write_text("\n".join(lines) + "\n")
    print(lines[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
