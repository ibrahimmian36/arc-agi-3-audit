"""The harness's per-level budget applied to the released human plays.

Preregistered in docs/PREREGISTRATION.md section 7. For every level a human
completed: c = actions the scorer charges (level resets included, the
construction reset excluded); g = resets issued straight after a GAME_OVER
frame, the reset the harness itself forces; B = ceil(5 * baseline). The harness
lets the completion stand iff c <= B; it is cut off only because post-game-over
resets are counted iff c > B and c - g <= B.

Only aggregates are written. Usage: human_budget.py ARCHIVE.zip
"""
from __future__ import annotations

import io
import json
import math
import re
import statistics
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from replays import RESET, parse_recording  # noqa: E402

MEMBER = re.compile(r"^public_games-dataset/([a-z0-9]+)/[0-9a-f-]+\.recording\.jsonl$")
MULT = 5.0


def level_tallies(play: list[dict]) -> list[tuple[int, int, int]]:
    """(level, charged, post_game_over_resets) for each level the play completed."""
    out, charged, gor, current = [], 0, 0, 0
    prev_state = None
    for i, s in enumerate(play):
        construction = (i == 0 and s["action"] == RESET)
        if not construction:
            charged += 1
            if s["action"] == RESET and prev_state == "GAME_OVER":
                gor += 1
        prev_state = s["state"]
        if s["levels"] > current:
            out.append((current, charged, gor))
            # a frame that completes two levels credits the second with nothing
            for k in range(current + 1, s["levels"]):
                out.append((k, 0, 0))
            current, charged, gor = s["levels"], 0, 0
    return out


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    archive = Path(argv[1])
    games = {g["game_id"].split("-")[0]: g["baseline_actions"]
             for g in json.load(open(ROOT / "artifacts" / "api" / "games.json"))}
    n = over = only_gor = 0
    with zipfile.ZipFile(archive) as z:
        for info in sorted(z.infolist(), key=lambda i: i.filename):
            m = MEMBER.match(info.filename)
            if not m:
                continue
            env = m.group(1)
            with z.open(info) as f:
                def lines():
                    for k, raw in enumerate(io.TextIOWrapper(f, encoding="utf-8"), 1):
                        raw = raw.strip()
                        if raw:
                            try:
                                yield k, json.loads(raw)
                            except json.JSONDecodeError:
                                continue
                rec = parse_recording(lines())
            for play in rec["plays"]:
                for level, c, g in level_tallies(play):
                    if level >= len(games[env]) or c == 0:
                        continue
                    b = math.ceil(games[env][level] * MULT)
                    n += 1
                    if c > b:
                        over += 1
                        if c - g <= b:
                            only_gor += 1
    cells = json.load(open(ROOT / "artifacts" / "replays" / "human_baselines.json"))["cells"]
    ns = sorted(c["n_plays"] for c in cells.values())
    small = sum(1 for x in ns if x < 5)
    lines_out = [
        f"HUMANBUDGET completions={n} over_budget={over} cut_only_by_post_game_over_resets={only_gor}",
        f"HUMANCELLS cells={len(ns)} plays_min={ns[0]} plays_median={statistics.median(ns):g} "
        f"plays_max={ns[-1]} cells_under_5_plays={small}",
    ]
    out = ROOT / "artifacts" / "replays" / "human_budget.log"
    out.write_text("\n".join(lines_out) + "\n")
    print("\n".join(lines_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
