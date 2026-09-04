"""How far does the aggregation defect reach?

Phase 5 found that the public toolkit divides the sum of environment scores by
the number of environments a scorecard contains. This asks two follow-ups that
decide what that finding means:

  1. WHICH code path produces the score in each operation mode. If an
     API-backed run's score comes from the server, the local arithmetic never
     runs for it and the finding is confined to the local path by construction.
  2. WITHIN the local path, does an environment that fails, is skipped, or is
     never started leave the denominator, or does it stay as a zero?

Reject-only, and conditional by construction: every result names the operation
mode and the code path it is about. The server-side scorer is not observable to
us and nothing here is a claim about it, about the official leaderboard, or
about any particular reported result.

Scope: the public toolkit at the pinned commit. No environment, no network --
the online paths are exercised with an intercepting transport that records the
attempt and never opens a socket.

Usage: aggregation_probe.py [--out artifacts/aggregation]
"""
from __future__ import annotations

import argparse
import json
import logging
import resource
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arc_agi.models import EnvironmentInfo  # noqa: E402
from arc_agi.scorecard import EnvironmentScorecard, Scorecard  # noqa: E402
from score_pipeline_probe import MOVE, linear_play, play, start  # noqa: E402

B5 = [10, 10, 10, 10, 10]


# --------------------------------------------------------------------------
# 1. Which code path produces the score, per operation mode
# --------------------------------------------------------------------------

class Intercepted(Exception):
    """Raised instead of opening a socket, to record that the remote path was taken."""


def mode_table() -> list[dict]:
    """For each mode, does `get_scorecard` compute locally or fetch remotely?

    Determined by running it, not by reading it: the session is replaced with one
    that raises on any request, so a mode that reaches the network is identified
    by the exception and a mode that does not is identified by returning a
    locally computed object. No socket is ever opened.
    """
    rows = []
    for mode in (OperationMode.OFFLINE, OperationMode.NORMAL,
                 OperationMode.ONLINE, OperationMode.COMPETITION):
        lg = logging.getLogger("agg"); lg.setLevel(logging.CRITICAL)
        arc = Arcade(arc_api_key="probe-key", operation_mode=mode,
                     environments_dir=str(ROOT / "vendor" / "ARC-AGI" / "test_environment_files"),
                     logger=lg)

        class NoNetwork:
            cookies = {}

            @staticmethod
            def _where(method: str, args) -> str:
                """The endpoint reached, with the scorecard id removed. Recording
                the raw URL put a random uuid in the artefact and destroyed
                byte-identity on a re-run."""
                url = str(args[0]) if args else ""
                path = url.split("/api/", 1)[1] if "/api/" in url else url
                head = path.split("/", 1)[0]
                return f"{method} /api/{head}"

            def get(self, *a, **k): raise Intercepted(self._where("GET", a))
            def post(self, *a, **k): raise Intercepted(self._where("POST", a))
        arc._session = NoNetwork()
        card_id = arc.scorecard_manager.new_scorecard(
            api_key="probe-key", source_url=None, tags=None, opaque=None)
        arc._default_scorecard_id = card_id
        where, detail = "local", None
        try:
            out = arc.get_scorecard(card_id)
            where = "local computation (EnvironmentScorecard.from_scorecard)"
            detail = None if out is None else round(out.score, 6)
        except Intercepted as e:
            where = "remote fetch (server supplies the scorecard)"
            detail = str(e)[:60]
        rows.append(dict(mode=mode.value, score_produced_by=where, detail=detail))
    return rows


# --------------------------------------------------------------------------
# 2. The denominator under failure
# --------------------------------------------------------------------------

def build(cards: dict[str, list[list[dict]]], infos: list[str],
          baselines: dict[str, list[int]], start_only: tuple[str, ...] = ()) -> dict:
    sc = Scorecard(card_id="probe", api_key="")
    for game_id, plays in cards.items():
        for j, steps in enumerate(plays):
            guid = f"{game_id}-g{j}"
            start(sc, game_id, guid)
            play(sc, game_id, guid, steps)
    for game_id in start_only:
        # A card that exists but whose play never began: the wrapper opened the
        # environment and nothing was recorded against it.
        sc.new_play(game_id, f"{game_id}-g0")
    env_infos = [EnvironmentInfo(game_id=g, title=g.upper(), baseline_actions=baselines.get(g, B5))
                 for g in infos]
    out = EnvironmentScorecard.from_scorecard(sc, env_infos)
    d = json.loads(out.model_dump_json())
    return dict(total=round(d["score"], 9),
                environments={e["id"]: round(e["score"], 9) for e in d["environments"]},
                messages={e["id"]: (e["runs"][0].get("message") if e.get("runs") else None)
                          for e in d["environments"]})


def denominator_probes() -> list[dict]:
    perfect = linear_play([10] * 5)
    nothing = [dict(action=MOVE, levels=0) for _ in range(20)]
    three = ("aa00", "bb00", "cc00")
    return [
        dict(id="D1", note="three environments played perfectly, set size 3 (the Phase 5 baseline)",
             cards={g: [perfect] for g in three}, infos=list(three), set_size=3),
        dict(id="D2", note="the same three, but the set has 135 environments",
             cards={g: [perfect] for g in three}, infos=list(three), set_size=135),
        dict(id="D3", note="three of four played; the fourth never produced a card (a failure or a skip)",
             cards={g: [perfect] for g in three}, infos=list(three) + ["dd00"], set_size=4),
        dict(id="D4", note="four played; the fourth completed nothing",
             cards={**{g: [perfect] for g in three}, "dd00": [nothing]},
             infos=list(three) + ["dd00"], set_size=4),
        dict(id="D5", note="four opened; the fourth's play never began",
             cards={g: [perfect] for g in three}, infos=list(three) + ["dd00"],
             start_only=("dd00",), set_size=4),
    ]


# --------------------------------------------------------------------------
# 3. Secondary leads
# --------------------------------------------------------------------------

def secondary_probes() -> list[dict]:
    perfect = linear_play([10] * 5)
    half = linear_play([10, 10], win=False)
    return [
        dict(id="S1", note="the scorecard's game id differs from the listing only by version",
             cards={"aa00-v1": [perfect]}, infos=["aa00-v2"], set_size=1,
             baselines={"aa00-v2": B5}),
        dict(id="S2", note="the same game id in both, as a control",
             cards={"aa00-v1": [perfect]}, infos=["aa00-v1"], set_size=1,
             baselines={"aa00-v1": B5}),
        dict(id="S3", note="two plays sharing one guid",
             cards={"aa00": [perfect]}, infos=["aa00"], set_size=1, share_guid=True,
             second=half),
        dict(id="S4", note="two plays with distinct guids, as a control",
             cards={"aa00": [perfect, half]}, infos=["aa00"], set_size=1),
    ]


def run_secondary(p: dict) -> dict:
    if p.get("share_guid"):
        sc = Scorecard(card_id="probe", api_key="")
        guid = "shared"
        start(sc, "aa00", guid); play(sc, "aa00", guid, p["cards"]["aa00"][0])
        start(sc, "aa00", guid); play(sc, "aa00", guid, p["second"])
        infos = [EnvironmentInfo(game_id="aa00", title="AA00", baseline_actions=B5)]
        d = json.loads(EnvironmentScorecard.from_scorecard(sc, infos).model_dump_json())
        card = json.loads(sc.cards["aa00"].model_dump_json())
        return dict(total=round(d["score"], 9),
                    environments={e["id"]: round(e["score"], 9) for e in d["environments"]},
                    total_plays=card["total_plays"], guids=card["guids"],
                    actions=card["actions"], levels_completed=card["levels_completed"])
    return build(p["cards"], p["infos"], p.get("baselines", {}))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "aggregation")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    lines, out = [], {}

    modes = mode_table()
    out["modes"] = modes
    for m in modes:
        lines.append(f"MODE {m['mode']:11s} score_produced_by={m['score_produced_by']}")
        print(lines[-1], flush=True)

    dens = []
    for p in denominator_probes():
        r = build(p["cards"], p["infos"], p.get("baselines", {}), p.get("start_only", ()))
        documented = sum(r["environments"].values()) / p["set_size"]
        row = dict(id=p["id"], note=p["note"], set_size=p["set_size"],
                   environments_in_scorecard=len(r["environments"]),
                   toolkit_total=r["total"], documented_total=round(documented, 9),
                   environment_scores=r["environments"], messages=r["messages"])
        dens.append(row)
        lines.append(f"{p['id']:4s} in_scorecard={row['environments_in_scorecard']} set_size={p['set_size']} "
                     f"toolkit_total={r['total']} documented_total={row['documented_total']} :: {p['note']}")
        print(lines[-1], flush=True)
    out["denominator"] = dens

    sec = []
    for p in secondary_probes():
        r = run_secondary(p)
        row = dict(id=p["id"], note=p["note"], **r)
        sec.append(row)
        lines.append(f"{p['id']:4s} total={r['total']} envs={r['environments']} "
                     f"{'plays=' + str(r.get('total_plays')) + ' actions=' + str(r.get('actions')) if 'total_plays' in r else 'messages=' + str(r.get('messages'))} "
                     f":: {p['note']}")
        print(lines[-1], flush=True)
    out["secondary"] = sec

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1048576 if sys.platform == "darwin" else 1024)
    lines.append(f"SUMMARY modes={len(modes)} denominator_probes={len(dens)} "
                 f"secondary_probes={len(sec)} peak_rss_mb_under_500={peak < 500}")
    (a.out / "aggregation.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    (a.out / "aggregation.log").write_text("\n".join(lines) + "\n")
    print(lines[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
