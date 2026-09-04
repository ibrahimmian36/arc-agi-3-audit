"""Lower-bound check on the published human baselines.

Every ARC-AGI-3 score is a ratio against `baseline_actions[level]`, documented
as the upper-median action count of first-time human players. A human cannot
complete a level in fewer actions than the level's optimum, so:

    baseline_actions[l]  >=  minimum actions in which level l can be completed.

Breadth-first search supplies that minimum, and supplies it soundly even when it
does not finish: a BFS that has fully expanded every state at depth d without
reaching a win has PROVED no solution exists in d actions or fewer. So each
level yields one of three verdicts:

  consistent       a win was found at depth <= baseline
  IMPOSSIBLE       every state at depth `baseline` was expanded and none wins
  not established  a cap stopped the search before either could be shown

Reject-only. "Not established" is never reported as either of the others, and a
proved bound applies to the SHIPPED LOCAL environment at the pinned version,
which is not necessarily the environment the human study measured.

Scope: the public set only. The semi-private and private sets are out of scope
and are never fetched, probed or inferred.

Usage: min_actions.py [--games ...] [--levels 1 2] [--max-states N]
                      [--max-seconds S] [--max-rss-mb M] [--out artifacts/minactions]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Each level is enumerated in its OWN process. The memory guard reads PEAK
# resident memory (ru_maxrss never falls), so in a single process one heavy
# environment raised the peak above the cap and every environment after it was
# reported as capped -- tu93 needs three states and was reported as stopped by
# memory. Isolation makes the guard mean what it says, and it also keeps one
# environment's crash from ending the run.
STATE_GRAPH = ROOT / "scripts" / "state_graph.py"


def verdict_of(r: dict, baseline: int | None) -> tuple[str, str]:
    if baseline is None:
        return "no baseline", "the environment publishes no baseline for this level"
    opt = r.get("shortest_win_depth")
    if opt is not None:
        if opt <= baseline:
            return "consistent", f"optimum {opt} <= baseline {baseline}"
        # A win deeper than the baseline is only decisive if the search was
        # exhaustive up to the baseline, which BFS guarantees by construction.
        return "IMPOSSIBLE", f"optimum {opt} > baseline {baseline}"
    lb = r.get("min_actions_lower_bound")
    if lb is not None and lb > baseline:
        return "IMPOSSIBLE", (f"every state within {lb - 1} actions was expanded and none wins, "
                              f"so the optimum is at least {lb}, above the baseline of {baseline}")
    return "not established", (f"search stopped by {r.get('truncated_reason')} after completing "
                               f"depth {r.get('completed_depth')}, baseline {baseline}")


def run_one_level(game: str, level: int, actions: list[int], depth_bound: int, a) -> dict:
    """Enumerate one level in a fresh process and read back its result."""
    tmp = Path(tempfile.mkdtemp(prefix="minact-"))
    try:
        cmd = [sys.executable, str(STATE_GRAPH), "--game", game, "--level", str(level),
               "--search", a.search, "--no-edges", "--max-states", str(a.max_states),
               "--max-seconds", str(a.max_seconds), "--max-rss-mb", str(a.max_rss_mb),
               "--max-depth", str(depth_bound), "--actions", ",".join(str(x) for x in actions),
               # The reset probe belongs to the sweep, not here; it costs a deep
               # copy per node and this phase only needs the depth guarantee.
               "--max-reset-checks", "0",
               "--out", str(tmp)]
        if a.environments_dir:
            cmd += ["--environments-dir", str(a.environments_dir)]
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=a.max_seconds + 120, cwd=str(ROOT))
        out = tmp / f"graph_L{level}.json"
        if not out.exists():
            return {"error": (p.stderr or p.stdout or "no output")[-300:]}
        return json.loads(out.read_text())
    except subprocess.TimeoutExpired:
        return {"error": f"subprocess exceeded {a.max_seconds + 120:.0f}s"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", nargs="*", default=None)
    ap.add_argument("--levels", type=int, nargs="+", default=[1])
    ap.add_argument("--max-states", type=int, default=400_000)
    ap.add_argument("--max-seconds", type=float, default=300)
    ap.add_argument("--max-rss-mb", type=float, default=2500)
    ap.add_argument("--depth-margin", type=int, default=1,
                    help="search to baseline + margin; the bound only needs baseline")
    ap.add_argument("--census", type=Path, default=ROOT / "artifacts" / "sweep" / "action_census.json")
    ap.add_argument("--environments-dir", type=Path, default=ROOT / "environment_files")
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "minactions")
    ap.add_argument("--search", choices=("bfs", "dldfs", "iddfs"), default="iddfs",
                    help="iddfs by default: the same completeness guarantee to a stated depth, "
                         "holding only the objects along one path, and banking a bound after "
                         "every completed depth rather than all-or-nothing")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    census = {r["game"]: r for r in json.loads(a.census.read_text())}
    games = a.games or sorted(g for g, r in census.items() if r["enumerable"])
    lines = []
    for name in games:
        row = census.get(name)
        if row is None or not row.get("enumerable"):
            lines.append(f"{name:6s} SKIPPED not enumerable"); continue
        for level in a.levels:
            rp = a.out / f"{name}_L{level}.json"
            if rp.exists() and not a.force:
                d = json.loads(rp.read_text())
                lines.append(f"{name:6s} L{level} cached verdict={d['verdict']}")
                continue
            base = (row.get("baseline_actions") or [None] * 99)
            baseline = base[level - 1] if len(base) >= level else None
            depth_bound = (baseline + a.depth_margin) if baseline else 100_000
            t0 = time.time()
            r = run_one_level(name, level, row["simple_actions"], depth_bound, a)
            if "error" in r:
                rp.write_text(json.dumps(dict(game=name, level=level, error=r["error"][:300]),
                                         indent=1, sort_keys=True) + "\n")
                lines.append(f"{name:6s} L{level} ERROR {r['error'][:70]}")
                print(lines[-1], flush=True)
                continue
            v, why = verdict_of(r, baseline)
            out = dict(game=r["game"], level=level, baseline=baseline, verdict=v, reason=why,
                       optimum=r.get("shortest_win_depth"), witness=r.get("shortest_win_path"),
                       min_actions_lower_bound=r.get("min_actions_lower_bound"),
                       completed_depth=r.get("completed_depth"), depth_bound=depth_bound,
                       states=r["states"], edges=r["edges"], truncated_reason=r.get("truncated_reason"),
                       peak_rss_mb=r.get("peak_rss_mb"), wall_seconds=round(time.time() - t0, 1))
            rp.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
            lines.append(f"{name:6s} L{level} baseline={baseline} optimum={out['optimum']} "
                         f"lower_bound={out['min_actions_lower_bound']} completed_depth={out['completed_depth']} "
                         f"states={out['states']} verdict={v} ({why}) peak_rss_mb={out['peak_rss_mb']}")
            print(lines[-1], flush=True)
    write_summary(a.out, census, a.levels)
    (a.out / "min_actions.log").write_text("\n".join(lines) + "\n")
    return 0


def write_summary(out: Path, census: dict, levels: list[int]) -> None:
    rows = []
    for p in sorted(out.glob("*_L*.json")):
        d = json.loads(p.read_text())
        if d.get("error"):
            rows.append(dict(game=d["game"], level=d["level"], verdict="error")); continue
        rows.append({k: d[k] for k in ("game", "level", "baseline", "optimum",
                                       "min_actions_lower_bound", "completed_depth",
                                       "verdict", "reason", "states", "truncated_reason")})
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    impossible = [f"{r['game']}L{r['level']}" for r in rows if r["verdict"] == "IMPOSSIBLE"]
    (out / "summary.json").write_text(json.dumps(dict(counts=counts, impossible=impossible, rows=rows),
                                                 indent=1, sort_keys=True) + "\n")
    (out / "summary.log").write_text(
        f"SUMMARY levels_checked={len(rows)} consistent={counts.get('consistent', 0)} "
        f"impossible={counts.get('IMPOSSIBLE', 0)} not_established={counts.get('not established', 0)} "
        f"impossible_list={impossible}\n")
    print(open(out / "summary.log").read().strip())


if __name__ == "__main__":
    raise SystemExit(main())
