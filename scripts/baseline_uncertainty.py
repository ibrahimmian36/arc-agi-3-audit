"""How stable the published baselines are (preregistered, PREREGISTRATION.md s.8).

For each cell (one level of one environment), bootstrap its human plays and
recompute the upper median, the published statistic, 2,000 times, each cell
with its own generator seeded from its name. The 95% percentile interval says
how far the baseline could move under a different draw of players; the score
effect is what an agent finishing in exactly the published baseline b would
receive if the true baseline were an end of that interval, 100*(end/b)^2 capped
at 115. Reads only the derived per-cell counts. Usage: baseline_uncertainty.py
"""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESAMPLES = 2000


def upper_median(xs):
    s = sorted(xs)
    return s[len(s) // 2]


def interval(xs, seed: str, resamples: int = RESAMPLES) -> tuple[int, int]:
    rng = random.Random(seed)
    n = len(xs)
    stats = sorted(upper_median([xs[rng.randrange(n)] for _ in range(n)]) for _ in range(resamples))
    return stats[int(0.025 * resamples)], stats[int(0.975 * resamples) - 1]


def score_at(end: int, b: int) -> float:
    return min(115.0, 100.0 * (end / b) ** 2)


def summarise(rows):
    widths = [r["rel_width"] for r in rows]
    return dict(cells=len(rows),
                median_rel_width=round(statistics.median(widths), 3),
                median_rel_width_pct=round(100 * statistics.median(widths), 1),
                max_rel_width=round(max(widths), 3),
                published_inside=sum(r["inside"] for r in rows),
                median_score_low=round(statistics.median(r["score_low"] for r in rows), 1),
                median_score_high=round(statistics.median(r["score_high"] for r in rows), 1))


def main() -> int:
    cells = json.load(open(ROOT / "artifacts" / "replays" / "human_baselines.json"))["cells"]
    rows = []
    for name, c in sorted(cells.items()):
        xs, b = c["charged"], c["published"]
        lo, hi = interval(xs, name)
        rows.append(dict(cell=name, n=len(xs), published=b, lo=lo, hi=hi,
                         rel_width=(hi - lo) / b, inside=(lo <= b <= hi),
                         score_low=score_at(lo, b), score_high=score_at(hi, b)))
    allc, small = summarise(rows), summarise([r for r in rows if r["n"] < 5])
    out = ROOT / "artifacts" / "replays"
    (out / "baseline_uncertainty.json").write_text(json.dumps(dict(all=allc, under_5=small, cells=rows), indent=1))
    log = [
        f"BASEUNC all resamples={RESAMPLES} " + " ".join(f"{k}={v}" for k, v in allc.items()),
        "BASEUNC under5 " + " ".join(f"{k}={v}" for k, v in small.items()),
    ]
    (out / "baseline_uncertainty.log").write_text("\n".join(log) + "\n")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
