"""Breadth sweep: enumerate the reachable state graph of ONE level of every
PUBLIC environment whose action space is small enough, and report the three
audit questions the enumerator answers without any model:

  * is the level winnable from its own start state;
  * does RESET restore the start state, or does something leak across it;
  * can one action advance the level counter by two (the F3 scorer edge).

Reject-only. A capped run reports the cap that stopped it and claims nothing it
cannot know: "not established within budget" is not "unreachable".

Resumable and checkpointed: each environment's result is written the moment it
finishes, and a completed environment is skipped on a later run, so a cap or a
crash costs one environment rather than the sweep.

Scope: the public set only. The semi-private and private sets are out of scope
and are never fetched, probed or inferred.

Usage: sweep.py [--level 1] [--games ls20 tr87] [--max-states N] [--max-seconds S]
                [--max-rss-mb M] [--out artifacts/sweep] [--force]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from state_graph import enumerate_level  # noqa: E402


def load_census(out: Path) -> list[dict]:
    p = out / "action_census.json"
    if not p.exists():
        raise SystemExit("run scripts/action_census.py first")
    return json.loads(p.read_text())


def valid_result(path: Path) -> dict | None:
    """A result file is trusted only if it parses and carries the fields the
    summary needs; anything else is re-run rather than silently believed."""
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text())
    except Exception:
        return None
    need = ("states", "edges", "win_reachable", "truncated", "reset_checked",
            "reset_returns_to_start", "double_advance_actions")
    return d if all(k in d for k in need) else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--games", nargs="*", default=None)
    ap.add_argument("--max-states", type=int, default=400_000)
    ap.add_argument("--max-seconds", type=float, default=300)
    ap.add_argument("--max-rss-mb", type=float, default=3000)
    ap.add_argument("--max-reset-checks", type=int, default=500)
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "sweep")
    ap.add_argument("--environments-dir", type=Path, default=ROOT / "environment_files")
    ap.add_argument("--search", choices=("bfs", "dfs"), default="dfs",
                    help="dfs by default: it holds only the objects along one path, so memory is O(depth) "
                         "rather than O(layer width), which is what stopped tr87 at the RSS cap under bfs")
    ap.add_argument("--max-depth", type=int, default=100_000)
    ap.add_argument("--force", action="store_true", help="re-run environments that already have a result")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    census = {r["game"]: r for r in load_census(a.out)}
    games = a.games or sorted(census)
    lines = []
    for name in games:
        row = census.get(name)
        if row is None:
            lines.append(f"{name:6s} SKIPPED not in the census"); continue
        rp = a.out / f"{name}_L{a.level}.json"
        if not row.get("enumerable"):
            rp.write_text(json.dumps(dict(game=row["game_id"], level=a.level, skipped=True,
                                          reason=row["reason"], actions=row["actions"],
                                          branching_factor=row["branching_factor"]),
                                     indent=1, sort_keys=True) + "\n")
            lines.append(f"{name:6s} SKIPPED {row['reason']}")
            continue
        existing = None if a.force else valid_result(rp)
        if existing is not None:
            lines.append(f"{name:6s} cached states={existing['states']} win={existing['win_reachable']}")
            continue
        t0 = time.time()
        try:
            r = enumerate_level(name, a.level - 1, a.max_states, a.max_seconds, a.max_rss_mb,
                                max_reset_checks=a.max_reset_checks, edges_path=None,
                                environments_dir=a.environments_dir, actions=row["simple_actions"],
                                search=a.search, max_depth=a.max_depth)
        except Exception as e:  # noqa: BLE001 -- one environment must not end the sweep
            rp.write_text(json.dumps(dict(game=row["game_id"], level=a.level, error=str(e)[:300],
                                          traceback=traceback.format_exc()[-1500:]),
                                     indent=1, sort_keys=True) + "\n")
            lines.append(f"{name:6s} ERROR {type(e).__name__}: {str(e)[:80]}")
            continue
        r["baseline_actions_level"] = (row.get("baseline_actions") or [None])[a.level - 1] \
            if row.get("baseline_actions") and len(row["baseline_actions"]) >= a.level else None
        r["wall_seconds"] = round(time.time() - t0, 1)
        rp.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
        lines.append(
            f"{name:6s} states={r['states']} edges={r['edges']} win_reachable={r['win_reachable']} "
            f"win_depth={r['first_win_depth']} baseline={r['baseline_actions_level']} "
            f"reset={r['reset_returns_to_start']}/{r['reset_checked']} "
            f"double_advance={r['double_advance_actions']} truncated={r['truncated_reason']} "
            f"peak_rss_mb={r['peak_rss_mb']} wall_s={r['wall_seconds']}")
        print(lines[-1], flush=True)
    write_summary(a.out, a.level, census)
    (a.out / f"sweep_L{a.level}.log").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-3:]))
    return 0


def write_summary(out: Path, level: int, census: dict) -> None:
    rows = []
    for name in sorted(census):
        d = valid_result(out / f"{name}_L{level}.json")
        if d is None:
            p = out / f"{name}_L{level}.json"
            raw = json.loads(p.read_text()) if p.exists() else {}
            rows.append(dict(game=name, status="skipped" if raw.get("skipped") else
                             ("error" if raw.get("error") else "not run"), reason=raw.get("reason") or raw.get("error")))
            continue
        rows.append(dict(game=name, status="truncated" if d["truncated"] else "complete",
                         truncated_reason=d.get("truncated_reason"), states=d["states"], edges=d["edges"],
                         win_reachable=d["win_reachable"], win_established=d.get("win_established"),
                         first_win_depth=d.get("first_win_depth"), search=d.get("search"),
                         baseline_actions_level=d.get("baseline_actions_level"),
                         reset_returns_to_start=d["reset_returns_to_start"], reset_checked=d["reset_checked"],
                         reset_mismatch=d["reset_checked"] != d["reset_returns_to_start"],
                         double_advance_actions=d["double_advance_actions"],
                         inverse_p_win_random=d.get("inverse_p_win_random"),
                         peak_rss_mb=d.get("peak_rss_mb"), unhandled_types=d.get("unhandled_types")))
    complete = [r for r in rows if r["status"] == "complete"]
    flags = dict(
        unwinnable_complete=[r["game"] for r in complete if r.get("win_established") and not r["win_reachable"]],
        win_not_established=[r["game"] for r in rows if r.get("win_established") is False],
        reset_mismatch=[r["game"] for r in rows if r.get("reset_mismatch")],
        double_advance=[r["game"] for r in rows if r.get("double_advance_actions")],
        truncated=[r["game"] for r in rows if r["status"] == "truncated"],
        skipped=[r["game"] for r in rows if r["status"] == "skipped"],
        errored=[r["game"] for r in rows if r["status"] == "error"],
    )
    enumerated = [r for r in rows if r["status"] in ("complete", "truncated")]
    totals = dict(
        environments=len(rows),
        enumerable=len(enumerated),
        skipped_click=len(flags["skipped"]),
        complete=len(complete),
        transitions_examined=sum(r["edges"] for r in enumerated),
        states_examined=sum(r["states"] for r in enumerated),
        reset_probes=sum(r["reset_checked"] for r in enumerated),
        reset_returns_to_start=sum(r["reset_returns_to_start"] for r in enumerated),
        double_advance_actions=sum(r["double_advance_actions"] for r in enumerated),
        peak_rss_mb_max=max((r["peak_rss_mb"] for r in enumerated), default=None),
    )
    summary = dict(level=level, environments=len(rows), complete=len(complete),
                   totals=totals, flags=flags, rows=rows)
    (out / f"summary_L{level}.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (out / f"summary_L{level}.log").write_text(
        f"SUMMARY level={level} environments={len(rows)} complete={len(complete)} "
        f"unwinnable={flags['unwinnable_complete']} reset_mismatch={flags['reset_mismatch']} "
        f"double_advance={flags['double_advance']} truncated={flags['truncated']} "
        f"skipped={len(flags['skipped'])} errored={flags['errored']}\n"
        f"TOTALS enumerable={totals['enumerable']} skipped_click={totals['skipped_click']} "
        f"complete={totals['complete']} states_examined={totals['states_examined']} "
        f"transitions_examined={totals['transitions_examined']} "
        f"reset_probes={totals['reset_probes']} reset_returns_to_start={totals['reset_returns_to_start']} "
        f"double_advance_actions={totals['double_advance_actions']} "
        f"peak_rss_mb_max={totals['peak_rss_mb_max']}\n")


if __name__ == "__main__":
    raise SystemExit(main())
