"""Play each PUBLIC ARC-AGI-3 environment and probe two audit questions that do
NOT need an exhaustive state graph:

  * does RESET restore the state the current level began in, or does something
    leak across it;
  * can one action advance the level counter by two (the scorer edge, F3), or
    make it go backwards without a full reset.

This exists because 19 of the 25 public environments advertise the click action
(x and y each 0..63), so their reachable state graph cannot be enumerated. Play
reaches them; enumeration does not.

This is an audit instrument, not a solver. It plays at random inside each game's
own advertised action set and never tries to win anything.

Reject-only. "No mismatch in N probes" is a sample of a large space, not a proof.

Memory: one game object at a time plus one short-lived copy per probe, so this
is far cheaper than the enumerator, which held a whole search layer.

Scope: the public set only. The semi-private and private sets are out of scope
and are never fetched, probed or inferred.

Usage: play_probe.py [--games ...] [--max-actions N] [--max-seconds S]
                     [--seed 0] [--probe-every K] [--out artifacts/play]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hashlib  # noqa: E402

import numpy as np  # noqa: E402
from arcengine import ActionInput, GameAction, GameState  # noqa: E402
from state_graph import (UNHANDLED, fast_copy, make_game, register_module,  # noqa: E402
                         rss_mb, state_key)

COMPLEX = {6}
GRID_MAX = 63          # ComplexAction declares x, y in 0..63; stay inside that contract
MAX_DIGESTS = 200_000  # cap the coverage set so memory cannot run away


def frame_hash(g) -> bytes:
    """What the AGENT sees: the rendered camera frame. Deliberately separate
    from the engine-state key. A level reset can restore everything an agent can
    observe while leaving internal bookkeeping untouched, and conflating the two
    turns a property of our instrument into a claim about the environment."""
    return hashlib.blake2b(np.asarray(g.camera.render(g.current_level.get_sprites())).tobytes(),
                           digest_size=16).digest()


def status_of(g) -> str:
    if g._state == GameState.GAME_OVER:
        return "GAME_OVER"
    if g._state == GameState.WIN:
        return "WIN"
    return "PLAY"


def probe_environment(game: str, actions: list[int], seed: int, max_actions: int,
                      max_seconds: float, probe_every: int, max_rss_mb: float,
                      environments_dir: Path | None = None) -> dict:
    rng = random.Random(seed)
    full_id, g = make_game(game, 0, environments_dir)
    register_module(g)
    UNHANDLED.clear()
    t0 = time.time()

    # The state each level began in. Recorded when the level is entered, never
    # reconstructed: reconstructing it would be the probe grading its own work.
    level_start: dict[int, bytes] = {0: state_key(g)}
    level_start_frame: dict[int, bytes] = {0: frame_hash(g)}
    seen: set[bytes] = {level_start[0]}

    taken = 0
    resets_issued = 0
    probes = ok_probes = ok_frames = 0
    mismatches: list[dict] = []
    double_advance: list[dict] = []
    level_regressions: list[dict] = []
    wins = game_overs = 0
    max_level = 0
    no_op_actions = 0
    stopped = None

    while taken < max_actions:
        if taken % 64 == 0:
            if time.time() - t0 > max_seconds:
                stopped = "max_seconds"; break
            if rss_mb() > max_rss_mb:
                stopped = "max_rss"; break

        st = status_of(g)
        # A RESET probe is only meaningful where the engine performs a LEVEL
        # reset: with no action taken yet, or after a WIN, `handle_reset`
        # performs a FULL reset instead (arcengine base_game.handle_reset).
        if st == "PLAY" and g._action_count > 0 and taken % probe_every == 0:
            c = fast_copy(g)
            c.perform_action(ActionInput(id=GameAction.RESET), raw=True)
            probes += 1
            expected = level_start.get(g._current_level_index)
            expected_frame = level_start_frame.get(g._current_level_index)
            state_ok = expected is not None and state_key(c) == expected
            frame_ok = expected_frame is not None and frame_hash(c) == expected_frame
            if state_ok:
                ok_probes += 1
            if frame_ok:
                ok_frames += 1
            if not state_ok and len(mismatches) < 20:
                mismatches.append(dict(action_index=taken, level=g._current_level_index,
                                       frame_also_differs=not frame_ok,
                                       full_reset=bool(getattr(c, "_full_reset", False)),
                                       score_before=g._score, score_after=c._score))
            del c

        if st in ("GAME_OVER", "WIN"):
            # The only way forward; after a WIN this is a full reset by design.
            before_level = g._current_level_index
            g.perform_action(ActionInput(id=GameAction.RESET), raw=True)
            resets_issued += 1
            taken += 1
            level_start[g._current_level_index] = state_key(g)
            level_start_frame[g._current_level_index] = frame_hash(g)
            continue

        a = rng.choice(actions)
        data = {}
        if a in COMPLEX:
            data = {"x": rng.randint(0, GRID_MAX), "y": rng.randint(0, GRID_MAX)}
        before_score = g._score
        before_level = g._current_level_index
        before_key = state_key(g)
        g.perform_action(ActionInput(id=GameAction.from_id(a), data=data), raw=True)
        taken += 1
        after_key = state_key(g)
        if after_key == before_key:
            no_op_actions += 1
        if len(seen) < MAX_DIGESTS:
            seen.add(after_key)

        delta = g._score - before_score
        if delta >= 2 and len(double_advance) < 20:
            double_advance.append(dict(action_index=taken, action=a, data=data,
                                       from_levels=before_score, to_levels=g._score))
        if delta < 0 and not getattr(g, "_full_reset", False) and len(level_regressions) < 20:
            level_regressions.append(dict(action_index=taken, action=a,
                                          from_levels=before_score, to_levels=g._score))
        if g._current_level_index != before_level:
            level_start[g._current_level_index] = after_key
            level_start_frame[g._current_level_index] = frame_hash(g)
            max_level = max(max_level, g._current_level_index)
        if status_of(g) == "WIN":
            wins += 1
        elif status_of(g) == "GAME_OVER":
            game_overs += 1

    return dict(
        game=full_id, seed=seed, actions_advertised=actions, complex_actions=sorted(set(actions) & COMPLEX),
        actions_taken=taken, resets_issued=resets_issued, stopped=stopped,
        distinct_states_visited=len(seen), distinct_states_capped=len(seen) >= MAX_DIGESTS,
        levels_entered=sorted(level_start), max_level_index=max_level,
        wins=wins, game_overs=game_overs, no_op_actions=no_op_actions,
        reset_probes=probes, reset_returns_to_level_start=ok_probes,
        reset_frame_returns_to_level_start=ok_frames,
        reset_mismatches=mismatches, double_advance_actions=len(double_advance),
        double_advance_examples=double_advance,
        level_regressions=len(level_regressions), level_regression_examples=level_regressions,
        unhandled_types=sorted(UNHANDLED), peak_rss_mb=round(rss_mb(), 1),
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", nargs="*", default=None)
    ap.add_argument("--max-actions", type=int, default=20_000)
    ap.add_argument("--max-seconds", type=float, default=120)
    ap.add_argument("--max-rss-mb", type=float, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--probe-every", type=int, default=25)
    ap.add_argument("--environments-dir", type=Path, default=ROOT / "environment_files")
    ap.add_argument("--census", type=Path, default=ROOT / "artifacts" / "sweep" / "action_census.json")
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "play")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    census = {r["game"]: r for r in json.loads(a.census.read_text())}
    games = a.games or sorted(census)
    lines = []
    for name in games:
        row = census.get(name)
        if row is None:
            lines.append(f"{name:6s} SKIPPED not in the census"); continue
        try:
            r = probe_environment(name, row["actions"], a.seed, a.max_actions, a.max_seconds,
                                  a.probe_every, a.max_rss_mb, a.environments_dir)
        except Exception as e:  # noqa: BLE001 -- one environment must not end the run
            (a.out / f"{name}.json").write_text(json.dumps(dict(game=row["game_id"], error=str(e)[:300]),
                                                           indent=1, sort_keys=True) + "\n")
            lines.append(f"{name:6s} ERROR {type(e).__name__}: {str(e)[:70]}")
            print(lines[-1], flush=True)
            continue
        (a.out / f"{name}.json").write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
        lines.append(
            f"{name:6s} actions={r['actions_taken']} states={r['distinct_states_visited']} "
            f"levels={len(r['levels_entered'])} wins={r['wins']} game_overs={r['game_overs']} "
            f"reset_state={r['reset_returns_to_level_start']}/{r['reset_probes']} "
            f"reset_frame={r['reset_frame_returns_to_level_start']}/{r['reset_probes']} "
            f"double_advance={r['double_advance_actions']} regressions={r['level_regressions']} "
            f"no_ops={r['no_op_actions']} peak_rss_mb={r['peak_rss_mb']} stopped={r['stopped']}")
        print(lines[-1], flush=True)
    write_summary(a.out, sorted(census))
    (a.out / "play.log").write_text("\n".join(lines) + "\n")
    return 0


def write_summary(out: Path, games: list[str]) -> None:
    rows = []
    for name in games:
        p = out / f"{name}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        if d.get("error"):
            rows.append(dict(game=name, status="error", reason=d["error"])); continue
        rows.append(dict(game=name, status="probed", actions_taken=d["actions_taken"],
                         distinct_states_visited=d["distinct_states_visited"],
                         levels_entered=len(d["levels_entered"]), wins=d["wins"],
                         reset_probes=d["reset_probes"], reset_ok=d["reset_returns_to_level_start"],
                         reset_frame_ok=d.get("reset_frame_returns_to_level_start"),
                         reset_mismatch=d["reset_probes"] != d["reset_returns_to_level_start"],
                         reset_frame_mismatch=d["reset_probes"] != d.get("reset_frame_returns_to_level_start"),
                         double_advance_actions=d["double_advance_actions"],
                         level_regressions=d["level_regressions"],
                         complex_actions=d["complex_actions"], peak_rss_mb=d["peak_rss_mb"]))
    probed = [r for r in rows if r["status"] == "probed"]
    totals = dict(
        environments=len(rows), probed=len(probed),
        with_click=len([r for r in probed if r["complex_actions"]]),
        actions_taken=sum(r["actions_taken"] for r in probed),
        distinct_states_visited=sum(r["distinct_states_visited"] for r in probed),
        reset_probes=sum(r["reset_probes"] for r in probed),
        reset_ok=sum(r["reset_ok"] for r in probed),
        reset_frame_ok=sum(r["reset_frame_ok"] or 0 for r in probed),
        double_advance_actions=sum(r["double_advance_actions"] for r in probed),
        level_regressions=sum(r["level_regressions"] for r in probed),
        peak_rss_mb_max=max((r["peak_rss_mb"] for r in probed), default=None),
    )
    flags = dict(reset_state_mismatch=[r["game"] for r in probed if r["reset_mismatch"]],
                 reset_frame_mismatch=[r["game"] for r in probed if r["reset_frame_mismatch"]],
                 double_advance=[r["game"] for r in probed if r["double_advance_actions"]],
                 level_regressions=[r["game"] for r in probed if r["level_regressions"]],
                 errored=[r["game"] for r in rows if r["status"] == "error"])
    (out / "summary.json").write_text(json.dumps(dict(totals=totals, flags=flags, rows=rows),
                                                 indent=1, sort_keys=True) + "\n")
    (out / "summary.log").write_text(
        f"SUMMARY environments={totals['environments']} probed={totals['probed']} "
        f"with_click={totals['with_click']} reset_state_mismatch={flags['reset_state_mismatch']} "
        f"reset_frame_mismatch={flags['reset_frame_mismatch']} "
        f"double_advance={flags['double_advance']} level_regressions={flags['level_regressions']} "
        f"errored={flags['errored']}\n"
        f"TOTALS actions_taken={totals['actions_taken']} "
        f"distinct_states_visited={totals['distinct_states_visited']} "
        f"reset_probes={totals['reset_probes']} reset_state_ok={totals['reset_ok']} "
        f"reset_frame_ok={totals['reset_frame_ok']} "
        f"double_advance_actions={totals['double_advance_actions']} "
        f"level_regressions={totals['level_regressions']} "
        f"peak_rss_mb_max={totals['peak_rss_mb_max']}\n")
    print(open(out / "summary.log").read().strip())


if __name__ == "__main__":
    raise SystemExit(main())
