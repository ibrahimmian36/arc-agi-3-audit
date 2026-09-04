"""Enumerate the reachable state graph of ONE level of a local ARC-AGI-3
environment by breadth-first search over the movement actions, using deep
copies of the SHIPPED game object. The shipped implementation is the
transition function; nothing here models it.

Memory design (the machine has 16 GB and this must never approach it):
  * game objects are held ONLY for the BFS layer being expanded, never for the
    whole graph (one ls20 game object is ~234 KB, so one-per-state is GBs);
  * per node we keep a 16-byte digest, a small tuple of the abstract state and
    the depth, nothing else;
  * edges are streamed to a gzipped JSONL file with both endpoints inline, so
    neither this process nor the differential ever holds the edge list;
  * an RSS guard and a states cap both stop cleanly and set `truncated`.

Also records, free of charge: whether any single action advances
`levels_completed` by two (the double-advance edge behind finding F3), and the
reset probe (RESET from a PLAY state must return to the level's start).

Usage:
  state_graph.py --game ls20 --level 1 [--max-states N] [--max-seconds S]
                 [--max-rss-mb M] [--out DIR] [--environments-dir DIR]
Artefacts: <out>/graph_L<k>.json (summary), <out>/graph_L<k>_edges.jsonl.gz
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import logging
import resource
import sys
import time
from pathlib import Path

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import ActionInput, GameAction, GameState

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = [1, 2, 3, 4]
# Engine bookkeeping that differs between two otherwise identical states and
# has no effect on future behaviour.
TRANSIENT = ("_action", "_action_complete", "_action_count", "_full_reset", "_next_level")


def open_gz(path, mode: str = "wt"):
    """gzip writer with a deterministic header: the default embeds the source
    filename and the current time, so two identical runs would differ on disk
    and byte-identity could never be checked."""
    import io
    if "w" in mode:
        raw = gzip.GzipFile(filename="", mode="wb", compresslevel=6, fileobj=open(path, "wb"), mtime=0)
        return io.TextIOWrapper(raw, encoding="utf-8")
    return gzip.open(path, mode, encoding="utf-8")

def rss_mb() -> float:
    """PEAK resident set size in MB (ru_maxrss is bytes on macOS, KB on Linux).
    Peak, not current: as a guard this is deliberately conservative, since a
    process that has once touched N MB may touch it again."""
    v = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return v / 1048576.0 if sys.platform == "darwin" else v / 1024.0


def register_module(g) -> None:
    """The toolkit exec()s the game source into a module it never inserts into
    sys.modules, so instances cannot be deep-copied by name. Insert a module
    with the same globals under the class's module name (read-only use)."""
    import types
    name = type(g).__module__
    pkg = name.split(".")[0]
    if pkg not in sys.modules:
        sys.modules[pkg] = types.ModuleType(pkg)
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__dict__.update(type(g).__init__.__globals__)
        sys.modules[name] = mod
        setattr(sys.modules[pkg], name.split(".", 1)[1], mod)


def level_signature(g, h) -> None:
    """Everything the game reads from the current level: each sprite's name,
    tags, position, visibility, rotation and pixels, in list order (order
    matters: the collision scan iterates in order and breaks)."""
    for sp in g.current_level.get_sprites():
        h.update(f"{sp.name}|{sp.tags}|{sp.x}|{sp.y}|{sp.is_visible}|{getattr(sp, 'rotation', None)}|".encode())
        px = getattr(sp, "pixels", None)
        if px is not None:
            h.update(np.asarray(px).tobytes())


def state_key(g) -> bytes:
    """Rule-level state digest: the level signature plus every game attribute
    the step function reads, excluding TRANSIENT bookkeeping. Truncated to 16
    bytes (collision probability below 1e-9 at 10^6 states). Over-fine rather
    than under-fine: an extra attribute splits states, it never merges them."""
    h = hashlib.blake2b(digest_size=16)
    level_signature(g, h)
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
    return h.digest()


def status(g, level_index: int) -> str:
    if g._state == GameState.GAME_OVER:
        return "GAME_OVER"
    if g._state == GameState.WIN or g._score > level_index:
        return "WIN"
    return "PLAY"


def lives_of(g):
    return getattr(g, "aqygnziho", None)


def abstract(g, level_index: int, cell: int = 5, ox: int = 4, oy: int = 0) -> dict:
    """Rule-level view of an ls20 state, named by ROLE (the attributes are the
    obfuscated ones identified in scripts/extract_level.py)."""
    p = getattr(g, "gudziatsk", None)
    ui = getattr(g, "_step_counter_ui", None)
    return dict(cx=None if p is None else (p.x - ox) // cell, cy=None if p is None else (p.y - oy) // cell,
                px=None if p is None else p.x, py=None if p is None else p.y,
                rot=getattr(g, "cklxociuu", None), color=getattr(g, "hiaauhahz", None), shape=getattr(g, "fwckfzsyc", None),
                lives=lives_of(g), steps=None if ui is None else ui.current_steps,
                eaten=eaten_mask(g),
                goals_done=list(getattr(g, "lvrnuajbl", []) or []), status=status(g, level_index))


STATUS_CODE = {"PLAY": 0, "WIN": 1, "GAME_OVER": 2}

# Energy-pickup cells of the level under enumeration, in the order the model
# numbers them (set once from the extracted level spec). Empty for a level with
# no pickups, which keeps the recorded `eaten` bitmask constant at 0 there.
ENERGY_CELLS: list[tuple[int, int]] = []


def set_energy_cells(cells) -> None:
    global ENERGY_CELLS
    ENERGY_CELLS = [tuple(c) for c in (cells or [])]


def eaten_mask(g, cell: int = 5, ox: int = 4, oy: int = 0) -> int:
    """Which energy pickups have been consumed, as a bitmask over ENERGY_CELLS.
    The shipped game removes a consumed pickup from the level and parks it in
    `ofoahudlo` so it can be restored when a life is lost."""
    if not ENERGY_CELLS:
        return 0
    taken = {((sp.x - ox) // cell, (sp.y - oy) // cell) for sp in (getattr(g, "ofoahudlo", []) or [])}
    return sum(1 << i for i, c in enumerate(ENERGY_CELLS) if c in taken)


def vec(a: dict) -> list:
    """The comparable part of an abstract state, as a compact array."""
    return [a["cx"], a["cy"], a["rot"], a["color"], a["shape"], a["lives"], a["steps"],
            STATUS_CODE[a["status"]], [1 if x else 0 for x in a["goals_done"]], a["eaten"]]


def make_game(game: str, level_index: int, environments_dir: Path | None = None):
    lg = logging.getLogger("sg"); lg.setLevel(logging.ERROR)
    logging.getLogger("arc_agi.scorecard").setLevel(logging.ERROR)
    arc = Arcade(operation_mode=OperationMode.OFFLINE,
                 environments_dir=str(environments_dir or (ROOT / "environment_files")), logger=lg)
    env = arc.make(game, save_recording=False)
    if env is None:
        raise SystemExit(f"could not make {game}")
    g = env._game
    if level_index > 0:
        # Start at the level's own beginning: advance the engine's level index
        # and its score so that completing this level reads as a WIN here.
        g._score = level_index
        g.set_level(level_index)
        g._state = GameState.NOT_FINISHED
    return env.info.game_id, g


def fast_copy(g):
    """deepcopy sharing the immutable level templates and the untouched other
    levels (level_reset re-clones from _clean_levels; nothing mutates them)."""
    memo = {id(g._clean_levels): g._clean_levels}
    for i, lv in enumerate(g._levels):
        if i != g._current_level_index:
            memo[id(lv)] = lv
    return copy.deepcopy(g, memo)


def enumerate_level(game: str, level_index: int, max_states: int, max_seconds: float,
                    max_rss_mb: float = 4096.0, check_reset: bool = True, max_reset_checks: int = 500,
                    edges_path: Path | None = None, environments_dir: Path | None = None,
                    progress_every: int = 5000) -> dict:
    full_id, g0 = make_game(game, level_index, environments_dir)
    register_module(g0)
    t0 = time.time()
    rss0 = rss_mb()

    root = state_key(g0)
    a0 = abstract(g0, level_index)
    index: dict[bytes, int] = {root: 0}
    # Per node: (status_code, depth). The abstract vector is written with each
    # edge instead of being retained, so the node table stays tiny.
    meta: list[tuple[int, int]] = [(STATUS_CODE[a0["status"]], 0)]
    lives_hist: dict[str, int] = {str(a0["lives"]): 1}

    out = open_gz(edges_path, "wt") if edges_path else None
    n_edges = 0
    truncated = None
    frontier: list[tuple[int, object, list]] = [(0, g0, vec(a0))]
    depth = 0
    reset_checked = reset_ok = checked = 0
    reset_bad: list[dict] = []
    double_advance: list[dict] = []
    win_nodes: list[int] = []
    over_nodes = 0
    shortest_win_depth = None
    # Parent pointers only along the search tree, for the win witness.
    parent: dict[int, tuple[int, int]] = {}

    try:
        while frontier and truncated is None:
            nxt: list[tuple[int, object, list]] = []
            for nid, g, av in frontier:
                if check_reset and reset_checked < max_reset_checks and depth > 0:
                    c = fast_copy(g)
                    c.perform_action(ActionInput(id=GameAction.RESET), raw=True)
                    reset_checked += 1
                    if state_key(c) == root:
                        reset_ok += 1
                    elif len(reset_bad) < 20:
                        reset_bad.append(dict(node=nid, after_reset=abstract(c, level_index)))
                    del c
                for a in ACTIONS:
                    c = fast_copy(g)
                    before_levels = c._score
                    c.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)
                    if c._score - before_levels >= 2 and len(double_advance) < 20:
                        double_advance.append(dict(node=nid, action=a, from_levels=before_levels, to_levels=c._score))
                    ck = state_key(c)
                    ab = abstract(c, level_index)
                    cv = vec(ab)
                    known = index.get(ck)
                    if known is None:
                        known = len(index)
                        index[ck] = known
                        meta.append((STATUS_CODE[ab["status"]], depth + 1))
                        parent[known] = (nid, a)
                        lives_hist[str(ab["lives"])] = lives_hist.get(str(ab["lives"]), 0) + 1
                        if ab["status"] == "PLAY":
                            nxt.append((known, c, cv))
                        elif ab["status"] == "WIN":
                            win_nodes.append(known)
                            if shortest_win_depth is None:
                                shortest_win_depth = depth + 1
                        else:
                            over_nodes += 1
                            del c
                    else:
                        del c
                    if out is not None:
                        # Both the true node ids (for exact graph arithmetic) and
                        # the abstract vectors (for the model differential): the
                        # vectors are coarser than the state key and must never
                        # be used as node identity.
                        out.write(json.dumps({"i": nid, "j": known, "a": a, "s": av, "t": cv},
                                             separators=(",", ":")) + "\n")
                    n_edges += 1
                if len(index) >= max_states:
                    truncated = "max_states"
                    break
                checked += 1
                if checked % progress_every == 0:
                    if time.time() - t0 > max_seconds:
                        truncated = "max_seconds"; break
                    if rss_mb() > max_rss_mb:
                        truncated = "max_rss"; break
            # The expanded layer's game objects go out of scope here; only the
            # next layer's are retained.
            frontier = nxt
            depth += 1
            if truncated is None and (time.time() - t0 > max_seconds):
                truncated = "max_seconds"
            if truncated is None and rss_mb() > max_rss_mb:
                truncated = "max_rss"
    finally:
        if out is not None:
            out.close()

    N = len(index)
    # Win witness along the search tree.
    path = None
    if win_nodes:
        best = min(win_nodes, key=lambda i: meta[i][1])
        path = []
        cur = best
        while cur in parent:
            p, a = parent[cur]
            path.append(a); cur = p
        path.reverse()
    # (a) random-policy win probability, exact only on a complete graph.
    p_random = None
    if win_nodes and truncated is None and edges_path is not None:
        p_random = random_policy_win_probability(edges_path, meta, N)
    return dict(game=full_id, level=level_index + 1, actions=ACTIONS, states=N, edges=n_edges,
                truncated=bool(truncated), truncated_reason=truncated, max_states=max_states,
                win_states=len(win_nodes), game_over_states=over_nodes, win_reachable=bool(win_nodes),
                shortest_win_depth=shortest_win_depth, shortest_win_path=path,
                states_by_lives=dict(sorted(lives_hist.items(), reverse=True)),
                p_win_random_policy=p_random, one_over_states=(1.0 / N), win_over_states=(len(win_nodes) / N),
                inverse_p_win_random=(None if not p_random else 1.0 / p_random),
                reset_checked=reset_checked, reset_returns_to_start=reset_ok, reset_mismatches=reset_bad,
                double_advance_actions=len(double_advance), double_advance_examples=double_advance,
                root_abstract=a0, peak_rss_mb=round(rss_mb(), 1), rss_at_start_mb=round(rss0, 1),
                max_rss_mb_cap=max_rss_mb)


def random_policy_win_probability(edges_path: Path, meta: list, N: int) -> float:
    """p(s) = mean over the four actions of p(next); WIN = 1, GAME_OVER = 0.
    Sparse value iteration over the streamed edge file, using the TRUE node ids
    (never the coarser abstract vectors). Memory: two int32 arrays of one entry
    per edge plus two float arrays of one entry per state."""
    src_l: list[int] = []
    dst_l: list[int] = []
    with gzip.open(edges_path, "rt") as fh:
        for line in fh:
            e = json.loads(line)
            src_l.append(e["i"]); dst_l.append(e["j"])
    src = np.asarray(src_l, dtype=np.int32); dst = np.asarray(dst_l, dtype=np.int32)
    del src_l, dst_l
    st = np.asarray([m[0] for m in meta], dtype=np.int8)
    p = (st == 1).astype(np.float64)
    play = st == 0
    for _ in range(200_000):
        nxt = np.zeros(N); np.add.at(nxt, src, p[dst]); nxt /= 4.0
        nxt[~play] = p[~play]
        if np.max(np.abs(nxt - p)) < 1e-12:
            p = nxt; break
        p = nxt
    return float(p[0])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="ls20")
    ap.add_argument("--level", type=int, default=1, help="1-based")
    ap.add_argument("--max-states", type=int, default=200_000)
    ap.add_argument("--max-seconds", type=float, default=900)
    ap.add_argument("--max-rss-mb", type=float, default=4096)
    ap.add_argument("--max-reset-checks", type=int, default=500)
    ap.add_argument("--environments-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    out = a.out or (ROOT / "artifacts" / "env" / a.game)
    out.mkdir(parents=True, exist_ok=True)
    spec_path = ROOT / "artifacts" / "env" / a.game / f"level{a.level}.json"
    if spec_path.exists():
        set_energy_cells(json.loads(spec_path.read_text()).get("energy"))
    edges = out / f"graph_L{a.level}_edges.jsonl.gz"
    r = enumerate_level(a.game, a.level - 1, a.max_states, a.max_seconds, a.max_rss_mb,
                        max_reset_checks=a.max_reset_checks, edges_path=edges,
                        environments_dir=a.environments_dir)
    (out / f"graph_L{a.level}.json").write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in r.items() if k not in ("reset_mismatches", "double_advance_examples", "root_abstract")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
