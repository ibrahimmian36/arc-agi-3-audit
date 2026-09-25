"""Replay every human recording through the shipped environment code.

For each recording the environment is constructed from environment_files/
exactly as the toolkit constructs it, the recorded actions are applied in
order with their recorded click coordinates, and after every action the
rendered frame, the state and the level count are compared with what the
recording holds.

Two engine settings are tried. The shipped default: a RESET is a full reset
(back to level 1) whenever the engine's per-level action counter is zero,
which it is at the start of every level and immediately after a level reset.
And ONLY_RESET_LEVELS=true, the engine's own switch under which a RESET never
leaves the level except after a win. A recording is classed

  full_default    reproduces frame for frame under the default;
  full_levelonly  reproduces frame for frame only under the switch;
  frame_only      state and level agree at every step under the switch, and
                  some frames differ (decoration: animation, random pixels);
  divergent       state or level disagree at some step even under the switch.

Trap events are counted under the switch, where they are what the human
actually did: a RESET issued while the counter is zero and the game is not
won, split into `double_reset` (the previous action was also a RESET) and
`reset_at_level_start` (the level had just been reached). Under the default
each such RESET would have sent the player back to level 1.

Nothing from the archive is written: per-environment class counts, event
counts, and first-divergence positions.

Usage: replay_check.py ARCHIVE.zip [--games ls20 tu93] [--limit N]
                       [--out artifacts/replays/replay_check.json]
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import resource
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "vendor" / "ARC-AGI"))
from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402
from replays import action_id, RESET  # noqa: E402

ENVDIR = ROOT / "environment_files"
MEMBER = re.compile(r"^public_games-dataset/([a-z0-9]+)/[0-9a-f-]+\.recording\.jsonl$")
SWITCH = "ONLY_RESET_LEVELS"


def peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


def make_env(game: str):
    lg = logging.getLogger("rc"); lg.setLevel(logging.ERROR)
    logging.getLogger("arc_agi.scorecard").setLevel(logging.ERROR)
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(ENVDIR), logger=lg)
    env = arc.make(game, save_recording=False)
    if env is None:
        raise SystemExit(f"could not make {game}")
    return env


def frame_of(fd) -> list:
    return [[list(row) for row in grid] for grid in fd.frame]


def steps(f):
    """Yield (n, record) for every frame line, the trailing card dropped."""
    for n, raw in enumerate(io.TextIOWrapper(f, encoding="utf-8"), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)["data"]
        except (json.JSONDecodeError, KeyError):
            continue
        if "action_input" in d:
            yield n, d


def apply(env, d: dict):
    a = action_id(d["action_input"]["id"])
    data = {k: v for k, v in (d["action_input"].get("data") or {}).items() if k in ("x", "y")}
    if a == RESET:
        return env.reset()
    return env.step(GameAction.from_id(a), data=data or None)


def replay_one(env_name: str, f, level_only: bool) -> dict:
    if level_only:
        os.environ[SWITCH] = "true"
    else:
        os.environ.pop(SWITCH, None)
    try:
        env = make_env(env_name)
        g = env._game
        n = frames_ok = state_ok = 0
        first_frame_bad = first_state_bad = None
        double = at_start = beyond = 0
        prev_reset = False
        for line, d in steps(f):
            a = action_id(d["action_input"]["id"])
            if a == RESET and n > 0 and g._action_count == 0 and g._state != GameState.WIN:
                if prev_reset:
                    double += 1
                else:
                    at_start += 1
                # on level 1 a full reset and a level reset coincide; beyond
                # it the default would discard the completed levels
                if g._score > 0:
                    beyond += 1
            fd = apply(env, d)
            n += 1
            prev_reset = (a == RESET)
            if fd is None:
                first_state_bad = first_state_bad or line
                continue
            st = fd.state.name == d["state"] and fd.levels_completed == d["levels_completed"]
            fr = st and frame_of(fd) == d["frame"]
            state_ok += st
            frames_ok += fr
            if not st and first_state_bad is None:
                first_state_bad = line
            if not fr and first_frame_bad is None:
                first_frame_bad = line
        return dict(steps=n, frames_ok=frames_ok, state_ok=state_ok, first_frame_bad=first_frame_bad,
                    first_state_bad=first_state_bad, double_reset=double, reset_at_level_start=at_start,
                    trap_beyond_level1=beyond)
    finally:
        os.environ.pop(SWITCH, None)


def classify(default: dict, levelonly: dict | None) -> str:
    if default["frames_ok"] == default["steps"] > 0:
        return "full_default"
    assert levelonly is not None
    if levelonly["frames_ok"] == levelonly["steps"] > 0:
        return "full_levelonly"
    if levelonly["state_ok"] == levelonly["steps"] > 0:
        return "frame_only"
    return "divergent"


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    archive = Path(argv[1])
    games = None
    if "--games" in argv:
        games = []
        for a in argv[argv.index("--games") + 1:]:
            if a.startswith("--"):
                break
            games.append(a)
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else ROOT / "artifacts" / "replays" / "replay_check.json"
    classes = ("full_default", "full_levelonly", "frame_only", "divergent")
    per = defaultdict(lambda: dict(recordings=0, old_schema=0, **{c: 0 for c in classes},
                                   double_reset=0, reset_at_level_start=0, plays_with_trap=0,
                                   trap_beyond_level1=0, plays_with_trap_beyond_level1=0,
                                   frames_differing=0, steps=0, first_state_divergences=[],
                                   state_default=0, state_levelonly=0))
    t0 = time.time()
    with zipfile.ZipFile(archive) as z:
        members = sorted((i for i in z.infolist() if MEMBER.match(i.filename)), key=lambda i: i.filename)
        if games:
            members = [i for i in members if MEMBER.match(i.filename).group(1) in games]
        if limit:
            members = members[:limit]
        for k, info in enumerate(members):
            env_name = MEMBER.match(info.filename).group(1)
            p = per[env_name]
            p["recordings"] += 1
            with z.open(info) as f:
                first = next(steps(f), None)
            p["old_schema"] += bool(first) and isinstance(first[1]["action_input"]["id"], str)
            with z.open(info) as f:
                lo = replay_one(env_name, f, level_only=True)
            with z.open(info) as f:
                de = replay_one(env_name, f, level_only=False)
            cls = classify(de, lo)
            p[cls] += 1
            # state and level (not frames) at every step, per engine setting
            p["state_default"] += (de["state_ok"] == de["steps"] > 0)
            p["state_levelonly"] += (lo["state_ok"] == lo["steps"] > 0)
            p["steps"] += lo["steps"]
            p["double_reset"] += lo["double_reset"]
            p["reset_at_level_start"] += lo["reset_at_level_start"]
            p["plays_with_trap"] += (lo["double_reset"] + lo["reset_at_level_start"] > 0)
            p["trap_beyond_level1"] += lo["trap_beyond_level1"]
            p["plays_with_trap_beyond_level1"] += (lo["trap_beyond_level1"] > 0)
            p["frames_differing"] += lo["steps"] - lo["frames_ok"]
            if cls == "divergent":
                p["first_state_divergences"].append(dict(step=lo["first_state_bad"], of=lo["steps"]))
            print(f"  {k+1}/{len(members)} {env_name} {cls} steps={lo['steps']} frames_ok={lo['frames_ok']} "
                  f"traps={lo['double_reset']}+{lo['reset_at_level_start']} {time.time()-t0:.0f}s rss={peak_rss_mb():.0f}MB",
                  file=sys.stderr)
    tot = {c: sum(p[c] for p in per.values()) for c in classes}
    tot.update(recordings=sum(p["recordings"] for p in per.values()),
               steps=sum(p["steps"] for p in per.values()),
               double_reset=sum(p["double_reset"] for p in per.values()),
               reset_at_level_start=sum(p["reset_at_level_start"] for p in per.values()),
               plays_with_trap=sum(p["plays_with_trap"] for p in per.values()),
               trap_beyond_level1=sum(p["trap_beyond_level1"] for p in per.values()),
               plays_with_trap_beyond_level1=sum(p["plays_with_trap_beyond_level1"] for p in per.values()),
               frames_differing=sum(p["frames_differing"] for p in per.values()),
               state_faithful=sum(p["full_default"] + p["full_levelonly"] + p["frame_only"] for p in per.values()),
               state_default=sum(p["state_default"] for p in per.values()),
               state_levelonly=sum(p["state_levelonly"] for p in per.values()))
    result = dict(archive=archive.name, switch=SWITCH, environments=dict(sorted(per.items())), totals=tot,
                  seconds=round(time.time() - t0, 1), peak_rss_mb=round(peak_rss_mb(), 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1))
    trap_envs = ",".join(e for e, p in sorted(per.items()) if p["plays_with_trap"])
    log = [
        f"REPLAY recordings={tot['recordings']} steps={tot['steps']} full_default={tot['full_default']} "
        f"full_levelonly={tot['full_levelonly']} frame_only={tot['frame_only']} divergent={tot['divergent']} "
        f"state_faithful={tot['state_faithful']}",
        f"REPLAY state_and_level_default={tot['state_default']} state_and_level_levelonly={tot['state_levelonly']} "
        f"state_and_level_only_under_switch={tot['state_levelonly'] - tot['state_default']}",
        f"REPLAY frames_differing={tot['frames_differing']} frame_only_envs="
        f"{','.join(e for e, p in sorted(per.items()) if p['frame_only'])}",
        f"REPLAY plays_with_trap={tot['plays_with_trap']} double_reset={tot['double_reset']} "
        f"reset_at_level_start={tot['reset_at_level_start']} trap_beyond_level1={tot['trap_beyond_level1']} "
        f"plays_with_trap_beyond_level1={tot['plays_with_trap_beyond_level1']} trap_envs={trap_envs}",
    ]  # timing stays in the JSON so the log is byte-identical across runs
    out.with_suffix(".log").write_text("\n".join(log) + "\n")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
