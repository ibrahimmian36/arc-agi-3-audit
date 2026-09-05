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
