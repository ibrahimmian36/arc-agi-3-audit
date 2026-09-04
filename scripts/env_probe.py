"""Environment differential (reference 1): the compiled level model versus the
SHIPPED implementation, (a) on every edge of the enumerated reachable graph
when it is complete, and (b) on N = 30 recorded traces (10 scripted + 20
random, seeds 0..19, length 200) regardless. Reject-only.

Usage: env_probe.py --game ls20 --level 1
Artefacts: artifacts/env/<game>/differential_L<k>.json, traces_L<k>.json, env.log
"""
from __future__ import annotations

import argparse
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
from state_graph import abstract, make_game, register_module  # noqa: E402


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
        w + [1, 2, 3, 4],                   # actions after WIN
        [2, 2, 3, 3, 1, 1, 4, 4] * 25,
        (w[:len(w) // 2] + [4, 3]) * 6,
    ]


def record_traces(game: str, level_index: int, traces: list[list[int]]) -> dict:
    nodes, edges = [], []
    for t in traces:
        _, g = make_game(game, level_index)
        register_module(g)
        nodes.append(dict(i=len(nodes), status=abstract(g, level_index)["status"], abs=abstract(g, level_index)))
        for a in t:
            if nodes[-1]["status"] != "PLAY":
                break
            g.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)
            nodes.append(dict(i=len(nodes), status=abstract(g, level_index)["status"], abs=abstract(g, level_index)))
            edges.append([nodes[-2]["i"], a, nodes[-1]["i"]])
    return dict(nodes=nodes, edges=edges, traces=len(traces), steps=len(edges))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="ls20"); ap.add_argument("--level", type=int, default=1)
    a = ap.parse_args(argv)
    d = ROOT / "artifacts" / "env" / a.game
    oracle = ROOT / "artifacts" / "oracle_env" / f"{a.game}_level{a.level}.js"
    module = f"Ls20Level{a.level}"
    graph = json.loads((d / f"graph_L{a.level}.json").read_text()) if (d / f"graph_L{a.level}.json").exists() else None
    out = dict(game=a.game, level=a.level, oracle_present=oracle.exists())
    log = []
    if graph and not graph["truncated"] and (d / f"graph_L{a.level}_edges.json").exists():
        r = run_node(oracle, d / f"graph_L{a.level}_edges.json", module)
        out["graph_edges"] = dict(loaded=r.get("loaded"), n=r.get("n"), disagreements=r.get("disagreements"), win_edges_status_only=r.get("win_edges_status_only"), rows=r.get("rows", [])[:50], error=r.get("error"))
        log.append(f"GRAPH_EDGES n={r.get('n')} disagreements={r.get('disagreements')} win_edges_status_only={r.get('win_edges_status_only')} loaded={r.get('loaded')} error={r.get('error')}")
    else:
        out["graph_edges"] = dict(skipped=True, reason="graph absent or truncated")
        log.append("GRAPH_EDGES skipped (graph absent or truncated)")
    rnd = []
    for seed in range(20):
        rng = random.Random(seed); rnd.append([rng.choice([1, 2, 3, 4]) for _ in range(200)])
    traces = scripted_traces(graph.get("shortest_win_path") if graph else None) + rnd
    rec = record_traces(a.game, a.level - 1, traces)
    tp = d / f"traces_L{a.level}.json"; tp.write_text(json.dumps(rec, sort_keys=True) + "\n")
    r = run_node(oracle, tp, module)
    out["traces"] = dict(traces=rec["traces"], steps=rec["steps"], loaded=r.get("loaded"), n=r.get("n"), disagreements=r.get("disagreements"), win_edges_status_only=r.get("win_edges_status_only"), rows=r.get("rows", [])[:50], error=r.get("error"))
    log.append(f"TRACES traces={rec['traces']} steps={rec['steps']} disagreements={r.get('disagreements')} win_edges_status_only={r.get('win_edges_status_only')} loaded={r.get('loaded')} error={r.get('error')}")
    (d / f"differential_L{a.level}.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    (d / "env.log").write_text("\n".join(log) + "\n")
    print("\n".join(log))
    for row in (out["traces"].get("rows") or [])[:5]:
        if not row.get("agree"):
            print("first trace disagreement:", json.dumps(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
