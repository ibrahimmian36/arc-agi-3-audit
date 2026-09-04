"""Extract one ls20 level's rule data from the SHIPPED game object into a JSON
artefact (cell lattice, walls, start, goal, modifier tiles, pickups, counters),
the source of the Dafny model's constants. Nothing is inferred from names: the
tag strings are copied as they appear in the source and mapped once, here, to
the roles observed in `step()`/`txnfzvzetn()`/`on_set_level()`.

Usage: extract_level.py --game ls20 --level 1 [--out artifacts/env/ls20/level1.json]
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from arc_agi import Arcade, OperationMode

ROOT = Path(__file__).resolve().parents[1]
# tag -> role, from reading environment_files/ls20/9607627b/ls20.py (txnfzvzetn, step, on_set_level)
ROLES = {
    "ihdgageizm": "wall",          # blocks movement
    "rjlbuycveu": "goal",          # must match shape/color/rotation; blocks + flash otherwise
    "npxgalaybz": "energy",        # refills the step counter, removed on pickup
    "ttfwljgohq": "shape_tile",    # cycles shape index
    "soyhouuebz": "color_tile",    # cycles color index
    "rhsxkxzdjz": "rotation_tile", # cycles rotation index
    "sfqyzhzkij": "player",
    "gbvqrjtaqo": "pusher",        # moving wall that pushes the player (levels 3+)
    "xfmluydglp": "patrol_path",   # path for moving objects (levels 5+)
    "kvynsvxbpi": "goal_marker",   # visual copy of the goal's required shape
}
ROTATIONS = [0, 90, 180, 270]
COLORS_LEN = 4
SHAPES_LEN = 6


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="ls20")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    lg = logging.getLogger("ex"); lg.setLevel(logging.ERROR); logging.getLogger("arc_agi.scorecard").setLevel(logging.ERROR)
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(ROOT / "environment_files"), logger=lg)
    env = arc.make(a.game, save_recording=False)
    g = env._game
    lv = g._clean_levels[a.level - 1]
    data = dict(lv._data) if hasattr(lv, "_data") else {}
    player = [s for s in lv.get_sprites() if s.tags and "sfqyzhzkij" in s.tags][0]
    cell = player.width
    ox, oy = player.x % cell, player.y % cell  # lattice offset
    def to_cell(x, y):
        assert (x - ox) % cell == 0 and (y - oy) % cell == 0, (x, y)
        return [(x - ox) // cell, (y - oy) // cell]
    items = {}
    for s in lv.get_sprites():
        for t in (s.tags or []):
            if t in ROLES and ROLES[t] not in ("player", "goal_marker"):
                if s.width == cell and s.height == cell and (s.x - ox) % cell == 0 and (s.y - oy) % cell == 0:
                    items.setdefault(ROLES[t], []).append(to_cell(s.x, s.y))
                else:
                    items.setdefault(ROLES[t] + "_offlattice", []).append([s.x, s.y, s.width, s.height])
    walls = sorted({tuple(c) for c in items.get("wall", [])})
    untagged = [[s.name, s.x, s.y, s.width, s.height] for s in lv.get_sprites() if not s.tags]
    goal_rot = data.get("GoalRotation"); goal_rot = goal_rot if isinstance(goal_rot, list) else [goal_rot]
    goal_col = data.get("GoalColor"); goal_col = goal_col if isinstance(goal_col, list) else [goal_col]
    goal_shape = data.get("kvynsvxbpi"); goal_shape = goal_shape if isinstance(goal_shape, list) else [goal_shape]
    out = dict(
        game=env.info.game_id, level=a.level, grid=list(lv.grid_size), cell=cell, lattice_offset=[ox, oy],
        start=to_cell(player.x, player.y), start_rotation_index=ROTATIONS.index(data["StartRotation"]),
        start_color_index=None, start_shape_index=data["StartShape"], start_color_value=data["StartColor"],
        goals=[dict(cell=c, rotation_index=ROTATIONS.index(goal_rot[i]), color_value=goal_col[i], shape_index=goal_shape[i])
               for i, c in enumerate(items.get("goal", []))],
        walls=[list(w) for w in walls], wall_sprites_total=len(items.get("wall", [])), walls_distinct=len(walls),
        rotation_tiles=items.get("rotation_tile", []), color_tiles=items.get("color_tile", []), shape_tiles=items.get("shape_tile", []),
        energy=items.get("energy", []), pushers=items.get("pusher", []) + items.get("pusher_offlattice", []),
        patrol=items.get("patrol_path", []) + items.get("patrol_path_offlattice", []),
        step_counter=data.get("StepCounter", 0), steps_decrement=data.get("StepsDecrement", 2), lives=3, fog=bool(data.get("Fog")),
        untagged_sprites=untagged, level_data=data, rotations=ROTATIONS, colors_len=COLORS_LEN, shapes_len=SHAPES_LEN,
        cells_x=sorted({w[0] for w in walls}), cells_y=sorted({w[1] for w in walls}),
    )
    out_path = a.out or (ROOT / "artifacts" / "env" / a.game / f"level{a.level}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: out[k] for k in ("game", "level", "cell", "lattice_offset", "start", "start_rotation_index", "goals", "rotation_tiles", "walls_distinct", "wall_sprites_total", "step_counter", "steps_decrement", "energy", "pushers", "untagged_sprites", "cells_x", "cells_y")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
