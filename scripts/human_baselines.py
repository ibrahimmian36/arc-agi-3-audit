"""Reproduce the published per-level human baselines from the human replays.

The benchmark publishes, per environment and level, an integer human baseline
described as the upper median of first-time players' action counts. The replay
dataset carries each human play's action stream and the toolkit's own scorecard
for it. This script streams every recording (one line in memory at a time),
counts each completed level's actions two ways -- as the scorer counts them,
level resets included ("charged"), and with level resets excluded
("uncharged") -- and asks which candidate rule reproduces the published
integers.

Preregistered reading (docs/DECISIONS.md, Phase 18): on cells where at least
one human reset and the two counts' medians differ, if the published baseline
equals the uncharged median and not the charged one, humans were not charged
for resets and the reset asymmetry is real; the reverse refutes it; a cell
that matches both or neither is reported as neither.

Only aggregates leave this script: per-cell sorted count lists and match
tallies. No recording name, participant identifier or timestamp is written.

Usage: human_baselines.py ARCHIVE.zip [--out artifacts/replays/human_baselines.json]
"""
from __future__ import annotations

import io
import json
import re
import resource
import statistics
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replays import parse_recording, per_level_counts, card_counts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MEMBER = re.compile(r"^public_games-dataset/([a-z0-9]+)/[0-9a-f-]+\.recording\.jsonl$")


def upper_median(xs):
    s = sorted(xs)
    return s[len(s) // 2]


def lower_median(xs):
    s = sorted(xs)
    return s[(len(s) - 1) // 2]


def rules():
    return {
        "upper_median": upper_median,
        "lower_median": lower_median,
        "median": lambda xs: statistics.median(xs),
        "mean": lambda xs: statistics.mean(xs),
    }


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    archive = Path(argv[1])
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else ROOT / "artifacts" / "replays" / "human_baselines.json"
    games = {g["game_id"].split("-")[0]: g for g in json.load(open(ROOT / "artifacts" / "api" / "games.json"))}

    # cell = (env, level) -> list of counts, per population
    cells = {pop: defaultdict(list) for pop in
             ("charged_all", "uncharged_all", "charged_first", "uncharged_first", "card_all")}
    resets_in_cell = defaultdict(int)
    n_rec = n_plays = n_card_agree = n_card_disagree = n_card_missing = n_card_old_offset = 0
    n_lines = 0
    version_mismatch = []
    t0 = time.time()
    import hashlib
    h = hashlib.sha256()
    with open(archive, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    sha = h.hexdigest()
    n_empty_card = n_old = 0
    with zipfile.ZipFile(archive) as z:
        members = [i for i in z.infolist() if MEMBER.match(i.filename)]
        for k, info in enumerate(sorted(members, key=lambda i: i.filename)):
            env = MEMBER.match(info.filename).group(1)
            with z.open(info) as f:
                def lines():
                    global _
                    for n, raw in enumerate(io.TextIOWrapper(f, encoding="utf-8"), 1):
                        raw = raw.strip()
                        if not raw:
                            continue
                        try:
                            yield n, json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                rec = parse_recording(lines())
            n_rec += 1
            n_old += rec["old_schema"]
            if rec["game_id"] and env in games and rec["game_id"] != games[env]["game_id"]:
                version_mismatch.append((env, rec["game_id"]))
            # The card can open an empty play before the real one; align on
            # the plays that have actions.
            card = [cc for cc in card_counts(rec["card"], rec["game_id"]) if cc["actions"]]
            if rec["card"] is not None and not card:
                n_empty_card += 1
            old_schema = bool(rec["plays"][0]) and rec["old_schema"]
            if not card:
                n_card_missing += 1
            for p, play in enumerate(rec["plays"]):
                if not play:
                    continue
                n_plays += 1
                c = per_level_counts(play)
                # cross-check against the toolkit's own per-level tally
                if p < len(card):
                    mine = [c["charged"].get(l, 0) for l in c["completed"]]
                    theirs = card[p]["per_level"]
                    resets_ok = card[p]["resets"] is None or sum(c["resets"].values()) == card[p]["resets"]
                    if mine == theirs and resets_ok:
                        n_card_agree += 1
                    elif old_schema and mine and theirs and mine[0] == theirs[0] + 1 and mine[1:] == theirs[1:] and resets_ok:
                        # the 2026-03 recorder's tally: one below at every boundary
                        n_card_old_offset += 1
                    else:
                        n_card_disagree += 1
                if p < len(card):
                    for l, v in enumerate(card[p]["per_level"]):
                        cells["card_all"][(env, l)].append(v)
                for l in c["completed"]:
                    ch, un = c["charged"][l], c["uncharged"].get(l, 0)
                    cells["charged_all"][(env, l)].append(ch)
                    cells["uncharged_all"][(env, l)].append(un)
                    if p == 0:
                        cells["charged_first"][(env, l)].append(ch)
                        cells["uncharged_first"][(env, l)].append(un)
                    resets_in_cell[(env, l)] += c["resets"].get(l, 0)
            if (k + 1) % 20 == 0:
                print(f"  {k+1}/{len(members)} recordings, {time.time()-t0:.0f}s", file=sys.stderr)

    # score every (population, rule) against the published integers
    published = {(env, l): b for env, g in games.items() for l, b in enumerate(g["baseline_actions"])}
    scores = {}
    for pop, cellmap in cells.items():
        for rname, rfn in rules().items():
            exact = off_by_one = total = 0
            for key, b in published.items():
                xs = cellmap.get(key)
                if not xs:
                    continue
                total += 1
                v = rfn(xs)
                if v == b:
                    exact += 1
                elif abs(v - b) <= 1:
                    off_by_one += 1
            scores[f"{pop}/{rname}"] = dict(exact=exact, off_by_one=off_by_one, cells=total)

    # the preregistered comparison, cell by cell, under the best-matching rule
    best = max(scores, key=lambda k: scores[k]["exact"])
    best_pop, best_rule = best.split("/")
    rfn = rules()[best_rule]
    suffix = best_pop.split("_")[1]
    decisive = []
    for key, b in sorted(published.items()):
        ch = cells[f"charged_{suffix}"].get(key); un = cells[f"uncharged_{suffix}"].get(key)
        if not ch:
            continue
        mc, mu = rfn(ch), rfn(un)
        if resets_in_cell[key] == 0 or mc == mu:
            continue
        verdict = ("charged" if b == mc and b != mu else
                   "uncharged" if b == mu and b != mc else "neither")
        decisive.append(dict(env=key[0], level=key[1] + 1, published=b, charged=mc, uncharged=mu,
                             resets=resets_in_cell[key], n=len(ch), verdict=verdict))

    cell_table = {}
    for key, b in sorted(published.items()):
        xs = cells["charged_all"].get(key, [])
        cell_table[f"{key[0]}/L{key[1]+1}"] = dict(
            published=b, n_plays=len(xs), resets=resets_in_cell[key],
            published_in_observed=(b in xs), card=sorted(cells["card_all"].get(key, [])),
            charged=sorted(xs), uncharged=sorted(cells["uncharged_all"].get(key, [])),
            charged_first=sorted(cells["charged_first"].get(key, [])),
            uncharged_first=sorted(cells["uncharged_first"].get(key, [])))
    per_env = defaultdict(lambda: dict(cells=0, exact=0, published_in_observed=0))
    for key, b in published.items():
        xs = cells["charged_all"].get(key)
        if not xs:
            continue
        e = per_env[key[0]]; e["cells"] += 1
        e["exact"] += (upper_median(xs) == b); e["published_in_observed"] += (b in xs)
    # A human count bounds the level's optimum from above: a cell whose
    # smallest human count is at or below the published baseline has a
    # baseline at or above the optimum. The search's lower bounds
    # (artifacts/minactions) must lie at or below every human count.
    bound = dict(consistent=0, undetermined=0, no_play=0)
    cells_below = []
    for key, b in sorted(published.items()):
        xs = cells["charged_all"].get(key)
        if not xs:
            bound["no_play"] += 1; continue
        if min(xs) <= b:
            bound["consistent"] += 1
        else:
            bound["undetermined"] += 1; cells_below.append(f"{key[0]}/L{key[1]+1}")
    minact = []
    for path in sorted((ROOT / "artifacts" / "minactions").glob("*_L*.json")):
        d = json.loads(path.read_text())
        key = (d["game"].split("-")[0], d["level"] - 1)
        xs = cells["charged_all"].get(key, [])
        lb = d["optimum"] if d["optimum"] is not None else d["min_actions_lower_bound"]
        minact.append(dict(cell=f"{key[0]}/L{key[1]+1}", baseline=d["baseline"], search=d["verdict"],
                           search_lower_bound=lb, human_min=(min(xs) if xs else None),
                           human_min_respects_bound=(lb is None or not xs or min(xs) >= lb),
                           now=("consistent" if xs and min(xs) <= d["baseline"] else d["verdict"])))
    result = dict(
        archive=archive.name, recordings=n_rec, plays=n_plays, per_env=dict(sorted(per_env.items())),
        human_bound=bound, human_bound_undetermined=cells_below, minactions_cells=minact,
        card_cross_check=dict(agree=n_card_agree, old_tally_offset=n_card_old_offset, disagree=n_card_disagree, missing_card=n_card_missing),
        version_mismatch=version_mismatch, scores=scores, best=best,
        decisive_cells=decisive,
        verdict_tally={v: sum(1 for d in decisive if d["verdict"] == v) for v in ("charged", "uncharged", "neither")},
        cells=cell_table, seconds=round(time.time() - t0, 1))
    result["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024), 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1))
    cc = result["card_cross_check"]
    sc = scores["charged_all/upper_median"]; su = scores["uncharged_all/upper_median"]; sk = scores["card_all/upper_median"]
    vt = result["verdict_tally"]
    not_repro = sorted({k.split("/")[0] for k, c in cell_table.items() if c["charged"] and upper_median(c["charged"]) != c["published"]})
    absent = sum(1 for c in cell_table.values() if c["charged"] and not c["published_in_observed"])
    log = [
        f"HUMAN recordings={n_rec} plays={n_plays} cells={sc['cells']} card_agree={cc['agree']} "
        f"card_old_tally_offset={cc['old_tally_offset']} card_disagree={cc['disagree']} version_mismatch={len(version_mismatch)}",
        f"HUMAN rule=upper_median charged_exact={sc['exact']} charged_off_by_one={sc['off_by_one']} "
        f"card_exact={sk['exact']} uncharged_exact={su['exact']} uncharged_off_by_one={su['off_by_one']}",
        f"HUMAN decisive_cells={len(decisive)} charged={vt['charged']} uncharged={vt['uncharged']} neither={vt['neither']}",
        f"HUMAN not_reproduced_envs={','.join(not_repro)} published_absent_from_release={absent}",
        f"HUMAN bound_consistent={bound['consistent']} bound_undetermined={bound['undetermined']} bound_no_play={bound['no_play']} "
        f"minactions_now_consistent={sum(1 for m in minact if m['now'] == 'consistent')} "
        f"minactions_bounds_respected={all(m['human_min_respects_bound'] for m in minact)}",
        "HUMAN not_reproduced " + " ".join(f"{e}={v['exact']}/{v['cells']}" for e, v in sorted(per_env.items()) if v["exact"] != v["cells"]),
        "HUMAN old_tally_cells=" + ",".join(
            f"{k}:published={c['published']}:card={upper_median(c['card'])}:stream={upper_median(c['charged'])}"
            for k, c in cell_table.items()
            if c["card"] and c["charged"] and upper_median(c["card"]) == c["published"] and upper_median(c["charged"]) == c["published"] + 1),
        f"ARCHIVE name={archive.name} bytes={archive.stat().st_size} sha256={sha} recordings={n_rec} announced=342 "
        f"empty_card_plays={n_empty_card} old_recorder_recordings={n_old}",
    ]
    # timing stays in the JSON only, so the log is byte-identical across runs
    out.with_suffix(".log").write_text("\n".join(log) + "\n")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
