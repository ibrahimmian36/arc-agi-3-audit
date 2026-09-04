"""Verify every load-bearing figure in the paper against the artefact that
produced it.

The audit kit's report checker matches a literal string in both the report and
the log. That works for an internal findings file, which quotes artefact syntax
verbatim, but a paper states numbers in prose. So each entry here carries three
things: the phrase as it appears in the paper, the value that phrase asserts,
and a regular expression that extracts the same value from the log. A claim
passes only when the phrase is present in the paper AND the log yields exactly
the value the phrase asserts.

Reading the numbers by eye is not a check. Exit 0 iff every claim verifies.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE.parent / "artifacts"

# (phrase as printed in the paper, value it asserts, log file, regex capturing it)
CLAIMS: list[tuple[str, str, Path, str]] = [
    # --- resets the agent did not choose: the denial and its size ---
    ("the environment scoring 0.0", "0.0",
     ART / "budget/budget.log", r"^B8\s+shipped: [^|]*score=([0-9.]+)"),
    ("completes the level and scores 1.316872428", "1.316872428",
     ART / "budget/budget.log", r"^B8.*counterfactual: [^|]*score=([0-9.]+)"),
    ("[8] for one death", "[8]", ART / "budget/budget.log",
     r"^WINDOW deaths=1 .*denial_budgets=(\[[^\]]*\])"),
    ("[12, 13] for two", "[12, 13]", ART / "budget/budget.log",
     r"^WINDOW deaths=2 .*denial_budgets=(\[[^\]]*\])"),
    ("[16, 17, 18] for three", "[16, 17, 18]", ART / "budget/budget.log",
     r"^WINDOW deaths=3 .*denial_budgets=(\[[^\]]*\])"),
    ("median of 3.251814028 points", "3.251814028",
     ART / "budget/budget.log", r"^TAX .*median_fall=([0-9.]+)"),
    ("183 levels of the 25 public", "183", ART / "budget/budget.log",
     r"^TAX levels=(\d+)"),
    ("183 levels of the 25 public", "25", ART / "budget/budget.log",
     r"^TAX levels=\d+ environments=(\d+)"),
    ("to 73.469387755", "73.469387755", ART / "budget/budget.log",
     r"^TAX .*after_one=([0-9.]+)"),

    # --- the scoring rule ---
    ("environment score of 49.333333", "49.333333", ART / "scorer/probes.log",
     r"^P2c .*prose_nocut=([0-9.]+)"),
    ("equation reading returns 50.483333", "50.483333", ART / "scorer/probes.log",
     r"^P2c .*eq_nocut=([0-9.]+)"),
    ("scores 115.0 in the shipped code", "115.0", ART / "scorer/probes.log",
     r"^P2a .*levels=\[([0-9.]+),"),
    ("is scored 93.589645 by the shipped scorer", "93.589645", ART / "scorer/probes.log",
     r"^P3b .*prose_nocut=([0-9.]+)"),
    ("gives 0.000000", "0.000000", ART / "scorer/probes.log",
     r"^P3b .*prose_cut=([0-9.]+)"),
    ("returns 66.666667", "66.666667", ART / "scorer/probes.log",
     r"^P8 .*shipped=([0-9.]+)"),
    ("documented rule gives 100.000000", "100.000000", ART / "scorer/probes.log",
     r"^P8 .*prose_nocut=([0-9.]+)"),
    ("discharges 50 proof obligations", "50", ART / "oracle/check_scoring.log",
     r"verified=(\d+) errors=0"),
    ("agrees with our verified model of the prose rule on 12", "12",
     ART / "scorer/probes.log", r"agree_primary=(\d+)"),
    ("On 14 preregistered planted traces", "14", ART / "scorer/probes.log", r"probes=(\d+)"),
    ("disagreeing on one", "1", ART / "scorer/probes.log", r"disagreements_primary=(\d+)"),
    # --- the harness ---
    ("Across six scripted runs", "6", ART / "harness/harness.log", r"probes=(\d+)"),
    ("two runs exited on the budget", "2", ART / "harness/harness.log", r"budget_exits=(\d+)"),
    # --- ls20 models ---
    ("14337", "14337", ART / "env/ls20/graph_L1.json", r'"states": (\d+)'),
    ("56772", "56772", ART / "env/ls20/graph_L1.json", r'"edges": (\d+)'),
    ("34739", "34739", ART / "env/ls20/graph_L2.json", r'"states": (\d+)'),
    ("133788", "133788", ART / "env/ls20/graph_L2.json", r'"edges": (\d+)'),
    ("13 & 45", "13", ART / "env/ls20/graph_L1.json", r'"shortest_win_depth": (\d+)'),
    ("13 & 45", "45", ART / "env/ls20/graph_L2.json", r'"shortest_win_depth": (\d+)'),
    ("17 & 26", "17", ART / "oracle_env/check_ls20_level1.log", r"verified=(\d+) errors=0"),
    ("17 & 26", "26", ART / "oracle_env/check_ls20_level2.log", r"verified=(\d+) errors=0"),
    ("3208", "3208", ART / "env/ls20/env_L1.log", r"steps=(\d+)"),
    ("1903", "1903", ART / "env/ls20/env_L2.log", r"steps=(\d+)"),
    ("500/500 & 500/500", "500", ART / "env/ls20/graph_L1.json", r'"reset_returns_to_start": (\d+)'),
    ("0.002813847150161035", "0.002813847150161035", ART / "env/ls20/graph_L1.json",
     r'"p_win_random_policy": ([0-9.]+)'),
    ("355.38533070027296", "355.38533070027296", ART / "env/ls20/graph_L1.json",
     r'"inverse_p_win_random": ([0-9.]+)'),
    ("4732/4731/4731", "4732", ART / "env/ls20/granularity.log", r"^L1 .*rule_by_lives=\{'3': (\d+)"),
    ("7400/7399/7399", "7400", ART / "env/ls20/granularity.log", r"^L2 .*rule_by_lives=\{'3': (\d+)"),
    ("7400/13024/13024", "13024", ART / "env/ls20/granularity.log",
     r"^L2 key_by_lives=\{[^}]*'1': (\d+)"),
    # --- breadth sweep ---
    ("Nineteen of the 25", "19", ART / "sweep/summary_L1.log", r"skipped_click=(\d+)"),
    ("The remaining six", "6", ART / "sweep/summary_L1.log", r"enumerable=(\d+)"),
    ("2609", "2609", ART / "sweep/tu93_L1.json", r'"states": (\d+)'),
    ("150000", "150000", ART / "sweep/tr87_L1.json", r'"states": (\d+)'),
    ("616946", "616946", ART / "sweep/summary_L1.log", r"states_examined=(\d+)"),
    ("1245427", "1245427", ART / "sweep/summary_L1.log", r"transitions_examined=(\d+)"),
    ("all\n3000 probes", "3000", ART / "sweep/summary_L1.log", r"reset_probes=(\d+)"),
    # --- play probe ---
    ("18663", "18663", ART / "play/summary.log", r"reset_probes=(\d+)"),
    ("15440", "15440", ART / "play/summary.log", r"reset_state_ok=(\d+)"),
    ("479040", "479040", ART / "play/summary.log", r"actions_taken=(\d+)"),
    # --- baselines ---
    ("Of 18 levels attempted", "18", ART / "minactions/summary.log", r"levels_checked=(\d+)"),
    ("six resolved and all six are consistent", "6", ART / "minactions/summary.log", r"consistent=(\d+)"),
    ("none is impossible", "0", ART / "minactions/summary.log", r"impossible=(\d+)"),
    ("twelve were stopped", "12", ART / "minactions/summary.log", r"not_established=(\d+)"),
    # --- scoring pipeline ---
    ("reports a\ntotal of 100.0", "100.0", ART / "pipeline/pipeline.log", r"^Q2 .*toolkit_total=([0-9.]+)"),
    ("documented rule gives 2.222222222", "2.222222222", ART / "pipeline/pipeline.log",
     r"^Q2 .*documented_total=([0-9.]+)"),
    ("a factor of\n45.0", "45.0", ART / "pipeline/pipeline.log", r"^Q2 .*ratio=([0-9.]+)"),
    ("from 100 to\n83.801652893", "83.801652893", ART / "pipeline/pipeline.log",
     r"^Q4 .*toolkit_total=([0-9.]+)"),
    # --- aggregation scope ---
    ("remote fetch (server supplies the scorecard)", "remote fetch (server supplies the scorecard)",
     ART / "aggregation/aggregation.log", r"^MODE online\s+score_produced_by=(.+)$"),
    ("gives a total of 100.0 where the documented rule over four gives 75.0",
     "100.0", ART / "aggregation/aggregation.log", r"^D3 .*toolkit_total=([0-9.]+)"),
    ("over four gives 75.0", "75.0", ART / "aggregation/aggregation.log",
     r"^D3 .*documented_total=([0-9.]+)"),
    # --- the client's wire ledger ---
    ("chooses 16 actions and\nis counted 19", "16", ART / "wire/wire.log", r"^W3 .*chosen=(\d+)"),
    ("is counted 19", "19", ART / "wire/wire.log", r"^W3 .*harness_counter=(\d+)"),
    ("loses a level three times", "3", ART / "wire/wire.log", r"^W3 .*forced=(\d+)"),
    # --- replays ---
    ("lists ten repositories", "10", ART / "replays/availability.log", r"github_repos=(\d+)"),
    ("lists three\ndatasets", "3", ART / "replays/availability.log", r"huggingface_datasets=(\d+)"),
]

# Optima and baselines in Table 2, checked against the per-level artefacts.
TABLE = [("ls20", 1, 13, 22), ("ls20", 2, 45, 123), ("ls20", 3, 39, 73),
         ("tu93", 1, 18, 19), ("tu93", 2, 10, 16), ("tu93", 3, 19, 34)]


def main() -> int:
    subprocess.run([sys.executable, str(HERE / "normalise.py")], check=True, capture_output=True)
    text = (HERE / "main.txt").read_text()
    flat = re.sub(r"\s+", " ", text)
    fails = 0
    for phrase, value, log, pattern in CLAIMS:
        ok, why = True, []
        needle = re.sub(r"\s+", " ", phrase)
        if needle not in flat:
            ok = False; why.append("phrase not in the paper")
        try:
            m = re.search(pattern, log.read_text(), re.M)
        except OSError as e:
            m = None; why.append(f"log unreadable: {e}")
        if m is None:
            ok = False; why.append("pattern not found in the log")
        elif m.group(1) != value:
            ok = False; why.append(f"log says {m.group(1)!r}, the paper asserts {value!r}")
        print(f"[{'ok' if ok else 'FAIL'}] {phrase[:52]!r} = {value}"
              + ("" if ok else "  (" + "; ".join(why) + ")"))
        fails += 0 if ok else 1
    import json
    for game, level, optimum, baseline in TABLE:
        p = ART / "minactions" / f"{game}_L{level}.json"
        d = json.loads(p.read_text())
        ok = d["optimum"] == optimum and d["baseline"] == baseline and d["verdict"] == "consistent"
        also = len(d.get("witness") or []) == optimum
        print(f"[{'ok' if ok and also else 'FAIL'}] table {game} L{level}: optimum {optimum}, "
              f"baseline {baseline} (artefact: {d['optimum']}, {d['baseline']}, {d['verdict']}, "
              f"witness len {len(d.get('witness') or [])})")
        fails += 0 if (ok and also) else 1
    total = len(CLAIMS) + len(TABLE)
    print(f"PAPER CHECK: {'PASS' if fails == 0 else f'FAIL ({fails} of {total} unverified)'} "
          f"({total} figures)")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
