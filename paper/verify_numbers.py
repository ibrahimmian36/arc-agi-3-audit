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
    # --- Phase 20: baseline stability ---
    ("Resampling each cell's plays 2,000\ntimes", "2000", ART / "replays/baseline_uncertainty.log", r"^BASEUNC all resamples=(\d+)"),
    ("interval is 84.6% as wide as its baseline", "84.6", ART / "replays/baseline_uncertainty.log", r"^BASEUNC all .*median_rel_width_pct=([0-9.]+)"),
    ("interval is 84.6% as wide as its published value", "84.6", ART / "replays/baseline_uncertainty.log", r"^BASEUNC all .*median_rel_width_pct=([0-9.]+)"),
    ("inside its own interval in 179 of the 183 cells", "179", ART / "replays/baseline_uncertainty.log", r"^BASEUNC all .*published_inside=(\d+)"),
    ("level score between 50.6 and the cap", "50.6", ART / "replays/baseline_uncertainty.log", r"^BASEUNC all .*median_score_low=([0-9.]+)"),
    ("between 50.6 and the cap of\n115", "115.0", ART / "replays/baseline_uncertainty.log", r"^BASEUNC all .*median_score_high=([0-9.]+)"),
    ("For the 21 cells with fewer than 5 plays the resampling", "21", ART / "replays/baseline_uncertainty.log", r"^BASEUNC under5 cells=(\d+)"),
    # --- Phase 19: the harness budget applied to human play ---
    ("the budget cuts off 29 of the 1,614 completions", "1614", ART / "replays/human_budget.log", r"completions=(\d+)"),
    ("the budget cuts off 29 of the 1,614 completions", "29", ART / "replays/human_budget.log", r"over_budget=(\d+)"),
    ("applied to the 1,614 level completions", "1614", ART / "replays/human_budget.log", r"completions=(\d+)"),
    ("the budget cuts off 29, none of them because of those", "0", ART / "replays/human_budget.log", r"cut_only_by_post_game_over_resets=(\d+)"),
    ("all 1,614 human\n      level completions", "1614", ART / "replays/human_budget.log", r"completions=(\d+)"),
    ("Cells rest on between 2 and 40 plays", "2", ART / "replays/human_budget.log", r"plays_min=(\d+)"),
    ("Cells rest on between 2 and 40 plays", "40", ART / "replays/human_budget.log", r"plays_max=(\d+)"),
    ("40 plays (median 8)", "8", ART / "replays/human_budget.log", r"plays_median=(\d+)"),
    ("and 21 of the 183 on fewer\nthan 5", "21", ART / "replays/human_budget.log", r"cells_under_5_plays=(\d+)"),
    ("321 under the shipped engine as configured", "321", ART / "replays/replay_check.log", r"state_and_level_default=(\d+)"),
    ("and 19 only\nunder the engine's", "19", ART / "replays/replay_check.log", r"state_and_level_only_under_switch=(\d+)"),
    ("19 of them only under an engine switch", "19", ART / "replays/replay_check.log", r"state_and_level_only_under_switch=(\d+)"),
    ("and 19 only under it", "19", ART / "replays/replay_check.log", r"state_and_level_only_under_switch=(\d+)"),
    # --- Phase 18: the human replays ---
    ("The 340 released recordings reproduce", "340", ART / "replays/human_baselines.log", r"^HUMAN recordings=(\d+)"),
    ("340 recordings, not 342", "340", ART / "replays/human_baselines.log", r"^ARCHIVE .* recordings=(\d+) announced"),
    ("340 recordings, not 342", "342", ART / "replays/human_baselines.log", r"announced=(\d+)"),
    ("reproduce 165 of the 183 published baselines", "165", ART / "replays/human_baselines.log", r"charged_exact=(\d+)"),
    ("reproduce 165 of the 183 published baselines", "183", ART / "replays/human_baselines.log", r"^HUMAN recordings=\d+ plays=\d+ cells=(\d+)"),
    ("reproduces 165 exactly and\nfour more within one", "4", ART / "replays/human_baselines.log", r"charged_off_by_one=(\d+)"),
    ("stored tallies reproduces 166", "166", ART / "replays/human_baselines.log", r"card_exact=(\d+)"),
    ("the uncharged reading reproduces 101 exactly", "101", ART / "replays/human_baselines.log", r"uncharged_exact=(\d+)"),
    ("and 42 more within one", "42", ART / "replays/human_baselines.log", r"uncharged_off_by_one=(\d+)"),
    ("On the 72 cells where\na human reset", "72", ART / "replays/human_baselines.log", r"decisive_cells=(\d+)"),
    ("charged reading on 65, the uncharged on one, and neither on six", "65", ART / "replays/human_baselines.log", r"^HUMAN decisive_cells=\d+ charged=(\d+)"),
    ("charged reading on 65, the uncharged on one, and neither on six", "1", ART / "replays/human_baselines.log", r"^HUMAN decisive.* uncharged=(\d+)"),
    ("charged reading on 65, the uncharged on one, and neither on six", "6", ART / "replays/human_baselines.log", r"^HUMAN decisive.* neither=(\d+)"),
    ("final line on 316 plays", "316", ART / "replays/human_baselines.log", r"card_agree=(\d+)"),
    ("on the 22\nold-recorder plays that complete a level", "22", ART / "replays/human_baselines.log", r"card_old_tally_offset=(\d+)"),
    ("two lp85 cards", "2", ART / "replays/human_baselines.log", r"card_disagree=(\d+)"),
    ("29 and 54, equal the upper", "29", ART / "replays/human_baselines.log", r"cn04/L1:published=(\d+)"),
    ("29 and 54, equal the upper", "54", ART / "replays/human_baselines.log", r"tr87/L1:published=(\d+)"),
    ("rule, 30 and 55", "30", ART / "replays/human_baselines.log", r"cn04/L1:published=\d+:card=\d+:stream=(\d+)"),
    ("rule, 30 and 55", "55", ART / "replays/human_baselines.log", r"tr87/L1:published=\d+:card=\d+:stream=(\d+)"),
    ("reproduces four of seven cells", "4/7", ART / "replays/human_baselines.log", r"g50t=(\d+/\d+)"),
    ("lp85 one of eight", "1/8", ART / "replays/human_baselines.log", r"lp85=(\d+/\d+)"),
    ("vc33 one of seven", "1/7", ART / "replays/human_baselines.log", r"vc33=(\d+/\d+)"),
    ("Eight published values\noccur as the charged count", "8", ART / "replays/human_baselines.log", r"published_absent_from_release=(\d+)"),
    ("baseline\nof 230 sits over two released plays that took 31 and 52 actions", "230", ART / "replays/human_baselines.json", r'"g50t/L4": \{\s*"published": (\d+)'),
    ("took 31 and 52 actions", "31", ART / "replays/human_baselines.json", r'"g50t/L4": \{[^}]*?"charged": \[\s*(\d+),'),
    ("took 31 and 52 actions", "52", ART / "replays/human_baselines.json", r'"g50t/L4": \{[^}]*?"charged": \[\s*\d+,\s*(\d+)\s*\]'),
    ("In all 183 cells the smallest human count", "183", ART / "replays/human_baselines.log", r"bound_consistent=(\d+)"),
    ("every one of their 180496 steps", "180496", ART / "replays/replay_check.log", r"steps=(\d+)"),
    ("every one of\n180496 steps", "180496", ART / "replays/replay_check.log", r"steps=(\d+)"),
    ("All 340 reproduce state and level", "340", ART / "replays/replay_check.log", r"state_faithful=(\d+)"),
    ("284 reproduce the rendered frame", "284", ART / "replays/replay_check.log", r"full_default=(\d+)"),
    ("15 do so only under the switch", "15", ART / "replays/replay_check.log", r"full_levelonly=(\d+)"),
    ("the remaining 41", "41", ART / "replays/replay_check.log", r"frame_only=(\d+)"),
    ("6844\nframes differ in decoration", "6844", ART / "replays/replay_check.log", r"frames_differing=(\d+)"),
    ("and 19 only under it, exactly the plays that contain such a reset beyond\nlevel 1", "19", ART / "replays/replay_check.log", r"plays_with_trap_beyond_level1=(\d+)"),
    ("29 resets fall at a zeroed counter, in 24 of the plays", "24", ART / "replays/replay_check.log", r"plays_with_trap=(\d+)"),
    ("where 24 of those 29 resets fall", "24", ART / "replays/replay_check.log", r"trap_beyond_level1=(\d+)"),
    ("29 resets fall, in 19\nplays", "19", ART / "replays/replay_check.log", r"plays_with_trap_beyond_level1=(\d+)"),
    ("Twenty-three recordings, all from March 2026", "23", ART / "replays/human_baselines.log", r"old_recorder_recordings=(\d+)"),
    ("28 are\na reset straight after a reset", "28", ART / "replays/replay_check.log", r"double_reset=(\d+)"),
    ("one is a reset at the start of a level", "1", ART / "replays/replay_check.log", r"reset_at_level_start=(\d+)"),
    ("environment scores\n10.714286", "10.714286", ART / "replays/full_reset_probe.log", r"^FULLRESET A_reset_then_continue level_only .*score=([\d.]+)"),
    ("the environment scores 3.571429", "3.571429", ART / "replays/full_reset_probe.log", r"^FULLRESET A_reset_then_continue default .*score=([\d.]+)"),
    ("never reset and now at 46", "46", ART / "replays/full_reset_probe.log", r"^FULLRESET A_reset_then_continue default .*harness_counter=(\d+)"),
    ("13 more charged actions", "[13, 58]", ART / "replays/full_reset_probe.log", r"^FULLRESET B_reset.*card_actions=(\[13, 58\])"),
    ("111142305\nbytes", "111142305", ART / "replays/human_baselines.log", r"bytes=(\d+)"),
    ("SHA-256 beginning 99a32ffc", "99a32ffc", ART / "replays/human_baselines.log", r"sha256=([0-9a-f]{8})"),
    # --- figures the consistency check found untraced (Phase 15) ---
    ("refused our request with HTTP 403", "403", ART / "replays/availability.log",
     r"announced_link_status=(\d+)"),
    ("one\nsubfolder per public environment", "25", ART / "replays/browser_observation.log",
     r"environment_folders=(\d+)"),
    ("under caps of 400000 states", "400000", ART / "env/ls20/graph_L1.json", r'"max_states": (\d+)'),
    ("3500~MB of resident memory", "3500", ART / "env/ls20/graph_L1.json", r'"max_rss_mb_cap": (\d+)'),
    ("depth-first with caps of 150000 states", "150000", ART / "sweep/tr87_L1.json", r'"max_states": (\d+)'),
    ("1200 seconds and 2500~MB", "2500", ART / "sweep/tr87_L1.json", r'"max_rss_mb_cap": (\d+)'),
    ("Eight rollouts are run per level", "8", ART / "deathcost/deathcost.log", r"died=\d+/(\d+)"),
    ("each of ten seeds", "10", ART / "tax/tax.log", r"^TAX .*seeds=(\d+)"),
    ("25 public environments as audited", "25", ART / "api/environment_sources.log", r"^SUMMARY environments=(\d+)"),
    ("143 on level~1", "143", ART / "env/ls20/graph_L1.json", r'"game_over_states": (\d+)'),
    ("1291 on level~2", "1291", ART / "env/ls20/graph_L2.json", r'"game_over_states": (\d+)'),
    ("23 of the 25 environments have at least one such", "23",
     ART / "deathcost/deathcost.log", r"^SUMMARY .*environments_with_an_exposed_level=(\d+)"),
    ("which is 234 of the 250", "234", ART / "tax/tax.log",
     r"^OUTCOME .*runs_where_neither_completed_a_level=(\d+)"),
    ("did not choose is 0.69", "0.006896552", ART / "tax/tax.log",
     r"^TAX .*median_forced_share_of_counted=([0-9.]+)"),
    ("costs a level between 0.035% and", "0.000346021", ART / "budget/budget.log",
     r"^TAX .*min_share=([0-9.]+)"),
    ("3.33% of its budget", "0.033333333", ART / "budget/budget.log",
     r"^TAX .*max_share=([0-9.]+)"),
    ("4732/4731/4731", "4731", ART / "env/ls20/granularity.log",
     r"^L1 .*rule_by_lives=\{'3': \d+, '2': (\d+)"),
    ("7400/7399/7399", "7399", ART / "env/ls20/granularity.log",
     r"^L2 .*rule_by_lives=\{'3': \d+, '2': (\d+)"),
    ("chooses 16 actions", "16", ART / "wire/wire.log", r"^W3 .*chosen=(\d+)"),
    ("on 30 recorded", "30", ART / "env/ls20/env_L1.log", r"TRACES traces=(\d+)"),
    ("against a budget of 110", "110", ART / "deathcost/deathcost.log",
     r"^DEATH ls20 L1 .*budget=(\d+)"),

    # --- what the forced resets cost a policy that simply plays ---

    ("On 148 of the 183 levels, that bound falls", "148", ART / "deathcost/deathcost.log",
     r"^SUMMARY .*exposed=(\d+)"),
    ("all 183 levels of the 25 public", "183", ART / "deathcost/deathcost.log",
     r"^SUMMARY .*levels=(\d+)"),
    ("the remaining 35", "35", ART / "deathcost/deathcost.log",
     r"^SUMMARY .*not_established=(\d+)"),

    ("250 paired runs over all 25 environments", "250", ART / "tax/tax.log",
     r"^TAX runs=(\d+)"),
    ("the maximum is 6.28%", "0.062801932", ART / "tax/tax.log",
     r"^TAX .*max_forced_share_of_counted=([0-9.]+)"),
    ("in any of the 250", "0", ART / "tax/tax.log",
     r"^OUTCOME .*runs_where_a_level_differs=(\d+)"),
    ("all 25 environments and", "25", ART / "tax/tax.log", r"^ENVS .*measured=(\d+)"),

    # --- the denial on a real public level, at its real budget ---
    ("scores 0.087046682", "0.087046682", ART / "realdenial/realdenial.log",
     r"^PAIR tu93 .*chosen=95 .*counterfactual:[^|]*score=([0-9.]+)"),
    ("baseline of 19 gives a budget of 95", "95", ART / "realdenial/realdenial.log",
     r"^SETUP tu93 L1 baseline=19 budget=(\d+)"),
    ("shortest losing line at 129", "129", ART / "deathcost/exhaustive.log",
     r"^EXHAUSTIVE ls20 L1 .*shortest_loss=(\d+)"),

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
    ("median of 3.251814028 level-score points", "3.251814028",
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
    ("12 were stopped", "12", ART / "minactions/summary.log", r"not_established=(\d+)"),
    # --- scoring pipeline ---
    ("reports a\ntotal of 100.0", "100.0", ART / "pipeline/pipeline.log", r"^Q2 .*toolkit_total=([0-9.]+)"),
    ("set-size reading gives 2.222222222", "2.222222222", ART / "pipeline/pipeline.log",
     r"^Q2 .*documented_total=([0-9.]+)"),
    ("a factor of\n45.0", "45.0", ART / "pipeline/pipeline.log", r"^Q2 .*ratio=([0-9.]+)"),
    ("from 100 to\n83.801652893", "83.801652893", ART / "pipeline/pipeline.log",
     r"^Q4 .*toolkit_total=([0-9.]+)"),
    # --- aggregation scope ---
    ("remote fetch (server supplies the scorecard)", "remote fetch (server supplies the scorecard)",
     ART / "aggregation/aggregation.log", r"^MODE online\s+score_produced_by=(.+)$"),
    ("gives a total of 100.0 where the set-size reading over four gives 75.0",
     "100.0", ART / "aggregation/aggregation.log", r"^D3 .*toolkit_total=([0-9.]+)"),
    ("over four gives 75.0", "75.0", ART / "aggregation/aggregation.log",
     r"^D3 .*documented_total=([0-9.]+)"),
    # --- the client's wire ledger ---
    ("chooses 16 actions and\nis counted 19", "16", ART / "wire/wire.log", r"^W3 .*chosen=(\d+)"),
    ("is counted 19", "19", ART / "wire/wire.log", r"^W3 .*harness_counter=(\d+)"),
    ("loses a level three times", "3", ART / "wire/wire.log", r"^W3 .*forced=(\d+)"),
    # --- replays ---
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
