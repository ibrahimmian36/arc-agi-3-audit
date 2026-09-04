"""Which search should the baseline check use?

The lower bound on a level's optimum needs a search that is complete to a stated
depth. Three qualify, and they trade memory against time differently:

  bfs    breadth-first, bounded by depth. Holds a whole layer of game objects.
  dldfs  one depth-limited depth-first pass with shallowest-depth memoisation.
         Holds only the objects along one path. All or nothing: it either
         completes its limit or proves nothing beyond the root.
  iddfs  those passes at increasing limits, banking a bound after each.

This measures the trade on the same levels rather than arguing it, because the
choice decides how many baselines the audit can check.

Reject-only. Scope: the public environments already on disk. No network.

Usage: search_comparison.py [--games ls20 tr87] [--level 1] [--out artifacts/searchcmp]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_GRAPH = ROOT / "scripts" / "state_graph.py"


def one(game: str, level: int, search: str, depth: int, actions: list[int],
        seconds: float, rss: float, states: int) -> dict:
    """Each run in its own process: the memory guard reads PEAK resident memory,
    so one heavy run would otherwise mark every later one as capped."""
    tmp = Path(tempfile.mkdtemp(prefix="cmp-"))
    try:
        t0 = time.time()
        p = subprocess.run([sys.executable, str(STATE_GRAPH), "--game", game, "--level", str(level),
                            "--search", search, "--no-edges", "--max-states", str(states),
                            "--max-seconds", str(seconds), "--max-rss-mb", str(rss),
                            "--max-depth", str(depth), "--max-reset-checks", "0",
                            "--actions", ",".join(str(x) for x in actions), "--out", str(tmp)],
                           capture_output=True, text=True, timeout=seconds + 120, cwd=str(ROOT))
        f = tmp / f"graph_L{level}.json"
        if not f.exists():
            return dict(search=search, error=(p.stderr or "no output")[-200:])
        d = json.loads(f.read_text())
        return dict(search=search, optimum=d.get("shortest_win_depth"),
                    explored_to_depth=d.get("explored_to_depth"),
                    lower_bound=d.get("min_actions_lower_bound"),
                    states=d["states"], peak_rss_mb=d.get("peak_rss_mb"),
                    truncated_reason=d.get("truncated_reason"),
                    wall_seconds=round(time.time() - t0, 1))
    except subprocess.TimeoutExpired:
        return dict(search=search, error="subprocess timeout")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", nargs="*", default=["ls20", "tr87"])
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--max-seconds", type=float, default=120)
    ap.add_argument("--max-rss-mb", type=float, default=2500)
    ap.add_argument("--max-states", type=int, default=400_000)
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "searchcmp")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    census = {r["game"]: r for r in json.loads((ROOT / "artifacts" / "sweep" / "action_census.json").read_text())}
    rows, lines = [], []
    for game in a.games:
        c = census[game]
        baseline = (c.get("baseline_actions") or [None])[a.level - 1]
        depth = (baseline + 1) if baseline else 100
        runs = [one(game, a.level, s, depth, c["simple_actions"], a.max_seconds,
                    a.max_rss_mb, a.max_states) for s in ("bfs", "iddfs")]
        rows.append(dict(game=game, level=a.level, baseline=baseline, depth_bound=depth, runs=runs))
        for r in runs:
            lines.append(f"{game:6s} L{a.level} {r['search']:6s} optimum={r.get('optimum')} "
                         f"explored_to={r.get('explored_to_depth')} bound={r.get('lower_bound')} "
                         f"states={r.get('states')} peak_rss_mb={r.get('peak_rss_mb')} "
                         f"stopped={r.get('truncated_reason')} wall_s={r.get('wall_seconds')}")
            print(lines[-1], flush=True)
    # Which search reached further, and which used less memory.
    verdicts = []
    for row in rows:
        by = {r["search"]: r for r in row["runs"] if "error" not in r}
        if len(by) < 2:
            continue
        deeper = max(by.values(), key=lambda r: (r.get("optimum") is not None,
                                                 r.get("explored_to_depth") or -1))["search"]
        lighter = min(by.values(), key=lambda r: r.get("peak_rss_mb") or 1e9)["search"]
        verdicts.append(dict(game=row["game"], level=row["level"], reached_further=deeper,
                             used_less_memory=lighter,
                             memory_ratio=round((by["bfs"].get("peak_rss_mb") or 0) /
                                                max(by["iddfs"].get("peak_rss_mb") or 1, 1), 2)))
        lines.append(f"VERDICT {row['game']} L{row['level']} reached_further={deeper} "
                     f"used_less_memory={lighter} bfs_over_iddfs_memory={verdicts[-1]['memory_ratio']}x")
        print(lines[-1], flush=True)
    (a.out / "search_comparison.json").write_text(json.dumps(dict(rows=rows, verdicts=verdicts),
                                                             indent=1, sort_keys=True) + "\n")
    (a.out / "search_comparison.log").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
