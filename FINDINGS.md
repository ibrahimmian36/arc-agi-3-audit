# FINDINGS — ARC-AGI-3 public-set audit, Phase 0 (scorer, harness, machinery)

Millennium Research, 2026-09-03 (scorer, harness) and 2026-09-04 (environment
ls20 level 1). Status: the scoring rule (reference 3), the benchmarking
harness's action budget, and one level of one public environment (reference
1) are audited and written up below; the per-level baselines (reference 2)
are recovered and characterised; levels 2–7 of ls20, the other 24 public
environments and the human-replay check are Phase 1 (see "Not done").

**Scope.** In scope: the 25 public demonstration environments, the public
toolkit `arcprize/ARC-AGI` (f12822c), the public harness
`arcprize/arc-agi-3-benchmarking` (1aa78da), the example agents (4743e7d), the
technical report (arXiv 2603.24621 v2) and docs.arcprize.org. **Not in scope,
ever:** the 55 semi-private and 55 private environments; any attempt to
recover, probe, scrape or infer them; anything that violates the competition
rules or the repositories' licences (all MIT); any agent whose purpose is to
score rather than to audit.

**Method.** The documented scoring rule was written as a Dafny model
(`model/scoring.dfy`, 50 obligations verified, 0 errors, no `assume` /
`{:axiom}` / `{:verify false}`), compiled to a JavaScript oracle, and run
differentially against the shipped Python scorer on 14 preregistered planted
traces (`docs/PREREGISTRATION.md` §1.2). The harness's real main loop and
budget logic were run against the toolkit in OFFLINE mode on 6 scripts (5
preregistered in §1.3, plus H1b added and dated in `docs/DECISIONS.md`). Reject-only
throughout: an automated step reports a disagreement or "no disagreement"; a
human read every disagreement and classified it below. Nothing here
certifies the scorer.

## Summary

| what | n | result | artefact |
|---|---|---|---|
| Scorer vs documented prose rule (cap 115 on the score) | 13 traces with an oracle value | `agree_primary=12` (tolerance 1e-6), per-level scores `levels_agree_primary=12`; the 13th is P8 below | `artifacts/scorer/probes.log` |
| Scorer vs oracle, primary reading | `probes=14` traces | `disagreements_primary=1`, `ids=['P8']` | `artifacts/scorer/probes.log` |
| Harness per-level budget (5x baseline) | `probes=6` scripts | `any_over_budget=False`; cut off exactly at the budget on H1b and H5 (`budget_exits=2`); harness and Card action counts equal on every script (`counts_equal=6`) | `artifacts/harness/harness.log` |
| Machinery on the fixture game (M1–M7) | `traces=7` | all as predicted from the engine source; recorder count = Card count (`parity_all_agree=True`) | `artifacts/recorder/machinery.log`, `artifacts/recorder/*.json` |
| Dafny model | 50 obligations | `verified=50 errors=0`; oracle sha256 `189d2bd85136764c809070276b76d4b6b333d18e77158e306b21ded3ba4e25e0` | `artifacts/oracle/check_model.log` |
| ls20 level 1: reachable state graph from the shipped game | `"states": 14337`, `"edges": 56772`, complete | three life-copies (`"3": 4732`, `"2": 4731`, `"1": 4731`) + `"game_over_states": 143` + `"win_states": 1`; `"shortest_win_depth": 13` (human baseline 22); `"reset_returns_to_start": 500` of `"reset_checked": 500` | `artifacts/env/ls20/graph_L1.json` |
| ls20 level 1: documented claim "P_win exactly 1 in 355" | 1 | `0.002813847150161035`, i.e. 1 in `355.38533070027296` under a uniform random policy | `artifacts/env/ls20/graph_L1.json` |
| ls20 level 1: Dafny model (generated from the shipped level data) | 12 obligations | `verified=12 errors=0` (E1 winnable by the 13-action witness, E2 closure, E3 reset); oracle sha256 `3ccf8b0293b25ba53b0834ab5737db9d8b6a1b9f169ed28aef433eec344cc598` | `artifacts/oracle_env/check_model.log` |
| ls20 level 1: model vs shipped implementation | every edge of the graph + 30 traces | `GRAPH_EDGES n=56772 disagreements=0 win_edges_status_only=96`; `TRACES traces=30 steps=3208 disagreements=0 win_edges_status_only=3` | `artifacts/env/ls20/env.log` |
| Re-run byte identity | scorer, harness, recorder | identical (`tests/test_scorer_probe.py`, `tests/test_harness_probe.py`, `tests/test_recorder.py::test_m8_byte_identity`) | suite |

The shipped scorer implements the rule as the report's prose and the docs
state it. The defects found are in the documentation of that rule and in one
unhandled edge of the scorer, listed below. The two leads in the initial brief are
closed: the 115 per-level cap is documented (toolkit changelog 0.9.7,
2026-04-14; docs methodology; report v2 §4.2), and level weights are 1-based.

## Findings

**F1 — Documentation defect (technical report v2, Equation 1).** Equation (1)
in §4.1 is typeset as `S = min(1.15, h/a)^2`, which caps the *ratio* before
squaring and allows a per-level score of 132.25%. The report's own prose
("we cap the maximum score for a level at 1.15x the human baseline"; "between
0% and 115%"), the docs methodology page, and the shipped scorer all cap the
*score* at 115%. Evidence: probe P2a, shipped level-1 score `115.0`; probe P2c,
shipped environment score `49.333333` under the prose reading versus
`50.483333` under the equation reading. The code is consistent with the prose;
the equation is the outlier. Classification: documentation.

**F2 — Documentation defect (where the 5x cutoff lives).** The report v2
§4.3.1 states a hard budget of five times the human baseline per level. That
budget exists only in the benchmarking harness (`MAX_ACTIONS_BASELINE_MULTIPLIER:
5.0` in every shipped model config; enforced per level in
`BenchmarkingAgent.is_done`). The scorer has no cutoff: probe P3b (level 1
solved in 51 actions against a baseline of 10) scores `93.589645`, where the
rule-as-stated gives `0.000000` (level never completed). The docs methodology
page and the competition-mode page do not mention the cutoff at all. Any
scorecard computed by the toolkit's scorer from a run that did not use the
harness (the example agents, a human-driven session, a third-party agent) is
scored without the budget. Classification: documentation (the cutoff is a run
policy of the official harness, not a property of the scoring rule; readers of
the report cannot tell). The harness itself enforces it exactly: H1b executes
`executed_per_level={'0': 20}` and exits `ACTION_BUDGET` with level 1 not
completed; H5 executes `{'0': 4, '1': 40}` and refuses the 41st action on
level 2.

**F3 — Scorer edge, undocumented (double advance).** If one action advances
`levels_completed` by two (the engine permits a game to call `next_level()`
twice in one `step()`; `_score` increases by two while the level index moves
by one), the scorer pairs the k-th `actions_by_level` entry with level k, so
the final level is scored as *not completed* although the play ends in WIN
with `levels_completed` equal to the level count. Probe P8: shipped `66.666667`
with state WIN and 5 of 5 levels completed; the documented rule gives
`100.000000`. Whether any public environment can trigger this is a static
check on the fetched sources (Phase 1); until then this is a robustness
finding about the scorer, not a claim about any environment. Classification:
scorer edge / engine documentation silent.

**F4 — Documentation gap (action accounting).** Neither the report nor the
docs pages fetched state how RESET, GAME_OVER, the initial RESET, or actions
outside `available_actions` are counted. Observed on the fixture with the
shipped toolkit: a level RESET counts as an action in the scorecard (M1,
`counts_agree: true` with two resets; P4 level-1 score `44.444444444` for
4 + RESET + 10); RESET after GAME_OVER is a level reset that keeps
`levels_completed` (M5); the initial RESET issued inside `make()` is counted by
neither the harness nor the scorecard (H1: 20 scripted actions all executed
within a budget of 20); an action not in `available_actions` is accepted,
counted, and changes nothing (M6, three such actions, recorder and Card both `"card_total": 3`).
These are consistent between harness and scorer and are not defects; they are
rules a reader cannot find written down. Classification: documentation.

**F5 — Stale comment (trivial).** `arc_agi/scorecard.py::add_level` comments
"max 100" above the `min(score, 115.0)` cap, and the toolkit's own test
comments say "Capped at 100" while asserting 115. Classification: code
comment.

**F6 — To verify after the fetch.** The docs' published response schema for
`/api/games` omits `baseline_actions`, while the toolkit reads that field from
the same endpoint. Which is right is settled by the real response saved by
`scripts/fetch_public_envs.py`; not a finding yet.

**F7 — Documentation gap (report v2 Fig. 3, "P_win for this level is exactly 1 in
355").** The term is not defined. Under the natural reading (probability that a
uniformly random policy over ACTION1–4 reaches the level's WIN before
GAME_OVER, starting from the reset state), the shipped level gives
`0.002813847150161035` = 1 in 355.39: consistent to three
significant figures, "exactly" is a rounding. Under the other readings we
computed (1 / states, winning states / states) the value is 1 in 14,337. The
figure's "three repeating states" is confirmed: the graph is three copies of
4,731–4,732 states, one per remaining life. Classification: documentation
(undefined term); the environment agrees with the intended claim.

**Observation, not a finding — baseline versus optimum.** ls20 level 1 is
solvable in 13 actions; the human baseline is 22. The docs define the
baseline as the upper-median first-time player, not the optimum, so an agent
can score above 100% on this level (up to the 115% cap at 20 or fewer
actions); this is the designed behaviour.

## Reference 1 — ls20 level 1: what was checked and found consistent

Model: `model/ls20_level1.dfy`, generated by `scripts/gen_level_model.py` from
`artifacts/env/ls20/level1.json` (walls, start, goal, rotation tile, step
budget, decrement, lives, all read from the shipped level object by
`scripts/extract_level.py`); the rules are hand-written from the shipped
`step()` at the rule level: walls block; the goal blocks unless the piece's
rotation matches, and then completes the level; the rotation tile cycles the
rotation; a move ending in a "flash" (goal mismatch, or a rotation into a
match) costs no step; every other move, blocked or not, costs one step; 43
costed moves exhaust a life and restore the start layout; three lives.

- E1 (winnable): the 13-action path found by enumerating the shipped game is
  replayed through the model and reaches WIN (`verified=12 errors=0`).
- E2 (closure): from a legal state every action yields a legal state or a
  terminal GAME_OVER; the extracted wall set contains the whole lattice border
  and the player is never on a wall cell.
- E3 (reset restores the start): by definition in the model; on the shipped
  game, RESET from 500 of 500 probed PLAY states (across all three lives, with
  steps spent and the rotation changed) returns exactly to the start state,
  including the hidden step counter. No state leaks across a level reset on
  this level.
- E4 (determinism): two fresh instances on the same 60-action trace reach the
  same state; the enumeration's transitions are functions.
- Differential: the compiled model agrees with the shipped implementation on
  all 56,772 transitions of the complete reachable graph and on all 3,208
  steps of 30 traces (10 scripted, 20 random with seeds 0–19). The 96 (and 3)
  winning transitions are compared on status only, because the shipped game
  has already loaded level 2 at that point (`docs/DECISIONS.md`).
- F3 reachability, static: every one of the 25 public sources has exactly one
  `next_level()` call site, none inside a loop. In 11 of 25 (ar25, cn04, dc22,
  ft09, g50t, lf52, lp85, ls20, su15, tn36, tr87) the call is immediately
  followed by `complete_action(); return`, which rules out a second advance in
  the same action; for the other 14 a second advance within one action is not
  excluded statically and is a Phase 1 dynamic check.

## Negatives (checked, found consistent)

- Scorer equals the documented prose rule on P1, P2a, P2b, P2c, P3a, P3b (no
  cutoff), P4, P5, P6, P7, P9, P10 and on every per-level score (12 of the 13
  with an oracle value; the 13th is P8, finding F3). P11 (baseline length mismatch) returns 0 with an
  explicit message; the rule is undefined there.
- Level weights are 1-based: P5 (only level 1, at baseline) scores
  `6.666667` = 100/15. Initial brief Lead 2 closed.
- The 115 cap: P2a level-1 score is `115.0`, matching changelog 0.9.7, the
  docs and report v2 prose. Initial brief Lead 1 closed as documented behaviour.
- Environment cap: P2b and P6 both give `66.666667` for 4 of 5 levels, as the
  docs' worked example states.
- Best-of-plays: P10 gives `100.000000`, matching "average of the best score
  for each environment".
- Harness: budgets `[20, 40, 80, 100, 120]` from baselines `[4, 8, 16, 20, 24]`;
  no probe executed more than its level budget; harness action counter and
  Card actions agree on all 6 scripts: H1 `harness_actions=20` / `card_actions=[20]`,
  H1b 20 / 20, H2 `harness_actions=19` / `card_actions=[19]`, H4 `harness_actions=44` /
  44, H5 44 / `card_actions=[44]`, H6 `harness_actions=9` / `card_actions=[9]`.
- Machinery: recorder count equals Card count (M1); RESET before any action
  is a full reset (M2); level reset keeps progress (M3); RESET after WIN
  starts a new play (M4); GAME_OVER then RESET is a level reset (M5);
  unavailable actions are accepted and counted (M6); never solving scores 0
  (M7); re-runs are byte-identical (M8).

## Preregistered predictions versus observed

| id | predicted | observed | note |
|---|---|---|---|
| P1–P7, P9, P10 | agree with prose reading | agree | as preregistered |
| P3b | scorer 93.59, rule-with-cutoff 0 | `93.589645` / `0.000000` | as preregistered (rounded value in the preregistration) |
| P8 | scorer 66.67, rule 100 | `66.666667` / `100.000000` | as preregistered |
| P2c | code follows prose | `49.333333` = prose | as preregistered |
| H1 | 20 executed, cut off, Card 19 | 20 executed, level completed, Card 20 | WRONG: the initial RESET is issued inside `make()` and counted by neither side (DECISIONS, pre-run row). H1b added: cut off at 20, level not completed |
| H2 | solves on the 20th, Card 19 | solves on the 19th, Card 19 | script was built on the wrong initial-reset assumption; no cutoff exercised |
| H4 / H5 | 40th allowed / 41st refused | `final_levels=2` / `ACTION_BUDGET` at 40 | as preregistered |
| H6 | harness 10, Card 9 | harness 9, Card 9 | same wrong assumption; the two counts agree |

The wrong prediction is reported as such. Its correction removes a
predicted asymmetry (harness stricter than scorer by one action on level 1);
the observed state is that they agree.

## Not done, and why

- Reference 1 beyond ls20 level 1: levels 2–7 add energy pickups, pushers,
  patrolling objects, colour/shape tiles and fog; the generator covers
  walls/goal/rotation-tile levels only. The other 24 public environments are
  identifier-obfuscated and undocumented; the preregistered rule selected ls20
  (`INVENTORY.md`). Phase 1.
- Reference 2 (baselines): recovered for all 25 environments (`INVENTORY.md`;
  the API listing and every `metadata.json` agree, 25/25). The statistic is
  documented (upper median of first-time players; report v1 said second-best).
  The 342 human replays announced on 2026-04-14 were not located or
  downloaded; replaying them is Phase 1.
- F3's dynamic reachability in the 14 environments where the static scan does
  not exclude it.
- The HN thread on a "misleading scorecard" (item 49556467) could not be
  fetched (HTTP 429) and is not used.

## Honest limits

1. Everything above is about the *public* toolkit, harness and documents at
   the pinned commits; the server-side scorer that produces the official
   leaderboard is not observable and is not claimed to match the toolkit.
2. "No disagreement" is on 14 planted traces and 6 harness scripts chosen by
   us; it is not a proof that the scorer is correct.
3. The Dafny model encodes our reading of the report and docs; a
   disagreement could always be our model being wrong. Where our own
   arithmetic or scripts were wrong (three test literals, H1/H2/H6's
   initial-reset assumption) it is recorded in `docs/DECISIONS.md`.
4. The harness probe replaces the model call with a scripted stub; the loop,
   `is_done`, `_sync_level_progress`, forced RESET handling and
   `choose_action` are the harness's own code.
5. The fixture game `bt11` is the toolkit's test environment, not a public
   benchmark environment; the only public environment claims are about ls20
   level 1, whose model we wrote from obfuscated source at the rule level.
   A rule we did not see (the model matched the implementation on every
   reachable transition, so any such rule is unreachable on this level or
   invisible in position/rotation/lives/steps/status).
6. Every number in this file is registered in `docs/claims.json` and checked
   by `../audit-kit/scripts/report_check.sh`; scripts and artefacts ship in
   this repository; the audited origins have Software Heritage save requests
   accepted (`artifacts/intake/swh_snapshot.log`).
7. What a reader must still trust: Dafny 4.11.0 and its JavaScript backend,
   Node 24, the vendored toolkit at the pinned commit, and our reading of the
   English in the report and docs.

## Reproduce

```
.venv/bin/python -m pytest -q
scripts/check_model.sh
.venv/bin/python scripts/scorer_probe.py
.venv/bin/python scripts/harness_probe.py --environments-dir vendor/ARC-AGI/test_environment_files
scripts/run_machinery.sh
.venv/bin/python scripts/extract_level.py --game ls20 --level 1
.venv/bin/python scripts/state_graph.py --game ls20 --level 1 --max-states 400000 --max-seconds 2400
.venv/bin/python scripts/gen_level_model.py --game ls20 --level 1 && scripts/check_model.sh model/ls20_level1.dfy artifacts/oracle_env
.venv/bin/python scripts/env_probe.py --game ls20 --level 1
../audit-kit/scripts/report_check.sh docs/claims.json
```

## Credit

The ARC Prize Foundation publishes the toolkit, harness, agents, report and
docs under MIT and open documentation; that openness is what makes this audit
possible. Findings are shared with them first (`notice/notice.DRAFT.md`).
Contact: ibrahimnmian@gmail.com
