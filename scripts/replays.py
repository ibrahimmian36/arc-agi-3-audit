"""Read the Foundation's human replay recordings without loading them whole.

The dataset is 342 files named <uuid>.recording.jsonl, one JSON record per
line, up to tens of megabytes each because frames are embedded. They are read
one line at a time and never held in memory together; a file that is truncated
mid-line yields its complete lines and reports the partial one.

The record schema is learned from the data with `inspect`, after the archive is
fetched with the lead author's explicit go-ahead. Nothing here fetches anything,
and nothing here writes any participant identifier into an artefact: the
file's uuid is replaced by its position in a sorted listing.

Usage:
    replays.py inspect <file> [--records 3]     # keys and shapes of the first records
    replays.py count <dir>                      # files, lines, bytes per environment
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Iterator


def stream_jsonl(path: Path) -> Iterator[tuple[int, dict]]:
    """Yield (line_number, record) for each complete JSON line.

    Memory is bounded by the longest single line. A trailing partial line (a
    recording cut off mid-write) is reported once on stderr and skipped, and a
    line that is not JSON is reported with its number and skipped, so one bad
    line never loses the rest of the file.
    """
    with open(path, "rb") as f:
        for n, raw in enumerate(f, 1):
            if not raw.endswith(b"\n"):
                if raw.strip():
                    print(f"{path.name}:{n}: partial final line skipped", file=sys.stderr)
                break
            line = raw.strip()
            if not line:
                continue
            try:
                yield n, json.loads(line)
            except json.JSONDecodeError as e:
                print(f"{path.name}:{n}: not JSON ({e.msg}); skipped", file=sys.stderr)


def shape(v, depth: int = 0) -> str:
    """A compact description of a value's structure, never its content."""
    if isinstance(v, dict):
        if depth > 2:
            return "{...}"
        return "{" + ", ".join(f"{k}: {shape(x, depth + 1)}" for k, x in list(v.items())[:12]) + ("…}" if len(v) > 12 else "}")
    if isinstance(v, list):
        if not v:
            return "[]"
        inner = shape(v[0], depth + 1)
        return f"[{len(v)} × {inner}]"
    return type(v).__name__


def inspect(path: Path, records: int) -> None:
    for n, rec in stream_jsonl(path):
        print(f"record {n}: {shape(rec)}")
        if n >= records:
            break


def count(root: Path) -> None:
    per_env: Counter = Counter()
    lines: Counter = Counter()
    size: Counter = Counter()
    for p in sorted(root.rglob("*.recording.jsonl")):
        env = p.parent.name
        per_env[env] += 1
        size[env] += p.stat().st_size
        with open(p, "rb") as f:
            lines[env] += sum(1 for _ in f)
    for env in sorted(per_env):
        print(f"{env} files={per_env[env]} lines={lines[env]} bytes={size[env]}")
    print(f"TOTAL files={sum(per_env.values())} lines={sum(lines.values())} bytes={sum(size.values())}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect"); i.add_argument("file", type=Path); i.add_argument("--records", type=int, default=3)
    c = sub.add_parser("count"); c.add_argument("dir", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "inspect":
        inspect(a.file, a.records)
    else:
        count(a.dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ── the recording format, as observed on 2026-09-05 ─────────────────────────
#
# One JSON object per line: {"timestamp", "data"}. Every line but the last is
# a frame after one action, and `data` is the toolkit's FrameData: game_id,
# frame, state, levels_completed, win_levels, action_input{id, data}, guid,
# full_reset, available_actions. The first action is the construction RESET.
# The last line's `data` is the toolkit's scorecard summary for the session:
# won, played, total_actions, levels_completed, cards{game_id: Card}, where the
# Card carries per-play lists: actions, actions_by_level, resets, states, guids.

RESET = 0
_NAMES = {"RESET": 0, **{f"ACTION{i}": i for i in range(1, 8)}}


def action_id(v) -> int:
    """Recordings from 2026-03 carry action names ("ACTION6"); later ones ids."""
    if isinstance(v, str):
        if v not in _NAMES:
            raise ValueError(f"unknown action name {v!r}")
        return _NAMES[v]
    return int(v)


def parse_recording(lines) -> dict:
    """Reduce a recording to what the analysis needs, frames discarded.

    Returns plays (split at full resets), each a list of steps
    {action, levels, state}, the game id, and the final card if present. The
    first construction RESET of each play is kept in the step list but marked
    so counts can exclude it the way the toolkit does.
    """
    game_id = None
    plays: list[list[dict]] = [[]]
    card = None
    old_schema = False
    for n, rec in lines:
        d = rec.get("data", {})
        if "action_input" not in d:
            if "cards" in d:
                card = d
            continue
        game_id = game_id or d.get("game_id")
        old_schema = old_schema or isinstance(d["action_input"]["id"], str)
        step = dict(action=action_id(d["action_input"]["id"]), levels=d["levels_completed"],
                    state=d["state"], full_reset=bool(d.get("full_reset")), line=n)
        if step["full_reset"] and plays[-1]:
            plays.append([])
        plays[-1].append(step)
    return dict(game_id=game_id, plays=plays, card=card, old_schema=old_schema)


def per_level_counts(play: list[dict]) -> dict:
    """Per-level action counts for one play, two ways.

    `charged` counts every action the scorer counts (all but the construction
    reset, level resets included); `uncharged` excludes level resets. A level k
    is credited when levels_completed rises past k; counts for a level never
    completed are reported under `incomplete`.
    """
    charged: dict[int, int] = {}
    uncharged: dict[int, int] = {}
    resets: dict[int, int] = {}
    completed: set[int] = set()
    current = 0
    for i, s in enumerate(play):
        is_construction = (i == 0 and s["action"] == RESET)
        level = current
        if not is_construction:
            charged[level] = charged.get(level, 0) + 1
            if s["action"] == RESET:
                resets[level] = resets.get(level, 0) + 1
            else:
                uncharged[level] = uncharged.get(level, 0) + 1
        if s["levels"] > current:
            for k in range(current, s["levels"]):
                completed.add(k)
            current = s["levels"]
    return dict(charged=charged, uncharged=uncharged, resets=resets,
                completed=sorted(completed), final_level=current,
                final_state=(play[-1]["state"] if play else None))


def card_counts(card: dict, game_id: str) -> list[dict]:
    """The toolkit's own per-play accounting from the session's card."""
    if not card or game_id not in card.get("cards", {}):
        return []
    c = card["cards"][game_id]
    out = []
    for p in range(len(c.get("actions", []))):
        # actions_by_level is a list of [level_reached, cumulative_actions]
        abl = c["actions_by_level"][p] if p < len(c.get("actions_by_level", [])) else []
        cum = [int(a) for _, a in abl]
        per_level = [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, len(cum))] if cum else []
        out.append(dict(actions=c["actions"][p], per_level=per_level,
                        resets=c["resets"][p] if p < len(c.get("resets", [])) else None,
                        levels_completed=c["levels_completed"][p] if p < len(c.get("levels_completed", [])) else None,
                        state=c["states"][p] if p < len(c.get("states", [])) else None))
    return out
