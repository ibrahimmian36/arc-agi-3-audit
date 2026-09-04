"""Harness cutoff probes: run the benchmarking harness's REAL main loop
(`benchmarking.base.Agent.main`), REAL `BenchmarkingAgent.is_done`,
`_sync_level_progress`, `_forced_action_for_frame` and `choose_action` against
the toolkit in OFFLINE mode. Only the model call (`_request_with_retries`) is
replaced by a scripted stub, and the agent is constructed the way the harness's
own unit tests construct it (tests/unit/test_benchmarking_agent.py).

Reject-only: reports what the harness executed against the documented budget.

Usage: harness_probe.py --environments-dir DIR --game bt11 [--out artifacts/harness]
Artefacts: <id>.json per probe and harness.log (deterministic; no wall-clock).
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "arc-agi-3-benchmarking"))
sys.path.insert(0, str(ROOT / "scripts"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import FrameData, GameAction, GameState  # noqa: E402
from benchmarking.agent import BenchmarkingAgent  # noqa: E402
from benchmarking.base import ExitReason  # noqa: E402
from benchmarking.runtime_models import ModelResponse, NormalizedUsage  # noqa: E402
from record_trace import canon_guids  # noqa: E402

MULT = 5.0  # every shipped model config sets MAX_ACTIONS_BASELINE_MULTIPLIER: 5.0


def cycle(pattern: list[str], n: int) -> list[str]:
    return pattern * n


def probes() -> list[dict]:
    """Preregistered scripts (docs/PREREGISTRATION.md §1.3), listed AFTER any
    initial RESET; the toolkit wrapper performs the initial RESET inside make()."""
    filler3 = ["ACTION3", "ACTION3", "ACTION3", "RESET"]
    filler4 = ["ACTION4", "ACTION4", "ACTION4", "RESET"]
    solve1 = ["ACTION3"] * 4
    solve2 = ["ACTION3"] * 8
    return [
        dict(id="H1", note="level 1, 20 scripted actions (preregistered as 'one over'; see DECISIONS 2026-09-03)", script=cycle(filler3, 4) + solve1),
        dict(id="H1b", note="level 1, one action over budget (added 2026-09-03 after H1 showed the initial RESET is not counted)", script=cycle(filler3, 5) + solve1),
        dict(id="H2", note="level 1, solving action is the 20th", script=cycle(filler4, 3) + ["ACTION4", "ACTION4", "RESET"] + solve1),
        dict(id="H4", note="level 2, solving action is the 40th of level 2", script=solve1 + cycle(filler4, 8) + solve2),
        dict(id="H5", note="level 2, one action over budget", script=solve1 + cycle(filler4, 8) + ["ACTION4"] + solve2),
        dict(id="H6", note="GAME_OVER then forced RESET then solve", script=["ACTION4"] * 4 + solve1),
    ]


class ScriptedAgent(BenchmarkingAgent):
    """No __init__: attributes are set the way the harness's unit tests set them."""

    def _request_with_retries(self, actions):  # type: ignore[override]
        if not self._script:
            raise RuntimeError("script exhausted")
        name = self._script.pop(0)
        self._executed_from_script.append(name)
        action = GameAction.from_name(name)
        return ModelResponse(output_text=name, usage=NormalizedUsage()), action, 0, []


def make_agent(env, game_id: str, baselines: list[int], script: list[str]) -> ScriptedAgent:
    agent = ScriptedAgent.__new__(ScriptedAgent)
    # -- as in tests/unit/test_benchmarking_agent.py::_agent_for_choose_action --
    agent.conversation = []
    agent._request_kwargs = {"model": "scripted"}
    agent.MAX_CONTEXT_LENGTH = 100_000
    agent.ESTIMATED_CHARS_PER_TOKEN = 1.0
    agent.MAX_RETRIES = 0
    agent.analysis_mode = False
    agent.token_counter = 0
    agent._server_state = False
    agent._previous_response_id = None
    agent._pending_user_messages = []
    agent.MODEL = "scripted"
    agent._pricing = {}
    agent.step_counter = 0
    agent._level_action_counter = 0
    agent._last_levels_completed = 0
    agent._level_just_advanced = False
    agent.action_counter = 0
    agent._previous_action = None
    agent._pending_action_reasoning = {}
    agent.MAX_ANIMATION_FRAMES = 7
    agent._saved_steps = []
    agent._save_step = agent._saved_steps.append
    agent._last_turn_result = None
    agent._continuous_conversation = False
    # -- as in benchmarking.base.Agent.__init__ / BenchmarkingAgent.__init__ --
    agent.game_id = game_id
    agent.exit_reason = ExitReason.UNKNOWN
    agent.arc_env = env
    agent.frames = [FrameData(levels_completed=0)]
    agent._cleanup = False
    agent._timed_out = False
    agent.MAX_RUNTIME_SECONDS = 600
    agent._level_action_budgets = [math.ceil(b * MULT) for b in baselines]
    agent.MAX_ACTIONS = sum(agent._level_action_budgets)
    agent._script = list(script)
    agent._executed_from_script = []
    return agent


def run_probe(environments_dir: Path, game: str, p: dict) -> dict:
    logger = logging.getLogger("arc_agi_3_audit.harness")
    logger.setLevel(logging.ERROR)
    logging.getLogger("benchmarking").setLevel(logging.ERROR)
    logging.getLogger("arc_agi.scorecard").setLevel(logging.ERROR)
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(environments_dir),
                 recordings_dir=str(ROOT / "artifacts" / "recordings"), logger=logger)
    card_id = arc.create_scorecard(tags=["audit-harness"])
    env = arc.make(game, scorecard_id=card_id, save_recording=False)
    if env is None:
        raise SystemExit(f"could not make {game}")
    baselines = list(env.info.baseline_actions or [])
    agent = make_agent(env, env.info.game_id, baselines, p["script"])
    error = None
    try:
        agent.main()
    except RuntimeError as e:  # the probe stub ran out of scripted actions; the harness itself would call the model again
        error = f"{e} (probe stub, not the harness)"
    # What the harness actually executed, per level, from the frames it appended.
    executed = []
    per_level: dict[int, int] = {}
    level_before = 0
    for f in agent.frames[1:]:
        act = f.action_input.id.name if f.action_input else "?"
        executed.append(dict(action=act, state=f.state.name, levels_completed=f.levels_completed))
        per_level[level_before] = per_level.get(level_before, 0) + 1
        level_before = f.levels_completed
    table: dict = {}
    card = canon_guids(json.loads(arc.scorecard_manager.scorecards[card_id].cards[env.info.game_id].model_dump_json()), table)
    scored = arc.get_scorecard(card_id)
    envscore = canon_guids(json.loads(scored.model_dump_json())["environments"][0], table) if scored and scored.environments else None
    budgets = agent._level_action_budgets
    over = {str(l): dict(executed=n, budget=budgets[l], over_budget=n > budgets[l]) for l, n in sorted(per_level.items()) if l < len(budgets)}
    return dict(id=p["id"], note=p["note"], game=env.info.game_id, baselines=baselines, budgets=budgets,
                script=p["script"], script_len=len(p["script"]), executed=executed,
                harness=dict(action_counter=agent.action_counter, level_action_counter=agent._level_action_counter,
                             last_levels_completed=agent._last_levels_completed, exit_reason=agent.exit_reason.name,
                             final_state=agent.frames[-1].state.name, final_levels_completed=agent.frames[-1].levels_completed,
                             script_actions_consumed=len(agent._executed_from_script), error=error),
                per_level_executed=over, any_level_over_budget=any(v["over_budget"] for v in over.values()),
                card=card, environment_score=envscore)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--environments-dir", type=Path, required=True)
    ap.add_argument("--game", default="bt11")
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "harness")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    lines = []
    for p in probes():
        r = run_probe(a.environments_dir, a.game, p)
        (a.out / f"{p['id']}.json").write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
        h = r["harness"]
        lines.append(f"{r['id']:3s} budgets={r['budgets']} executed_per_level={ {k: v['executed'] for k, v in r['per_level_executed'].items()} } "
                     f"harness_actions={h['action_counter']} exit={h['exit_reason']} final_levels={h['final_levels_completed']} "
                     f"card_actions={r['card']['actions']} card_levels={r['card']['levels_completed']} "
                     f"score={(r['environment_score'] or {}).get('score')} over_budget={r['any_level_over_budget']} :: {r['note']}")
    results = [json.loads((a.out / f"{p['id']}.json").read_text()) for p in probes()]
    counts_equal = sum(1 for r in results if r["harness"]["action_counter"] == sum(r["card"]["actions"]))
    lines.append(f"SUMMARY probes={len(results)} any_over_budget={any(r['any_level_over_budget'] for r in results)} "
                 f"counts_equal={counts_equal} budget_exits={sum(1 for r in results if r['harness']['exit_reason'] == 'ACTION_BUDGET')}")
    (a.out / "harness.log").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
