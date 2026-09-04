# FINDINGS — ARC-AGI-3 public-set audit, Phase 0 (scorer, harness, machinery)

Millennium Research, 2026-09-03 (scorer, harness) and 2026-09-04 (environment
ls20 levels 1 and 2, then a breadth sweep of level 1 across the public set).
Status: the scoring rule (reference 3), the benchmarking
harness's action budget, and two levels of one public environment (reference
1) are audited and written up below; the per-level baselines (reference 2)
are recovered and characterised; ls20 levels 3–7, the other 24 public
environments and the human-replay check are not done (see "Not done").

Related work, checked before building and not duplicated: Rudakov, Shock and
Cowley (arXiv 2512.24156, December 2025) build hash-identified state graphs to
*solve* ARC-AGI-3 environments, reporting no state counts, no win probability
and no verification; Rodionov (arXiv 2605.05138v2, June 2026) builds executable
Python world models for all 25 public games, checked against recordings rather
than machine-verified, and does not audit for defects. What is new here is a
machine-verified model of an environment's rules, compared against the shipped
implementation on every reachable transition, and used to check the benchmark's
own published claim about that environment.

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
| ls20 level 1: Dafny model (generated from the shipped level data) | 17 obligations | `verified=17 errors=0` with `TIMEOUTS: 0` (E1 winnable by the 13-action witness, E2 closure, E3 reset) | `artifacts/oracle_env/check_ls20_level1.log` |
| ls20 level 1: model vs shipped implementation | every edge of the graph + 30 traces | `GRAPH_EDGES n=56772 disagreements=0 win_edges_status_only=96`; `TRACES traces=30 steps=3208 disagreements=0 win_edges_status_only=3` | `artifacts/env/ls20/env_L1.log` |
| ls20 level 2: reachable state graph | `"states": 34739`, `"edges": 133788`, complete | one WIN state, `"game_over_states": 1291`, `"shortest_win_depth": 45` (human baseline 123), `"reset_returns_to_start": 500` of `"reset_checked": 500` | `artifacts/env/ls20/graph_L2.json` |
| ls20 level 2: Dafny model | 26 obligations | `verified=26 errors=0` with `TIMEOUTS: 0` | `artifacts/oracle_env/check_ls20_level2.log` |
| ls20 level 2: model vs shipped implementation | every edge of the graph + 30 traces | `GRAPH_EDGES n=133788 disagreements=0`; `TRACES traces=30 steps=1903 disagreements=0` | `artifacts/env/ls20/env_L2.log` |
| ls20: rule-level state space symmetric across the three lives | 2 levels | `rule_symmetric=True` on both | `artifacts/env/ls20/granularity.log` |
| Breadth: environments whose action space can be enumerated at all | 25 | `enumerable=6`, `skipped_click=19` | `artifacts/sweep/summary_L1.log` |
| Breadth: level-1 enumeration within budget | 6 | `complete=2` (ls20, tu93); 4 stopped at exactly 150,000 states | `artifacts/sweep/sweep_L1.log` |
| Breadth: RESET restores the level's start state | 3,000 probes across 6 environments | `reset_probes=3000 reset_returns_to_start=3000` | `artifacts/sweep/summary_L1.log` |
| Breadth: one action advancing the level counter by two (finding F3) | 1,247,448 transitions | `double_advance_actions=0` | `artifacts/sweep/summary_L1.log` |
| Breadth: peak memory | 6 environments | `peak_rss_mb_max=211.8` against a 2500 MB cap | `artifacts/sweep/summary_L1.log` |
| Double-advance (finding F3) reachability | every transition of both levels | `"double_advance_actions": 0` on each | `artifacts/env/ls20/graph_L1.json`, `graph_L2.json` |
| Peak memory of the enumeration | 2 levels | under 300 MB on both, against `"max_rss_mb_cap": 3500.0`; the exact figure varies run to run and is checked as a bound, not a literal | `artifacts/env/ls20/graph_L1.json`, `graph_L2.json` |
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

## Reference 1 — ls20 levels 1 and 2: what was checked and found consistent

Models: `model/ls20_level1.dfy` and `model/ls20_level2.dfy`, generated by
`scripts/gen_level_model.py` from `artifacts/env/ls20/level<k>.json` (walls,
start, goal, rotation tile, energy pickups, step budget, decrement, lives, all
read from the shipped level object by `scripts/extract_level.py`). The rules
are hand-written from the shipped `step()` at the rule level: walls block and
end the collision scan; the goal blocks unless the piece's rotation matches, and
then completes the level; the rotation tile cycles the rotation; a move ending
in a "flash" costs no step; an energy pickup refills the counter and skips that
move's decrement entirely; every other move, blocked or not, costs one
decrement; exhausting the counter costs a life and restores the start layout;
three lives; and an action outside the movement set changes nothing, so the
model is total in the action.

Two rules differ between the levels and are taken from the source, not guessed.
Cycling a tile into a match is a free move on level 1 only, because the shipped
check returns false once the level index is above zero. Level 1 decrements the
counter by one per move and level 2 by two. These are undocumented, as every
ARC-AGI-3 environment rule is by design, and are not reported as defects.

- E1 (winnable): the shortest winning path found by enumerating the shipped
  game (13 actions on level 1, 45 on level 2) is replayed through the model,
  and at every step the model's state is asserted equal to the state the
  shipped game is actually in. The lemma therefore says far more than "the run
  ends in a win": if model and implementation parted company anywhere along the
  winning path it would not verify.
- E2 (closure): from a legal state every action yields a legal state or a
  terminal GAME_OVER; the extracted wall set contains the whole lattice border
  and the player is never on a wall cell.
- E3 (reset restores the start): by definition in the model; on the shipped
  game, RESET from 500 of 500 probed PLAY states on each level (across all three
  lives, with steps spent, the rotation changed and pickups consumed) returns
  exactly to the start state, including the hidden step counter and the
  restored pickups. No state leaks across a level reset on either level.
- E4 (determinism): two fresh instances on the same 60-action trace reach the
  same state; the enumeration's transitions are functions.
- Differential: the compiled model agrees with the shipped implementation on
  every transition of both complete reachable graphs (56,772 and 133,788) and
  on every step of 30 traces per level (10 scripted, 20 random with seeds
  0–19). Winning transitions are compared on status only, because the shipped
  game has already loaded the next level at that point (`docs/DECISIONS.md`).
- F3 reachability, dynamic: no single action advanced the level counter by two
  anywhere in either ls20 level's complete graph, nor anywhere in the breadth
  sweep (`double_advance_actions=0` over 1,247,448 transitions in six
  environments), so the scorer edge is unreachable everywhere it could be
  checked.
- F3 reachability, static: every one of the 25 public sources has exactly one
  `next_level()` call site, none inside a loop. In 11 of 25 (ar25, cn04, dc22,
  ft09, g50t, lf52, lp85, ls20, su15, tn36, tr87) the call is immediately
  followed by `complete_action(); return`, which rules out a second advance in
  the same action; for the other 14 a second advance within one action is not
  excluded statically and is a Phase 1 dynamic check.

**Observation, not a finding — a state count depends on what counts as a
state.** The three-life mechanic should give three copies of the same rule-level
state space, and at the rule level it does. Level 1 is symmetric under both
measures (`rule_by_lives={'3': 4732, '2': 4731, '1': 4731, '0': 143}`, equal to
its key counts). Level 2 is symmetric at the rule level
(`rule_by_lives={'3': 7400, '2': 7399, '1': 7399, '0': 630}`) but not under our
enumerator's raw key (`key_by_lives={'0': 1291, '1': 13024, '2': 13024, '3': 7400}`).
The cause was found and confirmed directly: when a life is lost the shipped game
re-appends previously consumed pickups to the end of the level's sprite list, so
a run that ate a pickup and a run that did not are distinguishable by sprite
order while rendering identically. Level 1 has no pickups, which is why it is
unaffected. This changes no transition (zero disagreements on all 133,788
level-2 edges) and no absorption probability, but it is a caveat on any
published state count for these environments, our own included: the number
depends on the granularity of the identity function, and a frame hash, an
engine-state hash and a rule-level abstraction give three different answers.

## Breadth sweep — level 1 across the public set

Method: enumerate the reachable state graph of level 1 from the shipped game,
with no model and no differential. That alone answers three audit questions per
environment: is the level winnable from its own start state, does RESET restore
that start state, and can one action advance the level counter by two. Search is
depth-first, which holds only the objects along one path, so memory is bounded
by depth rather than by the width of a search layer.

**What is enumerable at all.** Six of the 25 public environments
(`enumerable=6`): ls20, tr87, tu93, g50t, re86, wa30. The other nineteen
(`skipped_click=19`) advertise the click action, whose x and y each range over
0 to 63, giving at least 4,096 successors per state. Exhaustive enumeration is
out of reach for those within any sane budget. This is a measured property of
the advertised action space, taken from the shipped games themselves, not a
judgement about the environments. It is also a limit on any state-graph method
applied to ARC-AGI-3, ours and the published ones alike.

**What completed.** Level 1 finished inside the budget for two environments
(`complete=2`): ls20 at `"states": 14337` and tu93 at `"states": 2609`. The
other four stopped at exactly `"states": 150000`, a deterministic cap chosen so
the artefacts are reproducible; a wall-clock cap stops at a different place on
every run and cannot carry a claim. A capped run establishes nothing about reachability either way,
and the artefacts say so: `win_reachable` is null and no win probability is
reported when a run was truncated without finding a win.

**Findings: none.** Across `states_examined=616946` states and
`transitions_examined=1247448` transitions in six environments:

- No level 1 was shown unwinnable. Both completed environments are winnable.
- RESET returned exactly to the level's start state on every probe:
  `reset_probes=3000 reset_returns_to_start=3000`, 500 per environment, taken
  from states with actions spent and progress made. No state leaked across a
  level reset anywhere.
- No single action advanced the level counter by two:
  `double_advance_actions=0`. The scorer edge behind finding F3 is unreachable
  everywhere it could be checked.

**Why those negatives are worth reading.** A negative only means something if
the detector could have fired. Both are tested against deliberately broken
games: with RESET stubbed out the probe reports a mismatch, and with the engine
made to advance two levels in one action the detector catches it
(`tests/test_sweep.py`). The sweep's zeros are therefore evidence, not silence.

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

- Levels 2 and above of the other five enumerable environments, and level 1 of
  the four that were capped at 150,000 states. Continuing them is a matter of
  compute, not of method; a capped command is in the status note.
- Any state-graph result for the nineteen click-based environments. Their
  branching factor rules the method out, which is stated rather than worked
  around.
- Reference 1 beyond ls20 level 2: the generator refuses levels 3–7 and names
  why — pushers (3–7), colour tiles (3–7), shape tiles (4–7), patrol areas
  (5–7), two goals (6), fog (7). Nothing is claimed about those levels. The
  other 24 public environments are identifier-obfuscated and undocumented; the
  preregistered rule selected ls20 (`INVENTORY.md`).
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
4. The levels audited with a verified model are 2 of ls20's 7. The breadth
   sweep covers level 1 of six environments, two of them exhaustively. Nothing
   here supports a statement about ARC-AGI-3 as a whole, and in particular the
   nineteen click-based environments are untouched by it.
5. A truncated enumeration is a sample of a larger graph, not a survey of it:
   the sweep's negatives hold over the states actually reached, which for four
   environments is the first 150,000 that depth-first search happened to visit.
6. The harness probe replaces the model call with a scripted stub; the loop,
   `is_done`, `_sync_level_progress`, forced RESET handling and
   `choose_action` are the harness's own code.
7. The fixture game `bt11` is the toolkit's test environment, not a public
   benchmark environment; the only public environment claims are about ls20
   levels 1 and 2, whose models we wrote from obfuscated source at the rule
   level. A rule we did not see would be one the model matched anyway on every
   reachable transition, so it is either unreachable on these levels or
   invisible in position, rotation, lives, steps, pickups and status.
8. Every number in this file is registered in `docs/claims.json` and checked
   by `../audit-kit/scripts/report_check.sh`; scripts and artefacts ship in
   this repository; the audited origins have Software Heritage save requests
   accepted (`artifacts/intake/swh_snapshot.log`).
9. What a reader must still trust: Dafny 4.11.0 and its JavaScript backend,
   Node 24, the vendored toolkit at the pinned commit, and our reading of the
   English in the report and docs.

## Reproduce

```
.venv/bin/python -m pytest -q
scripts/check_model.sh
.venv/bin/python scripts/scorer_probe.py
.venv/bin/python scripts/harness_probe.py --environments-dir vendor/ARC-AGI/test_environment_files
scripts/run_machinery.sh
for L in 1 2; do
  .venv/bin/python scripts/extract_level.py --game ls20 --level $L
  .venv/bin/python scripts/state_graph.py --game ls20 --level $L --max-states 400000 --max-seconds 1500 --max-rss-mb 3500
  .venv/bin/python scripts/gen_level_model.py --game ls20 --level $L
  scripts/check_model.sh model/ls20_level$L.dfy artifacts/oracle_env
  .venv/bin/python scripts/env_probe.py --game ls20 --level $L
done
.venv/bin/python scripts/action_census.py
.venv/bin/python scripts/sweep.py --level 1 --search dfs --max-states 150000 --max-seconds 1200 --max-rss-mb 2500
../audit-kit/scripts/report_check.sh docs/claims.json
```

## Credit

The ARC Prize Foundation publishes the toolkit, harness, agents, report and
docs under MIT and open documentation; that openness is what makes this audit
possible. Findings are shared with them first (`notice/notice.DRAFT.md`).
Contact: ibrahimnmian@gmail.com
