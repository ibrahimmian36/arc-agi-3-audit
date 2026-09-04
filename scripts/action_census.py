"""Action-space census of the 25 PUBLIC ARC-AGI-3 environments, read from the
shipped games in OFFLINE mode. Generated; never hand-written.

Why it gates everything else: a game that advertises the click action (ACTION6,
x and y each 0-63) has 4096 successors per state before the other actions are
counted, so an exhaustive reachable-state enumeration is out of reach for it
within any sane budget. Establishing that up front turns "we did not enumerate
these" from a gap into a stated, measured fact.

Scope: the public set only. The semi-private and private sets are out of scope
and are never fetched, probed or inferred.

Usage: action_census.py [--out artifacts/sweep/action_census.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
from pathlib import Path

from arc_agi import Arcade, OperationMode

ROOT = Path(__file__).resolve().parents[1]
COMPLEX_ACTIONS = {6}          # ACTION6 carries x, y in 0..63
GRID = 64 * 64


def census(environments_dir: Path) -> list[dict]:
    lg = logging.getLogger("census"); lg.setLevel(logging.ERROR)
    logging.getLogger("arc_agi.scorecard").setLevel(logging.ERROR)
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(environments_dir), logger=lg)
    rows = []
    for meta in sorted(glob.glob(str(environments_dir / "*" / "*" / "metadata.json"))):
        d = json.loads(Path(meta).read_text())
        gid = d["game_id"]
        env = arc.make(gid, save_recording=False)
        if env is None:
            rows.append(dict(game=gid.split("-")[0], game_id=gid, error="could not instantiate"))
            continue
        g = env._game
        acts = sorted(g._available_actions or [])
        cplx = sorted(set(acts) & COMPLEX_ACTIONS)
        simple = [a for a in acts if a not in COMPLEX_ACTIONS]
        branching = len(simple) + len(cplx) * GRID
        rows.append(dict(
            game=gid.split("-")[0], game_id=gid, title=d.get("title"), tags=d.get("tags"),
            actions=acts, complex_actions=cplx, simple_actions=simple, branching_factor=branching,
            levels=len(g._levels), baseline_actions=d.get("baseline_actions"),
            enumerable=not cplx,
            reason=None if not cplx else f"advertises the click action, {branching} successors per state",
        ))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--environments-dir", type=Path, default=ROOT / "environment_files")
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "sweep" / "action_census.json")
    a = ap.parse_args(argv)
    rows = census(a.environments_dir)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")
    enum = [r for r in rows if r.get("enumerable")]
    lines = [f"{r['game']:6s} actions={str(r['actions']):22s} branching={r['branching_factor']:5d} "
             f"levels={r['levels']:2d} enumerable={r.get('enumerable')}" for r in rows]
    lines.append(f"SUMMARY environments={len(rows)} enumerable={len(enum)} "
                 f"click_based={len(rows) - len(enum)} enumerable_games={sorted(r['game'] for r in enum)}")
    (a.out.parent / "action_census.log").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-3:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
