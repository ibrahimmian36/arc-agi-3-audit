"""Scorer probes: planted Cards through the shipped scorer, compared with the
compiled Dafny oracle under four readings of the documented rule.

Reject-only. Prints one line per probe; a line containing DISAGREEMENT means the
shipped scorer and the oracle differ under the primary reading (prose, no
cutoff). Every disagreement is read by a human and classified in FINDINGS.md.

Usage: scorer_probe.py [--out artifacts/scorer] [--oracle artifacts/oracle/scoring.js]
Artefacts (deterministic, no wall-clock fields): fixtures.json, probes.json, probes.log
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from arc_agi.models import EnvironmentInfo
from arc_agi.scorecard import Card, EnvironmentScorecard, Scorecard
from arcengine import GameState

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "differential.cjs"
MARK = "__DIFF__"
TOL = 1e-6
B10 = [10, 10, 10, 10, 10]


def probes() -> list[dict]:
    """The preregistered planted traces (docs/PREREGISTRATION.md §1.2)."""
    return [
        dict(id="P1", note="exact baseline", baselines=B10, levels=[10, 10, 10, 10, 10]),
        dict(id="P2a", note="fewer than baseline on L1", baselines=B10, levels=[9, 10, 10, 10, 10]),
        dict(id="P2b", note="much fewer on L1, L5 incomplete", baselines=B10, levels=[5, 10, 10, 10], tail=20),
        dict(id="P2c", note="distinguishes prose vs equation cap", baselines=B10, levels=[5, 12, 12, 12], tail=20),
        dict(id="P3a", note="exactly at 5x cutoff on L1", baselines=B10, levels=[50, 10, 10, 10, 10]),
        dict(id="P3b", note="one action over 5x cutoff on L1", baselines=B10, levels=[51, 10, 10, 10, 10]),
        dict(id="P4", note="reset mid-level: 4 actions, RESET, 10 actions (Card counts the RESET)", baselines=B10,
             levels=[15, 10, 10, 10, 10], resets=1),
        dict(id="P5", note="level-weight edge: only L1 completed", baselines=B10, levels=[10], tail=0),
        dict(id="P6", note="unsolved final level", baselines=B10, levels=[10, 10, 10, 10], tail=20),
        dict(id="P7", note="never solves", baselines=B10, levels=[], tail=30),
        dict(id="P8", note="double advance: one action completes L1 and L2", baselines=B10,
             card=dict(levels_completed=5, actions=40, resets=0, state="WIN",
                       actions_by_level=[(2, 10), (3, 20), (4, 30), (5, 40)]),
             oracle=dict(actions=[10, 1, 10, 10, 10], completed=[True] * 5,
                         why="documented value under the charitable reading: L1 and L2 share 10 actions; any positive L2 count <= h gives E = 100")),
        dict(id="P9", note="GAME_OVER after 3 actions, RESET, 10 actions (Card L1 = 14)", baselines=B10,
             levels=[14, 10, 10, 10, 10], resets=1),
        dict(id="P10", note="two plays: best play counts", baselines=B10, levels=[10, 10, 10, 10, 10],
             extra_plays=[dict(levels=[10], tail=0)]),
        dict(id="P11", note="baseline length mismatch (5 baselines, 6 level entries)", baselines=B10,
             levels=[10, 10, 10, 10, 10, 10], no_oracle=True),
    ]


def play_from_levels(levels: list[int], tail: int | None, resets: int = 0) -> dict:
    cum, abl = 0, []
    for i, a in enumerate(levels):
        cum += a
        abl.append((i + 1, cum))
    total = cum + (tail or 0)
    completed_all = tail is None
    return dict(levels_completed=len(levels), actions=total, resets=resets,
                state="WIN" if completed_all else "NOT_FINISHED", actions_by_level=abl)


def build_card(p: dict, game_id: str) -> tuple[Card, dict]:
    plays = []
    if "card" in p:
        plays.append(p["card"])
    else:
        plays.append(play_from_levels(p["levels"], p.get("tail"), p.get("resets", 0)))
    for e in p.get("extra_plays", []):
        plays.append(play_from_levels(e["levels"], e.get("tail"), e.get("resets", 0)))
    # The best play (most levels completed) is what the scorer reports; the
    # first play listed is the one the probe is about.
    card = Card(
        game_id=game_id,
        total_plays=len(plays),
        guids=[f"g{i + 1}" for i in range(len(plays))],
        levels_completed=[q["levels_completed"] for q in plays],
        actions=[q["actions"] for q in plays],
        resets=[q["resets"] for q in plays],
        states=[GameState[q["state"]] for q in plays],
        actions_by_level=[[tuple(x) for x in q["actions_by_level"]] for q in plays],
    )
    return card, plays[0]


def oracle_fixture(p: dict, play: dict) -> dict | None:
    if p.get("no_oracle"):
        return None
    n = len(p["baselines"])
    if "oracle" in p:
        return dict(id=p["id"], baselines=p["baselines"], actions=p["oracle"]["actions"], completed=p["oracle"]["completed"])
    levels = p["levels"]
    actions = list(levels) + [0] * (n - len(levels))
    completed = [True] * len(levels) + [False] * (n - len(levels))
    if len(levels) < n and p.get("tail") is not None:
        actions[len(levels)] = p["tail"]
    return dict(id=p["id"], baselines=p["baselines"], actions=actions, completed=completed)


def run_oracle(oracle: Path, fixtures: Path, timeout_s: float = 60.0) -> dict:
    node = shutil.which("node")
    if node is None:
        raise SystemExit("node not found")
    env = {k: os.environ[k] for k in ("PATH",) if k in os.environ}
    try:
        p = subprocess.run([node, str(RUNNER), str(oracle), str(fixtures)], capture_output=True, text=True,
                           timeout=timeout_s, env=env, cwd=str(ROOT / "scripts"))
    except subprocess.TimeoutExpired:
        return {"loaded": False, "error": f"timed out after {timeout_s:.0f}s", "rows": []}
    lines = [l for l in p.stdout.splitlines() if l.startswith(MARK)]
    if not lines:
        return {"loaded": False, "error": (p.stderr or "no runner output")[-300:], "rows": []}
    return json.loads(lines[-1][len(MARK):])


def shipped_score(card: Card, baselines: list[int], game_id: str) -> dict:
    sc = Scorecard(card_id="probe", api_key="", cards={game_id: card})
    info = EnvironmentInfo(game_id=game_id, title=game_id.upper(), baseline_actions=baselines, tags=["probe"])
    out = EnvironmentScorecard.from_scorecard(sc, [info])
    env = out.environments[0]
    best = max(env.runs, key=lambda r: r.score)
    return dict(score=round(env.score, 9), levels_completed=env.levels_completed, completed=env.completed,
                runs=len(env.runs), best_run=dict(score=round(best.score, 9), level_scores=[round(x, 9) for x in (best.level_scores or [])],
                level_actions=best.level_actions, level_baseline_actions=best.level_baseline_actions,
                levels_completed=best.levels_completed, actions=best.actions, resets=best.resets,
                message=best.message))


def close(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(a - b) <= TOL


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "scorer")
    ap.add_argument("--oracle", type=Path, default=ROOT / "artifacts" / "oracle" / "scoring.js")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    game_id = "probe-0000"
    rows, fixtures = [], []
    for p in probes():
        card, play = build_card(p, game_id)
        fx = oracle_fixture(p, play)
        if fx:
            fixtures.append(fx)
        rows.append(dict(id=p["id"], note=p["note"], baselines=p["baselines"], planted=play,
                         card=json.loads(card.model_dump_json()), fixture=fx,
                         shipped=shipped_score(card, p["baselines"], game_id)))
    fixtures_path = a.out / "fixtures.json"
    fixtures_path.write_text(json.dumps(fixtures, indent=1, sort_keys=True) + "\n")
    orc = run_oracle(a.oracle, fixtures_path)
    by_id = {r["id"]: r for r in orc.get("rows", [])}
    log = []
    n_disagree = 0
    for r in rows:
        o = by_id.get(r["id"])
        r["oracle"] = o["readings"] if o else None
        r["oracle_loaded"] = bool(orc.get("loaded"))
        s = r["shipped"]["score"]
        readings = {}
        if o:
            for name, val in o["readings"].items():
                if "error" in val:
                    readings[name] = dict(env=None, agree=None, error=val["error"])
                    continue
                env_pct = float(val["env"]["pct"])
                lv = [float(x["pct"]) for x in val["levels"]]
                sl = r["shipped"]["best_run"]["level_scores"]
                lv_agree = len(sl) == len(lv) and all(close(x, y) for x, y in zip(sl, lv))
                readings[name] = dict(env=round(env_pct, 9), levels=[round(x, 9) for x in lv],
                                      agree=close(s, env_pct), levels_agree=lv_agree)
        r["readings"] = readings
        primary = readings.get("prose_nocut", {}).get("agree")
        r["disagreement_primary"] = (primary is False)
        if primary is False:
            n_disagree += 1
        def fmt(name):
            v = readings.get(name)
            if not v or v.get("env") is None:
                return f"{name}=n/a"
            return f"{name}={v['env']:.6f}({'agree' if v['agree'] else 'DIFF'})"
        tag = "DISAGREEMENT" if primary is False else ("no disagreement" if primary else "no oracle")
        log.append(f"{r['id']:4s} shipped={s:.6f} levels={r['shipped']['best_run']['level_scores']} "
                   f"{fmt('prose_nocut')} {fmt('eq_nocut')} {fmt('prose_cut')} {fmt('eq_cut')} :: {tag} :: {r['note']}")
    n_agree = sum(1 for r in rows if r["readings"].get("prose_nocut", {}).get("agree") is True)
    n_levels_agree = sum(1 for r in rows if r["readings"].get("prose_nocut", {}).get("levels_agree") is True)
    summary = dict(probes=len(rows), oracle_loaded=bool(orc.get("loaded")), oracle_error=orc.get("error"),
                   agree_primary=n_agree, levels_agree_primary=n_levels_agree,
                   disagreements_primary=n_disagree,
                   disagreement_ids=[r["id"] for r in rows if r["disagreement_primary"]],
                   oracle_sha256=sha256(a.oracle))
    (a.out / "probes.json").write_text(json.dumps(dict(summary=summary, rows=rows), indent=1, sort_keys=True) + "\n")
    log.append(f"SUMMARY probes={summary['probes']} oracle_loaded={summary['oracle_loaded']} agree_primary={n_agree} "
               f"levels_agree_primary={n_levels_agree} disagreements_primary={n_disagree} ids={summary['disagreement_ids']} "
               f"oracle_sha256={summary['oracle_sha256']}")
    (a.out / "probes.log").write_text("\n".join(log) + "\n")
    print("\n".join(log))
    return 0


def sha256(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"


if __name__ == "__main__":
    raise SystemExit(main())
