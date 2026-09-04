"""What the client puts on the wire, and what it costs the agent.

An official ARC-AGI-3 run scores server-side, so the audit cannot see the
arithmetic. It can see the CLIENT, and whatever the client sends is what the
server has to count. This records, for a run of the real benchmarking harness
against the toolkit's fixture game, every action that would go on the wire,
tagged by who chose it:

  construction  the RESET the environment wrapper issues when it is built
  forced        a RESET the harness issues on its own after a game over
  chosen        an action the agent actually selected

and reconciles those totals against the harness's own action counter and against
what the local scorecard charges.

Reject-only, and conditional by construction. Every statement is about the
CLIENT. Whether the server charges a given action, and how, is not observable to
us; the local scorer's treatment is reported as the local scorer's.

Scope: the public harness and toolkit at the pinned commits, run OFFLINE against
the toolkit's own fixture game. No network, no API key, no public environment.

Usage: wire_probe.py [--out artifacts/wire]
"""
from __future__ import annotations

import argparse
import json
import logging
import resource
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "arc-agi-3-benchmarking"))
sys.path.insert(0, str(ROOT / "scripts"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402
from benchmarking.base import ExitReason  # noqa: E402
from harness_probe import MULT, make_agent  # noqa: E402

FIXTURE = ROOT / "vendor" / "ARC-AGI" / "test_environment_files"
SOLVE_L1 = ["ACTION3"] * 4          # bt11 level 1 is solved by four ACTION3
LOSE_L1 = ["ACTION4"] * 4           # and lost by four ACTION4


def run(script: list[str], budget_multiplier: float = MULT,
        budgets: list[int] | None = None, runtime_seconds: float | None = None) -> dict:
    """Drive the harness's real loop and record the wire ledger."""
    lg = logging.getLogger("wire"); lg.setLevel(logging.CRITICAL)
    logging.getLogger("benchmarking").setLevel(logging.CRITICAL)
    logging.getLogger("arc_agi.scorecard").setLevel(logging.CRITICAL)
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(FIXTURE),
                 recordings_dir=str(ROOT / "artifacts" / "recordings"), logger=lg)
    card_id = arc.create_scorecard(tags=["audit-wire"])
    env = arc.make("bt11", scorecard_id=card_id, save_recording=False)

    wire: list[dict] = [dict(kind="construction", action="RESET")]
    real_step = env.step

    def counting_step(action, data=None, reasoning=None):
        wire.append(dict(kind="pending", action=action.name))
        return real_step(action, data=data, reasoning=reasoning)
    env.step = counting_step

    agent = make_agent(env, env.info.game_id, list(env.info.baseline_actions or []), script)
    if budgets is not None:
        agent._level_action_budgets = list(budgets)
        agent.MAX_ACTIONS = sum(budgets)
    if runtime_seconds is not None:
        # The wall-clock cutoff is entered by setting the limit, never by
        # waiting: a probe that sleeps spends the machine's time proving that a
        # clock advances.
        agent.MAX_RUNTIME_SECONDS = runtime_seconds

    # Tag each action by who chose it, using the harness's own rule. Wrap
    # _resolve_action, which runs exactly once per action: wrapping
    # _forced_action_for_frame instead miscounts, because the harness evaluates
    # it twice for a chosen action (once in _resolve_action, once again inside
    # choose_action) and once for a forced one.
    real_resolve = agent._resolve_action
    forced_flags: list[bool] = []

    def spy_resolve(frames, latest_frame):
        forced_flags.append(agent._forced_action_for_frame(latest_frame) is not None)
        return real_resolve(frames, latest_frame)
    agent._resolve_action = spy_resolve

    env_calls = {"take_action": 0}
    real_take = agent.take_action

    def counting_take(action):
        env_calls["take_action"] += 1
        return real_take(action)
    agent.take_action = counting_take

    error = None
    try:
        agent.main()
    except RuntimeError as e:
        error = f"{e} (probe stub, not the harness)"

    # The harness calls _forced_action_for_frame once per loop iteration through
    # _resolve_action; choose_action calls it again only on the forced path.
    sent = [w for w in wire if w["kind"] == "pending"]
    for i, w in enumerate(sent):
        w["kind"] = "forced" if (i < len(forced_flags) and forced_flags[i]) else "chosen"
    ledger = [wire[0]] + sent

    card = json.loads(arc.scorecard_manager.scorecards[card_id].cards[env.info.game_id].model_dump_json())
    scored = arc.get_scorecard(card_id)
    envscore = json.loads(scored.model_dump_json())["environments"][0] if scored and scored.environments else None
    counts = dict(on_wire=len(ledger),
                  construction=sum(1 for w in ledger if w["kind"] == "construction"),
                  forced=sum(1 for w in ledger if w["kind"] == "forced"),
                  chosen=sum(1 for w in ledger if w["kind"] == "chosen"))
    return dict(budgets=agent._level_action_budgets, counts=counts,
                runtime_seconds=agent.MAX_RUNTIME_SECONDS,
                harness_action_counter=agent.action_counter,
                take_action_calls=env_calls["take_action"],
                card_actions=card["actions"], card_resets=card["resets"],
                card_levels_completed=card["levels_completed"],
                exit_reason=agent.exit_reason.name, error=error,
                environment_score=(round(envscore["score"], 9) if envscore else None),
                level_actions=(envscore["runs"][0].get("level_actions") if envscore else None),
                ledger_tail=[w["kind"] for w in ledger][:40])


def probes() -> list[dict]:
    return [
        dict(id="W1", note="never lost: solve level 1 cleanly", script=SOLVE_L1),
        dict(id="W2", note="lost once, then solve level 1", script=LOSE_L1 + SOLVE_L1),
        dict(id="W3", note="lost three times, then solve level 1",
             script=LOSE_L1 * 3 + SOLVE_L1),
        dict(id="W4", note="a per-level budget of one action", script=SOLVE_L1, budgets=[1, 40, 80, 100, 120]),
        dict(id="W5", note="a budget small enough that forced resets alone can exhaust it",
             script=LOSE_L1 * 3 + SOLVE_L1, budgets=[6, 40, 80, 100, 120]),
        dict(id="W6", note="the level advances on the last action the budget permits",
             script=SOLVE_L1, budgets=[4, 40, 80, 100, 120]),
        dict(id="W7", note="a game over on the last action the budget permits",
             script=LOSE_L1 + SOLVE_L1, budgets=[4, 40, 80, 100, 120]),
    ]


def retry_isolation() -> dict:
    """Does a retried model call reach the environment more than once?

    Measured two ways rather than reasoned about: the harness's own retry loop
    contains no call that reaches the environment, and across every probe the
    number of environment calls equals the number of actions the harness counted.
    """
    src = (ROOT / "vendor" / "arc-agi-3-benchmarking" / "benchmarking" / "agent.py").read_text()
    body = src[src.index("def _request_with_retries"):]
    body = body[:body.index("\n    def ", 10)]
    reaches_env = [t for t in ("take_action", "do_action_request", "arc_env", "self.env")
                   if t in body]
    return dict(retry_body_lines=len(body.splitlines()),
                calls_reaching_the_environment=reaches_env,
                isolated=not reaches_env)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "wire")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    rows, lines = [], []
    for p in probes():
        r = run(p["script"], budgets=p.get("budgets"))
        rows.append(dict(id=p["id"], note=p["note"], **r))
        c = r["counts"]
        lines.append(f"{p['id']:3s} on_wire={c['on_wire']} construction={c['construction']} "
                     f"forced={c['forced']} chosen={c['chosen']} "
                     f"harness_counter={r['harness_action_counter']} card_actions={r['card_actions']} "
                     f"card_resets={r['card_resets']} level_actions={r['level_actions']} "
                     f"score={r['environment_score']} exit={r['exit_reason']} :: {p['note']}")
        print(lines[-1], flush=True)
    iso = retry_isolation()
    lines.append(f"RETRY isolated={iso['isolated']} "
                 f"calls_reaching_the_environment={iso['calls_reaching_the_environment']}")
    print(lines[-1], flush=True)
    consistent = all(r["take_action_calls"] == r["harness_action_counter"] for r in rows)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1048576 if sys.platform == "darwin" else 1024)
    lines.append(f"SUMMARY probes={len(rows)} one_environment_call_per_counted_action={consistent} "
                 f"peak_rss_mb_under_500={peak < 500}")
    (a.out / "wire.json").write_text(json.dumps(dict(probes=rows, retry=iso), indent=1, sort_keys=True) + "\n")
    (a.out / "wire.log").write_text("\n".join(lines) + "\n")
    print(lines[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
