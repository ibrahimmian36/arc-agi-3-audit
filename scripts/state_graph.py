"""E5 / E1: enumerate the reachable state graph of one level of a local
ARC-AGI-3 environment by breadth-first search over ACTION1..ACTION4, using deep
copies of the shipped game object (the shipped implementation IS the transition
function here; nothing is modelled). WIN (level completed) and GAME_OVER are
absorbing. Reject-only: reports numbers to be read against the documented claim.

Usage: state_graph.py --game ls20 --level 1 [--max-states 200000] [--out artifacts/env/ls20]
Artefact: graph_L<k>.json (deterministic: no wall-clock, no ids).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import pickle
import time
from collections import deque
from pathlib import Path

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import ActionInput, GameAction, GameState

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = [1, 2, 3, 4]


# Engine bookkeeping that differs between two otherwise identical states and
# has no effect on future behaviour: the last action taken, its completion
# flag, the running action count, the full-reset flag, the pending-level flag.
TRANSIENT = ("_action", "_action_complete", "_action_count", "_full_reset", "_next_level")


def register_module(g) -> None:
    """The toolkit exec()s the game source into a module it never inserts into
    sys.modules, so instances cannot be pickled. Insert a module with the same
    globals under the class's module name (read-only use)."""
    import sys, types
    name = type(g).__module__
    pkg = name.split(".")[0]
    if pkg not in sys.modules:
        sys.modules[pkg] = types.ModuleType(pkg)
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__dict__.update(type(g).__init__.__globals__)
        sys.modules[name] = mod
        setattr(sys.modules[pkg], name.split(".", 1)[1], mod)


def level_signature(g) -> bytes:
    """Everything the game reads from the current level: every sprite's name,
    tags, position, visibility, rotation and pixel content, in list order
    (order matters: txnfzvzetn scans in order and breaks)."""
    h = hashlib.sha1()
    for sp in g.current_level.get_sprites():
        h.update(f"{sp.name}|{sp.tags}|{sp.x}|{sp.y}|{sp.is_visible}|{getattr(sp, 'rotation', None)}|".encode())
        px = getattr(sp, "pixels", None)
        if px is not None:
            h.update(np.asarray(px).tobytes())
    return h.digest()


def state_key(g) -> str:
    """Rule-level state: the level signature plus every game attribute that the
    step function reads, excluding transient engine bookkeeping (TRANSIENT).
    Under-fine only if a read attribute is missing here; the differential's
    abstract-state comparison is independent of this key."""
    h = hashlib.sha1(level_signature(g))
    ui = getattr(g, "_step_counter_ui", None)
    fields = [g._state.name, g._score, g._current_level_index,
              None if ui is None else (ui.current_steps, ui.osgviligwp, ui.efipnixsvl)]
    for k in ("aqygnziho", "cklxociuu", "hiaauhahz", "fwckfzsyc", "lvrnuajbl", "akoadfsur", "ebfuxzbvn",
              "ltwrkifkx", "zyoimjaei", "ehwheiwsk", "yjdexjsoa", "ldxlnycps"):
        fields.append(repr(getattr(g, k, None)))
    for k in ("ofoahudlo", "byotxmvkt", "alsxlhizr", "euemavvxz"):
        fields.append(len(getattr(g, k, []) or []))
    for pu in getattr(g, "hasivfwip", []) or []:
        fields.append((pu.sprite.x, pu.sprite.y, pu.is_pushing, pu.target_x, pu.target_y))
    for mv in getattr(g, "wsoslqeku", []) or []:
        fields.append((mv._sprite.x, mv._sprite.y, mv._dir, mv._undo_x, mv._undo_y, mv._undo_dir))
    h.update(repr(fields).encode())
    return h.hexdigest()


def fast_copy(g):
    """deepcopy sharing the immutable level templates and the untouched other
    levels (level_reset re-clones from _clean_levels; nothing mutates them)."""
    memo = {id(g._clean_levels): g._clean_levels}
    for i, lv in enumerate(g._levels):
        if i != g._current_level_index:
            memo[id(lv)] = lv
    return copy.deepcopy(g, memo)


def status(g, level_index: int) -> str:
    if g._state == GameState.GAME_OVER:
        return "GAME_OVER"
    if g._state == GameState.WIN or g._score > level_index:
        return "WIN"
    return "PLAY"


def lives_of(g):
    return getattr(g, "aqygnziho", None)


def abstract(g, level_index: int, cell: int = 5, ox: int = 4, oy: int = 0) -> dict:
    """Rule-level view of an ls20 state (fields named by ROLE, read from the
    obfuscated attributes identified in extract_level.py / the model)."""
    p = getattr(g, "gudziatsk", None)
    ui = getattr(g, "_step_counter_ui", None)
    return dict(cx=None if p is None else (p.x - ox) // cell, cy=None if p is None else (p.y - oy) // cell,
                px=None if p is None else p.x, py=None if p is None else p.y,
                rot=getattr(g, "cklxociuu", None), color=getattr(g, "hiaauhahz", None), shape=getattr(g, "fwckfzsyc", None),
                lives=lives_of(g), steps=None if ui is None else ui.current_steps,
                goals_done=list(getattr(g, "lvrnuajbl", []) or []), status=status(g, level_index))


def make_game(game: str, level_index: int):
    lg = logging.getLogger("sg"); lg.setLevel(logging.ERROR); logging.getLogger("arc_agi.scorecard").setLevel(logging.ERROR)
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(ROOT / "environment_files"), logger=lg)
    env = arc.make(game, save_recording=False)
    g = env._game
    if level_index > 0:
        g._score = level_index
        g.set_level(level_index)
        g._state = GameState.NOT_FINISHED
    return env.info.game_id, g


def enumerate_level(game: str, level_index: int, max_states: int, max_seconds: float,
                    check_reset: bool = True, max_reset_checks: int = 500) -> dict:
    full_id, g0 = make_game(game, level_index)
    register_module(g0)
    t0 = time.time()
    root = state_key(g0)
    nodes = {root: dict(i=0, status=status(g0, level_index), lives=lives_of(g0), depth=0, parent=None, via=None, abs=abstract(g0, level_index))}
    objs = {root: g0}
    edges: list[tuple[int, int, int]] = []
    q = deque([root])
    truncated = False
    while q:
        k = q.popleft()
        n = nodes[k]
        if n["status"] != "PLAY":
            continue
        for a in ACTIONS:
            c = fast_copy(objs[k])
            c.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)
            ck = state_key(c)
            if ck not in nodes:
                nodes[ck] = dict(i=len(nodes), status=status(c, level_index), lives=lives_of(c), depth=n["depth"] + 1,
                                 parent=n["i"], via=a, abs=abstract(c, level_index))
                objs[ck] = c
                q.append(ck)
            edges.append((n["i"], a, nodes[ck]["i"]))
        if len(nodes) % 5000 == 0 and len(nodes) > 0:
            print(f"progress states={len(nodes)} queue={len(q)} t={int(time.time() - t0)}s", flush=True)
        if len(nodes) >= max_states or time.time() - t0 > max_seconds:
            truncated = True
            break
    N = len(nodes)
    idx = {v["i"]: v for v in nodes.values()}
    wins = [v["i"] for v in nodes.values() if v["status"] == "WIN"]
    overs = [v["i"] for v in nodes.values() if v["status"] == "GAME_OVER"]
    shortest_win = min((idx[i]["depth"] for i in wins), default=None)
    # (a) random-policy win probability: p = A p + b on PLAY nodes (only exact when not truncated).
    p_random = None
    if wins and not truncated:
        # p(s) = mean over actions of p(next); WIN = 1, GAME_OVER = 0. Sparse
        # value iteration to 1e-12 (the chain is absorbing: every PLAY state
        # can run out of steps, so iteration converges).
        p = np.zeros(N); p[wins] = 1.0
        src = np.array([e[0] for e in edges]); dst = np.array([e[2] for e in edges])
        play_mask = np.array([idx[i]["status"] == "PLAY" for i in range(N)])
        for _ in range(100000):
            nxt = np.zeros(N); np.add.at(nxt, src, p[dst]); nxt /= 4.0
            nxt[~play_mask] = p[~play_mask]
            if np.max(np.abs(nxt - p)) < 1e-12:
                p = nxt; break
            p = nxt
        p_random = float(p[0])
    # Shortest win path (parent pointers), for the model's E1 witness.
    path = None
    if wins:
        best = min(wins, key=lambda i: idx[i]["depth"])
        path = []
        cur = idx[best]
        while cur["parent"] is not None:
            path.append(cur["via"]); cur = idx[cur["parent"]]
        path.reverse()
    # E3 on the shipped game: RESET from every PLAY node must return to the root key.
    reset_checked = reset_ok = 0
    reset_bad = []
    if check_reset:
        for k, n in nodes.items():
            if n["status"] != "PLAY" or reset_checked >= max_reset_checks:
                continue
            c = fast_copy(objs[k])
            c.perform_action(ActionInput(id=GameAction.RESET), raw=True)
            reset_checked += 1
            if state_key(c) == root:
                reset_ok += 1
            elif len(reset_bad) < 20:
                reset_bad.append(dict(node=n["i"], after_reset=abstract(c, level_index)))
    by_lives: dict[str, int] = {}
    for v in nodes.values():
        by_lives[str(v["lives"])] = by_lives.get(str(v["lives"]), 0) + 1
    return dict(game=full_id, level=level_index + 1, actions=ACTIONS, states=N, edges=len(edges), truncated=truncated,
                max_states=max_states, win_states=len(wins), game_over_states=len(overs), win_reachable=bool(wins),
                shortest_win_depth=shortest_win, states_by_lives=dict(sorted(by_lives.items(), reverse=True)),
                p_win_random_policy=p_random, one_over_states=(1.0 / N), win_over_states=(len(wins) / N),
                inverse_p_win_random=(None if not p_random else 1.0 / p_random),
                shortest_win_path=path, reset_checked=reset_checked, reset_returns_to_start=reset_ok, reset_mismatches=reset_bad,
                root_abstract=idx[0]["abs"],
                graph=dict(nodes=[dict(i=v["i"], status=v["status"], depth=v["depth"], abs=v["abs"]) for v in sorted(nodes.values(), key=lambda v: v["i"])],
                           edges=edges),
                elapsed_s_bucket=int(time.time() - t0) // 10 * 10)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="ls20")
    ap.add_argument("--level", type=int, default=1, help="1-based")
    ap.add_argument("--max-states", type=int, default=200_000)
    ap.add_argument("--max-seconds", type=float, default=900)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    out = a.out or (ROOT / "artifacts" / "env" / a.game)
    out.mkdir(parents=True, exist_ok=True)
    r = enumerate_level(a.game, a.level - 1, a.max_states, a.max_seconds)
    r.pop("elapsed_s_bucket", None)
    graph = r.pop("graph")
    (out / f"graph_L{a.level}.json").write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
    (out / f"graph_L{a.level}_edges.json").write_text(json.dumps(graph, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in r.items() if k != "reset_mismatches"}))
    print("reset_mismatches (first):", json.dumps(r["reset_mismatches"][:3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
