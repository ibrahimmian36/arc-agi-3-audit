"""How many states an ARC-AGI-3 level has depends on what counts as a state.

Reads an enumerated level's streamed edges and reports, per remaining life:
  * the enumerator's own key count (finer than the rendered frame: it includes
    sprite order, which a life loss changes by re-appending consumed pickups);
  * the count of distinct RULE-LEVEL states (position, rotation, lives, steps,
    status, pickups consumed) -- the granularity a model reasons at.

Reject-only: this reports two counts and whether the rule-level space is
symmetric across lives, which is what the three-life mechanic implies. It
certifies nothing.

Usage: state_granularity.py [--game ls20] [--levels 1 2]
Artefact: artifacts/env/<game>/granularity.json, granularity.log
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Index into the recorded state vector (see state_graph.vec).
CX, CY, ROT, COLOR, SHAPE, LIVES, STEPS, STATUS, GOALS, EATEN = range(10)


def rule_level_counts(edges_path: Path) -> dict[str, int]:
    seen: dict[int, set] = collections.defaultdict(set)
    with gzip.open(edges_path, "rt") as fh:
        for line in fh:
            e = json.loads(line)
            for v in (e["s"], e["t"]):
                seen[v[LIVES]].add((v[CX], v[CY], v[ROT], v[LIVES], v[STEPS], v[STATUS], v[EATEN]))
    return {str(k): len(v) for k, v in sorted(seen.items(), reverse=True)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="ls20")
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2])
    a = ap.parse_args(argv)
    d = ROOT / "artifacts" / "env" / a.game
    out, log = {}, []
    for level in a.levels:
        gp, ep = d / f"graph_L{level}.json", d / f"graph_L{level}_edges.jsonl.gz"
        if not (gp.exists() and ep.exists()):
            continue
        g = json.loads(gp.read_text())
        rule = rule_level_counts(ep)
        live = [rule[k] for k in ("3", "2", "1") if k in rule]
        symmetric = len(live) == 3 and max(live) - min(live) <= 1
        out[f"L{level}"] = dict(key_states_by_lives=g["states_by_lives"], rule_states_by_lives=rule,
                                rule_symmetric_across_lives=symmetric,
                                key_states=g["states"], rule_states=sum(rule.values()))
        log.append(f"L{level} key_by_lives={g['states_by_lives']} rule_by_lives={rule} "
                   f"rule_symmetric={symmetric} key_total={g['states']} rule_total={sum(rule.values())}")
    (d / "granularity.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    (d / "granularity.log").write_text("\n".join(log) + "\n")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
