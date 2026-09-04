"""OFFLINE trace recorder: drive a local ARC-AGI-3 environment with a scripted
action list, record every frame's state, and keep an INDEPENDENT action count to
compare with the toolkit's own scorecard bookkeeping.

Reject-only: the parity block reports `counts_agree` true/false; false is a
disagreement to be read by a human, never a verdict.

Usage: record_trace.py --environments-dir DIR --game ID --actions ACTION3,RESET,... [--out FILE] [--seed 0]
Action tokens: RESET, ACTION1..ACTION7, ACTION6:x,y
Artefact: JSON without wall-clock fields (byte-identical on re-run).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from arc_agi import Arcade, OperationMode
from arcengine import GameAction

ROOT = Path(__file__).resolve().parents[1]


def parse_action(tok: str) -> tuple[GameAction, dict]:
    name, _, arg = tok.partition(":")
    act = GameAction.from_name(name.strip())
    data = {}
    if arg:
        x, y = arg.split(",")
        data = {"x": int(x), "y": int(y)}
    return act, data


def canon_guids(obj, table: dict | None = None):
    """Replace random per-wrapper guids with stable placeholders (guid-1, guid-2, ...)
    so that artefacts are byte-identical across runs."""
    table = {} if table is None else table
    if isinstance(obj, dict):
        return {k: canon_guids(v, table) for k, v in obj.items()}
    if isinstance(obj, list):
        return [canon_guids(v, table) for v in obj]
    if isinstance(obj, str) and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", obj):
        return table.setdefault(obj, f"guid-{len(table) + 1}")
    return obj


def run_script(environments_dir: Path, game: str, actions: list[str], seed: int = 0,
               recordings_dir: Path | None = None) -> dict:
    logger = logging.getLogger("arc_agi_3_audit.recorder")
    logger.setLevel(logging.ERROR)
    logging.getLogger("arc_agi.scorecard").setLevel(logging.ERROR)
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(environments_dir),
                 recordings_dir=str(recordings_dir or (ROOT / "artifacts" / "recordings")), logger=logger)
    card_id = arc.create_scorecard(tags=["audit-recorder"])
    env = arc.make(game, scorecard_id=card_id, seed=seed, save_recording=False)
    if env is None:
        raise SystemExit(f"could not make {game} from {environments_dir}")
    first = env.observation_space
    steps = [dict(i=0, action="(make: initial RESET inside the wrapper)", state=first.state.name,
                  levels_completed=first.levels_completed, full_reset=first.full_reset,
                  available_actions=list(first.available_actions))]
    ours = dict(non_reset_actions=0, resets=0, full_resets_observed=0)
    for i, tok in enumerate(actions, start=1):
        act, data = parse_action(tok)
        obs = env.step(act, data=data)
        if obs is None:
            steps.append(dict(i=i, action=tok, error="step returned None"))
            continue
        if act == GameAction.RESET:
            ours["resets"] += 1
        else:
            ours["non_reset_actions"] += 1
        if obs.full_reset:
            ours["full_resets_observed"] += 1
        steps.append(dict(i=i, action=tok, state=obs.state.name, levels_completed=obs.levels_completed,
                          full_reset=obs.full_reset, available_actions=list(obs.available_actions)))
    full_id = env.info.game_id
    raw = arc.scorecard_manager.scorecards[card_id].cards[full_id]
    card = canon_guids(json.loads(raw.model_dump_json()))
    scored = arc.get_scorecard(card_id)
    envscore = canon_guids(json.loads(scored.model_dump_json())) if scored else None
    # Parity: the Card counts non-reset actions plus LEVEL resets on the current
    # play; a FULL reset after the first action starts a new play instead of
    # counting. The initial RESET inside make() is not counted by the Card.
    ours["total_including_resets"] = ours["non_reset_actions"] + ours["resets"]
    card_total = sum(card["actions"])
    parity = dict(ours_total=ours["total_including_resets"], card_total=card_total,
                  ours_minus_new_play_resets=ours["total_including_resets"] - max(0, card["total_plays"] - 1),
                  counts_agree=(ours["total_including_resets"] - max(0, card["total_plays"] - 1)) == card_total)
    return dict(game=full_id, seed=seed, script=actions, steps=steps, ours=ours, card=card, parity=parity,
                environment_score=(envscore["environments"][0] if envscore and envscore.get("environments") else None))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--environments-dir", type=Path, required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--actions", required=True, help="comma-separated action tokens")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    res = run_script(a.environments_dir, a.game, [t for t in a.actions.split(",") if t], a.seed)
    text = json.dumps(res, indent=1, sort_keys=True) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text)
    print(json.dumps(dict(game=res["game"], ours=res["ours"], parity=res["parity"],
                          final=res["steps"][-1], score=(res["environment_score"] or {}).get("score"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
