"""Run-level policies on the official client: the limits that decide when a run
stops, what the client does when a request fails, and what the agent is shown.

An official ARC-AGI-3 run is scored by a server this audit cannot see, so the
client is the only observable half. Phase 7 covered accounting inside a run.
This covers the policy layer around it:

  limits   every shipped model configuration's action multiplier, runtime limit,
           context limit and animation-frame cap
  timeout  what a wall-clock cutoff does to a partly finished run
  resend   whether one intended action can reach the server twice
  frames   how many frames an action produces against how many the agent sees

Reject-only, and conditional by construction. Every statement is about the
CLIENT; the server's treatment of anything is not observable and is not claimed.

Scope: the public harness and toolkit at the pinned commits, run OFFLINE against
the toolkit's own fixture game. No socket is ever opened: the remote wrapper is
driven with a transport that records each attempt and raises.

Usage: limits_probe.py [--out artifacts/limits]
"""
from __future__ import annotations

import argparse
import json
import logging
import resource
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "arc-agi-3-benchmarking"))
sys.path.insert(0, str(ROOT / "scripts"))

import requests  # noqa: E402  (only its exception types are used)
from arc_agi.models import EnvironmentInfo  # noqa: E402
from arc_agi.remote_wrapper import RemoteEnvironmentWrapper  # noqa: E402
from arcengine import GameAction  # noqa: E402
from benchmarking.base import Agent  # noqa: E402
from wire_probe import SOLVE_L1, run as wire_run  # noqa: E402

CONFIGS = ROOT / "vendor" / "arc-agi-3-benchmarking" / "benchmarking" / "model_configs.yaml"


# --------------------------------------------------------------------------
# A. What every shipped configuration sets
# --------------------------------------------------------------------------

def limits_table() -> dict:
    entries = yaml.safe_load(CONFIGS.read_text())
    rows = []
    for e in entries:
        a = (e or {}).get("agent") or {}
        rows.append(dict(id=e.get("id"),
                         action_multiplier=a.get("MAX_ACTIONS_BASELINE_MULTIPLIER"),
                         runtime_seconds=a.get("MAX_RUNTIME_SECONDS"),
                         context_length=a.get("MAX_CONTEXT_LENGTH"),
                         animation_frames=a.get("MAX_ANIMATION_FRAMES")))
    defaults = dict(action_multiplier=None, runtime_seconds=Agent.MAX_RUNTIME_SECONDS,
                    animation_frames=None)
    distinct = {k: sorted({str(r[k]) for r in rows})
                for k in ("action_multiplier", "runtime_seconds", "context_length", "animation_frames")}
    return dict(configs=len(rows), rows=rows, base_runtime_seconds=Agent.MAX_RUNTIME_SECONDS,
                distinct_values=distinct,
                uniform={k: len(v) == 1 for k, v in distinct.items()})


# --------------------------------------------------------------------------
# B. The timeout, entered by construction rather than by waiting
# --------------------------------------------------------------------------

def timeout_probes() -> list[dict]:
    out = []
    for label, limit in (("zero", 0.0), ("negative", -1.0), ("ample", 3600.0)):
        r = wire_run(SOLVE_L1)
        # Re-run with the limit applied by patching the agent before main().
        r2 = wire_run(SOLVE_L1, runtime_seconds=limit)
        out.append(dict(id=f"T-{label}", runtime_seconds=limit,
                        exit_reason=r2["exit_reason"], actions=r2["harness_action_counter"],
                        score=r2["environment_score"],
                        unlimited_exit=r["exit_reason"], unlimited_actions=r["harness_action_counter"]))
    return out


# --------------------------------------------------------------------------
# C. Does one intended action reach the server twice?
# --------------------------------------------------------------------------

class RecordingTransport:
    """A session that records every attempt and never opens a socket."""

    def __init__(self, mode: str):
        self.mode = mode
        self.attempts: list[str] = []
        self.cookies = requests.cookies.RequestsCookieJar()

    def post(self, url, **kw):
        self.attempts.append(url.rsplit("/", 1)[-1])
        if self.mode == "connection_error":
            raise requests.exceptions.ConnectionError("connection refused")
        if self.mode == "timeout_after_send":
            raise requests.exceptions.ReadTimeout("response lost after the request was sent")
        if self.mode == "server_error":
            resp = requests.Response(); resp.status_code = 500; resp._content = b"boom"
            resp.raise_for_status()
        if self.mode == "empty_ok":
            resp = requests.Response(); resp.status_code = 200; resp._content = b"{}"
            return resp
        raise AssertionError(self.mode)

    def get(self, url, **kw):
        return self.post(url, **kw)


def resend_probes() -> list[dict]:
    """One intended action per probe. The count of attempts is what matters:
    more than one would mean the client can have the server count an action
    twice for a single intent."""
    rows = []
    for mode in ("connection_error", "timeout_after_send", "server_error", "empty_ok"):
        lg = logging.getLogger("limits"); lg.setLevel(logging.CRITICAL)
        info = EnvironmentInfo(game_id="probe-0000", title="PROBE", baseline_actions=[10])
        w = RemoteEnvironmentWrapper.__new__(RemoteEnvironmentWrapper)
        # Construct without the constructor's own RESET, which would add an
        # attempt that has nothing to do with the question.
        w.base_url = "https://example.invalid"
        w.environment_info = info
        w.arc_api_key = "probe-key"
        w.logger = lg
        w.scorecard_id = "probe"
        w.save_recording = False
        w.include_frame_data = False
        w.recordings_dir = str(ROOT / "artifacts" / "recordings")
        w.scorecard_manager = None
        w.renderer = None
        w._last_response = None
        w._guid = "probe-guid"
        w._recording_filename = None
        w._steps = 0
        import threading
        w._cookie_lock = threading.Lock()
        w._master_cookie_jar = requests.cookies.RequestsCookieJar()
        t = RecordingTransport(mode)
        w._session = t
        result = w.step(GameAction.ACTION1)
        rows.append(dict(mode=mode, attempts=len(t.attempts), endpoints=t.attempts,
                         returned_none=result is None))
    return rows


# --------------------------------------------------------------------------
# D. Frames produced against frames shown
# --------------------------------------------------------------------------

def frame_probes() -> list[dict]:
    from benchmarking.agent import BenchmarkingAgent
    agent = BenchmarkingAgent.__new__(BenchmarkingAgent)
    rows = []
    for produced in (1, 3, 7, 8, 20):
        for cap in (1, 7):
            agent.MAX_ANIMATION_FRAMES = cap
            grids = [[[i]] for i in range(produced)]
            shown = agent.interpolate_frames(grids)
            rows.append(dict(produced=produced, cap=cap, shown=len(shown),
                             keeps_last=shown[-1] == grids[-1],
                             keeps_first=shown[0] == grids[0]))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "limits")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    lines = []

    lim = limits_table()
    lines.append(f"LIMITS configs={lim['configs']} base_runtime_seconds={lim['base_runtime_seconds']} "
                 f"runtime_overrides={lim['distinct_values']['runtime_seconds']} "
                 f"animation_overrides={lim['distinct_values']['animation_frames']} "
                 f"multiplier_values={lim['distinct_values']['action_multiplier']} "
                 f"uniform_multiplier={lim['uniform']['action_multiplier']}")
    print(lines[-1], flush=True)

    tos = timeout_probes()
    for t in tos:
        lines.append(f"{t['id']:12s} runtime_seconds={t['runtime_seconds']} exit={t['exit_reason']} "
                     f"actions={t['actions']} score={t['score']}")
        print(lines[-1], flush=True)

    res = resend_probes()
    for r in res:
        lines.append(f"RESEND {r['mode']:20s} attempts={r['attempts']} returned_none={r['returned_none']}")
        print(lines[-1], flush=True)

    fr = frame_probes()
    worst = max(fr, key=lambda r: r["produced"] - r["shown"])
    lines.append(f"FRAMES max_dropped={worst['produced'] - worst['shown']} "
                 f"(produced={worst['produced']} cap={worst['cap']} shown={worst['shown']}) "
                 f"always_keeps_last={all(r['keeps_last'] for r in fr)}")
    print(lines[-1], flush=True)

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1048576 if sys.platform == "darwin" else 1024)
    resend_max = max(r["attempts"] for r in res)
    lines.append(f"SUMMARY max_attempts_per_intended_action={resend_max} "
                 f"peak_rss_mb_under_500={peak < 500}")
    print(lines[-1], flush=True)
    (a.out / "limits.json").write_text(json.dumps(dict(limits=lim, timeouts=tos, resend=res, frames=fr),
                                                  indent=1, sort_keys=True) + "\n")
    (a.out / "limits.log").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
