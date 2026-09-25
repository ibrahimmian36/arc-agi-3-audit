"""What a RESET at the start of a level costs an agent under the shipped
harness, and what it cost the humans who set the baselines.

The engine zeroes its per-level action counter on every set_level, and its
handle_reset makes a RESET at counter zero a FULL reset (back to level 1)
unless ONLY_RESET_LEVELS=true. The human recordings replay only under that
switch (scripts/replay_check.py), so the humans' RESETs never left the level.
This probe drives the REAL harness main loop (as harness_probe.py does) with a
scripted agent on ls20: the 13-action level-1 witness, one RESET as the first
action of level 2, then play on. Under each engine setting it reports what the
engine did, what the harness counted, and what the scorecard recorded.

Usage: full_reset_probe.py [--out artifacts/replays/full_reset_probe.json]
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "arc-agi-3-benchmarking"))
sys.path.insert(0, str(ROOT / "scripts"))
from arc_agi import Arcade, OperationMode  # noqa: E402
from harness_probe import make_agent  # noqa: E402

ENVDIR = ROOT / "environment_files"
SWITCH = "ONLY_RESET_LEVELS"
NAME = {0: "RESET", **{i: f"ACTION{i}" for i in range(1, 8)}}


def witness(level: int) -> list[int]:
    return json.load(open(ROOT / "artifacts" / "minactions" / f"ls20_L{level}.json"))["witness"]


def run(script: list[int], level_only: bool) -> dict:
    if level_only:
        os.environ[SWITCH] = "true"
    else:
        os.environ.pop(SWITCH, None)
    try:
        lg = logging.getLogger("frp"); lg.setLevel(logging.CRITICAL)
        for name in ("benchmarking", "arc_agi.scorecard"):
            logging.getLogger(name).setLevel(logging.CRITICAL)
        arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(ENVDIR), logger=lg)
        card_id = arc.create_scorecard(tags=["audit-fullreset"])
        env = arc.make("ls20", scorecard_id=card_id, save_recording=False)
        if level_only:
            # Under the switch the construction RESET is not flagged full, so
            # the local card never opens a play; the toolkit's API server
            # forces one (api.py, `level_reset_only`), and so do we.
            arc.scorecard_manager.add_game(card_id, env._guid)
            arc.scorecard_manager.update_scorecard(env._guid, env.observation_space, True)
        agent = make_agent(env, env.info.game_id, list(env.info.baseline_actions or []), [NAME[a] for a in script])
        seen = []
        counter_after = {"v": None}
        real_do = agent.do_action_request

        def spy_do(action):
            fr = real_do(action)
            # the counter as it stands after this action; the harness bumps
            # it again before the next model call, which the exhausted stub
            # never answers
            counter_after["v"] = agent._level_action_counter
            return fr
        agent.do_action_request = spy_do
        real_sync = agent._sync_level_progress

        def spy_sync(frame):
            real_sync(frame)
            seen.append((frame.levels_completed, bool(frame.full_reset), agent._level_action_counter))
        agent._sync_level_progress = spy_sync
        error = None
        try:
            agent.main()
        except RuntimeError as e:
            error = str(e)
        card = json.loads(arc.scorecard_manager.scorecards[card_id].cards[env.info.game_id].model_dump_json())
        scored = arc.get_scorecard(card_id)
        envscore = json.loads(scored.model_dump_json())["environments"][0] if scored and scored.environments else None
        # full-reset frames after the construction one
        full_resets = sum(1 for _, fr, _ in seen[1:] if fr)
        return dict(level_only=level_only, script_len=len(script), executed=len(agent._executed_from_script),
                    full_resets_seen=full_resets, levels_completed_final=seen[-1][0] if seen else None,
                    max_levels_seen=max((l for l, _, _ in seen), default=None),
                    harness_counter_final=counter_after["v"],
                    harness_last_levels=agent._last_levels_completed,
                    budgets=list(agent._level_action_budgets),
                    exit_reason=agent.exit_reason.name if agent.exit_reason else None,
                    card_plays=card["total_plays"], card_actions=card["actions"], card_resets=card["resets"],
                    card_levels=card["levels_completed"],
                    environment_score=(round(envscore["score"], 6) if envscore else None),
                    error=error)
    finally:
        os.environ.pop(SWITCH, None)


def main(argv) -> int:
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else ROOT / "artifacts" / "replays" / "full_reset_probe.json"
    w1, w2 = witness(1), witness(2)
    # A: witness 1, RESET at the start of level 2, then witness 2. Under the
    #    switch the RESET is a no-op level reset and witness 2 wins level 2.
    #    Under the default the RESET is a full reset and witness 2 is played
    #    on level 1, where it does not win.
    # B: the same, but after the RESET the agent re-clears level 1 and then
    #    plays witness 2: what the default costs an agent that recovers.
    # B is meaningful only under the default: under the switch the RESET is a
    # no-op and the re-clear moves are played on level 2, which is a different
    # script, not a comparison.
    result = {
        "A_reset_then_continue": dict(default=run(w1 + [0] + w2, False), level_only=run(w1 + [0] + w2, True)),
        "B_reset_reclear_continue": dict(default=run(w1 + [0] + w1 + w2, False)),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1))
    lines = []
    for name, r in result.items():
        for setting, d in r.items():
            lines.append(f"FULLRESET {name} {setting} card_plays={d['card_plays']} "
                         f"card_levels={d['card_levels']} card_actions={d['card_actions']} levels_final={d['levels_completed_final']} "
                         f"harness_counter={d['harness_counter_final']} harness_last_levels={d['harness_last_levels']} "
                         f"exit={d['exit_reason']} score={d['environment_score']}")
    out.with_suffix(".log").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
