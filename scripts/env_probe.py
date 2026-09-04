"""Environment differential (reference 1): the compiled level model versus the
SHIPPED implementation, (a) on every edge of the enumerated reachable graph
when it is complete, and (b) on N = 30 recorded traces (10 scripted + 20
random, seeds 0..19, length 200) regardless. Reject-only.

Usage: env_probe.py --game ls20 --level 1
Artefacts: artifacts/env/<game>/differential_L<k>.json, traces_L<k>.json, env.log
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import random
import shutil
import subprocess
from pathlib import Path

from arcengine import ActionInput, GameAction

ROOT = Path(__file__).resolve().parents[1]
MARK = "__DIFF__"
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from state_graph import abstract, make_game, open_gz, register_module, set_energy_cells, vec  # noqa: E402


def run_node(oracle: Path, edges: Path, module: str, timeout_s: float = 300.0) -> dict:
    node = shutil.which("node")
    env = {k: os.environ[k] for k in ("PATH",) if k in os.environ}
    try:
        p = subprocess.run([node, str(ROOT / "scripts" / "env_differential.cjs"), str(oracle), str(edges), module],
                           capture_output=True, text=True, timeout=timeout_s, env=env, cwd=str(ROOT / "scripts"))
    except subprocess.TimeoutExpired:
        return {"loaded": False, "error": "timeout", "rows": []}
    lines = [l for l in p.stdout.splitlines() if l.startswith(MARK)]
    return json.loads(lines[-1][len(MARK):]) if lines else {"loaded": False, "error": (p.stderr or "no output")[-300:], "rows": []}


def scripted_traces(witness: list[int] | None) -> list[list[int]]:
    w = witness or [1] * 22
    return [
        w,                                  # shortest win
        [4] * 60,                           # bump into a wall until a life is lost
        [1, 2] * 100,                       # oscillate: exhausts steps three times -> GAME_OVER
        w[:-1] + [3, 4] + w[-1:],           # detour then win
        [3] * 10 + [4] * 10 + [1] * 10 + [2] * 10,
        w[:5] + [2] * 50 + w[:5],
        [1] * 50 + [3] * 50,
        w + [1, 2, 3, 4],                   # actions after WIN (the recorder stops at WIN; the engine's post-terminal behaviour is covered by tests)
        [2, 2, 3, 3, 1, 1, 4, 4] * 25,
        (w[:len(w) // 2] + [4, 3]) * 6,
    ]


def record_traces(game: str, level_index: int, traces: list[list[int]], out_path: Path,
                  environments_dir: Path | None = None) -> dict:
    """Play each trace against the SHIPPED game and stream the transitions to a
    gzipped JSONL edge file in the same format the enumerator writes. A trace
    stops at WIN or GAME_OVER; actions after a terminal state are covered by the
    dedicated post-terminal traces, not by continuing here."""
    steps = 0
    nid = 0
    with open_gz(out_path, "wt") as fh:
        for t in traces:
            _, g = make_game(game, level_index, environments_dir)
            register_module(g)
            cur = abstract(g, level_index)
            src = nid
            for a in t:
                if cur["status"] != "PLAY":
                    break
                g.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)
                nxt = abstract(g, level_index)
                nid += 1
                fh.write(json.dumps({"i": src, "j": nid, "a": a, "s": vec(cur), "t": vec(nxt)},
                                    separators=(",", ":")) + "\n")
                steps += 1
                src = nid
                cur = nxt
            nid += 1
    return dict(traces=len(traces), steps=steps)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="ls20"); ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--module", default=None, help="Dafny module name (default Ls20Level<k>)")
    a = ap.parse_args(argv)
    d = ROOT / "artifacts" / "env" / a.game
    oracle = ROOT / "artifacts" / "oracle_env" / f"{a.game}_level{a.level}.js"
    module = a.module or f"Ls20Level{a.level}"
    spec_path = d / f"level{a.level}.json"
    if spec_path.exists():
        set_energy_cells(json.loads(spec_path.read_text()).get("energy"))
    gp = d / f"graph_L{a.level}.json"
    graph = json.loads(gp.read_text()) if gp.exists() else None
    edges_gz = d / f"graph_L{a.level}_edges.jsonl.gz"
    out = dict(game=a.game, level=a.level, oracle_present=oracle.exists())
    log = []
    if graph and not graph["truncated"] and edges_gz.exists():
        r = run_node(oracle, edges_gz, module)
        out["graph_edges"] = dict(loaded=r.get("loaded"), n=r.get("n"), disagreements=r.get("disagreements"),
                                  win_edges_status_only=r.get("win_edges_status_only"),
                                  model_errors=r.get("model_errors"), rows=r.get("rows", [])[:50], error=r.get("error"))
        log.append(f"GRAPH_EDGES n={r.get('n')} disagreements={r.get('disagreements')} "
                   f"win_edges_status_only={r.get('win_edges_status_only')} model_errors={r.get('model_errors')} "
                   f"loaded={r.get('loaded')} error={r.get('error')}")
    else:
        out["graph_edges"] = dict(skipped=True, reason="graph absent or truncated")
        log.append("GRAPH_EDGES skipped (graph absent or truncated)")
    rnd = []
    for seed in range(20):
        rng = random.Random(seed); rnd.append([rng.choice([1, 2, 3, 4]) for _ in range(200)])
    traces = scripted_traces(graph.get("shortest_win_path") if graph else None) + rnd
    tp = d / f"traces_L{a.level}.jsonl.gz"
    rec = record_traces(a.game, a.level - 1, traces, tp)
    r = run_node(oracle, tp, module)
    out["traces"] = dict(traces=rec["traces"], steps=rec["steps"], loaded=r.get("loaded"), n=r.get("n"), disagreements=r.get("disagreements"), win_edges_status_only=r.get("win_edges_status_only"), model_errors=r.get("model_errors"), rows=r.get("rows", [])[:50], error=r.get("error"))
    log.append(f"TRACES traces={rec['traces']} steps={rec['steps']} disagreements={r.get('disagreements')} "
               f"win_edges_status_only={r.get('win_edges_status_only')} model_errors={r.get('model_errors')} "
               f"loaded={r.get('loaded')} error={r.get('error')}")
    (d / f"differential_L{a.level}.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    (d / f"env_L{a.level}.log").write_text("\n".join(log) + "\n")
    print("\n".join(log))
    for row in (out["traces"].get("rows") or [])[:5]:
        if not row.get("agree"):
            print("first trace disagreement:", json.dumps(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
