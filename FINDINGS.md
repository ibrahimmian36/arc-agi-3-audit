# FINDINGS — ARC-AGI-3 public-set audit, Phase 0 (scorer, harness, machinery)

Millennium Research, 2026-09-03 (scorer, harness) and 2026-09-04 (environment
ls20 levels 1 and 2, then a breadth sweep of level 1 across the public set,
then a play-based probe of all 25, then a lower-bound check on the published
human baselines, then a probe of the scoring pipeline that feeds the formula, then a probe of how
far its aggregation defect reaches, then a ledger of what the client puts on the
wire, then the run-level policies around a run, then an attempt to resolve the
remaining baselines with a different search). Status: the scoring rule (reference 3), the benchmarking
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
| Breadth: one action advancing the level counter by two (finding F3) | 1,245,427 transitions | `double_advance_actions=0` | `artifacts/sweep/summary_L1.log` |
| Breadth: peak memory | 6 environments | `peak_rss_mb_max=202.3` against a 2500 MB cap | `artifacts/sweep/summary_L1.log` |
| Play probe: RESET restores the frame the level began with | 18,663 probes in all 25 environments | `reset_frame_ok=18663` of `reset_probes=18663`; `reset_frame_mismatch=[]` | `artifacts/play/summary.log` |
| Play probe: RESET restores all internal engine state | the same 18,663 probes | `reset_state_ok=15440`; 7 environments differ | `artifacts/play/summary.log` |
| Play probe: one action advancing the level counter by two | `actions_taken=479040` in all 25 | `double_advance_actions=0`, `level_regressions=0` | `artifacts/play/summary.log` |
| Baselines: is any published baseline below the level's optimum? | 18 levels attempted | `consistent=6 impossible=0 not_established=12` | `artifacts/minactions/summary.log` |
| The 342 human replays announced 2026-04-14 | GitHub org and HuggingFace author | `located=False`; `announced_link_status=403` | `artifacts/replays/availability.log` |
| Aggregation denominator: 3 environments played of a 135-environment set | 1 planted scorecard | toolkit reports `toolkit_total=100.0`, the documented rule gives `documented_total=2.222222222`, a `ratio=45.0` | `artifacts/pipeline/pipeline.log` |
| A level RESET charged to the agent's per-level action count | 1 planted scorecard | four resets take an otherwise perfect environment from 100 to `83.801652893` | `artifacts/pipeline/pipeline.log` |
| Which code path scores a run | 4 operation modes | offline and normal compute locally; `online` and `competition` are `remote fetch (server supplies the scorecard)` | `artifacts/aggregation/aggregation.log` |
| An environment that produces no card leaves the denominator | 1 planted scorecard | three of four played gives `toolkit_total=100.0` against `documented_total=75.0` | `artifacts/aggregation/aggregation.log` |
| A game id differing only by version | 1 planted scorecard | the environment scores `0.0` with `No Matching EnvironmentInfo found` | `artifacts/aggregation/aggregation.log` |
| Resets the harness issues on the agent's behalf, and what they cost | 7 scripted harness runs | an agent that chose 16 actions is counted 19: `forced=3 chosen=16`, `harness_counter=19` | `artifacts/wire/wire.log` |
| A retried model call reaching the environment twice | the harness's own retry path plus 7 runs | `RETRY isolated=True`; `one_environment_call_per_counted_action=True` | `artifacts/wire/wire.log` |
| One intended action reaching the server twice | 4 failure modes of the remote wrapper | `max_attempts_per_intended_action=1` | `artifacts/limits/limits.log` |
| Run-level limits varying between entrants | all 12 shipped configurations | `configs=12`, `runtime_overrides=['None']`, `animation_overrides=['None']`, `uniform_multiplier=True` | `artifacts/limits/limits.log` |
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

**F8 — Scorer defect in the public toolkit: the aggregation denominator.**
`EnvironmentScorecard.from_scorecard` computes the overall score as the sum of
environment scores divided by the number of environments present in the
scorecard, that is the number actually played. Report v2 §4.1 defines the total
as "the sum of individual environment scores divided by the total number of
environments", and the documentation's methodology page describes the total as
the average of all game scores over the set. On a planted scorecard covering
three environments of a 135-environment set, each completed perfectly, the
toolkit reports `toolkit_total=100.0` where the documented rule gives
`documented_total=2.222222222`: a `ratio=45.0`. Played over the whole set the two
agree exactly.

This is the first finding in this audit that changes a number rather than a
document, and its scope is now measured rather than assumed. Running
`Arcade.get_scorecard` under each operation mode with a transport that refuses
to open a socket shows where the number comes from: `offline` and `normal`
compute it locally through this arithmetic, while `online` and `competition`
are a `remote fetch (server supplies the scorecard)`. The official benchmarking
harness constructs the toolkit as
`Arcade(operation_mode=OperationMode.ONLINE)`, so this arithmetic never runs for
an official run. That is a stronger and more accurate reason than the one we
first gave, which was that the harness plays the whole set.

The exposure is to the local path, and it is not hypothetical: the toolkit's own
minimal example in its README constructs `Arcade()` --- the default, which is
`normal` --- plays a single environment and prints `scorecard.score`. Following
the quickstart on one environment prints that environment's score where the
report's definition gives it divided by the number of environments in the set.

We make no claim about the server-side scorer, the official leaderboard, or any
particular published result; none of them is observable to us. Classification:
scorer defect on the local path of the public toolkit, or a naming collision
between two documented quantities, depending on whether that field is meant to
be the benchmark metric. Either way a reader can be badly misled.

**F10 --- The denominator loses an environment that fails, not one that scores
zero.** Our first statement of F8 supposed that a run covering the whole set is
safe. It is not, on the local path, because the divisor counts environments that
produced a card. Planting three environments played perfectly and a fourth that
produced no card at all --- a failure, a skip, a filtered id --- gives
`toolkit_total=100.0` where the documented rule over the four gives
`documented_total=75.0`. An environment that produces a card and completes
nothing, and one that is opened but never played, both stay in the divisor and
give `75.0` correctly. So the boundary is between a card that exists and one
that does not, and only the second inflates the total. Same scope as F8: the
local path only.

**F11 --- A version-only difference in a game id scores the environment zero.**
Environment information is matched by full game id including version. A
scorecard recorded against `aa00-v1` and scored against a listing containing
`aa00-v2` scores that environment `0.0`, with the message `No Matching
EnvironmentInfo found`. The control, matching ids, scores `100.0`. This one
moves a score down rather than up, and it is a plausible accident: an
environment version refreshing between a run and its scoring would silently zero
it. The scorer does say so in a message, which a caller may not read.

**F9 — Documentation gap with a score effect: resets are charged to the agent,
and the human side is unknown.** `Card.inc_reset_count` increments both the reset
count and the action count, and the action lands on the level in progress, so a
level reset lowers that level's efficiency score. On an otherwise perfect
five-level play, one reset before each of levels two to five takes the
environment from 100 to `83.801652893`.

Neither the report nor the documentation says whether a RESET counts as an
action. The methodology page defines an action as a discrete interaction that
affects the game state, and excludes internal operations, without settling
RESET. The asymmetry matters because human participants were explicitly allowed
to reset a level at any time, and the report notes that some "reset levels after
reaching a solution in order to improve efficiency". If the published baselines
were computed without charging human resets while agents are charged for theirs,
the ratio is biased against agents by an amount that depends on how often each
side reset. We cannot settle this: it needs the human replays, which we could
not locate (above). We report it as the sharpest open question in the scoring
rule.

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
  sweep (`double_advance_actions=0` over 1,245,427 transitions in six
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
`transitions_examined=1245427` transitions in six environments:

- No level 1 was shown unwinnable. Both completed environments are winnable.
- RESET returned exactly to the level's start state on every probe:
  `reset_probes=3000 reset_returns_to_start=3000`, 500 per environment, taken
  from states with actions spent and progress made. No state leaked across a
  level reset anywhere.
- No single action advanced the level counter by two:
  `double_advance_actions=0`. The scorer edge behind finding F3 is unreachable
  everywhere it could be checked.
- Every environment reports `"unhandled_types": []`: the state key read every
  attribute of every game by value, so it cannot have merged two states that
  the game itself distinguishes.

**Why those negatives are worth reading.** A negative only means something if
the detector could have fired. Both are tested against deliberately broken
games: with RESET stubbed out the probe reports a mismatch, and with the engine
made to advance two levels in one action the detector catches it
(`tests/test_sweep.py`). The sweep's zeros are therefore evidence, not silence.

## Play probe — all 25 environments, including the click-based ones

Method: play each environment at random inside its own advertised action set,
sampling click coordinates uniformly within the declared 0 to 63 bounds, and
probe as you go. Memory stayed under 200 MB across the whole run, against a
1 GB cap: the prober holds one game object plus one short-lived copy per probe,
where the enumerator held a whole search layer. Two of the three questions the enumerator answers need no state
graph, so this reaches the nineteen environments enumeration cannot touch. It is
an audit instrument, not a solver: it never tries to win anything, and it never
did (`wins=0` everywhere, which is what random play on these environments looks
like).

**RESET restores everything an agent can observe, everywhere.** Across
`reset_probes=18663` probes in all 25 environments, the rendered frame after a
level reset was identical to the frame the level began with every single time:
`reset_frame_ok=18663`, `reset_frame_mismatch=[]`.

**It does not restore all internal engine state, in seven of them.**
`reset_state_ok=15440` of the same probes, with
`reset_state_mismatch=['cd82', 'ft09', 'm0r0', 'r11l', 'sb26', 'sc25', 'sp80']`. What survives is a small number of the game object's
own attributes: in cd82 and sp80 plain integers that play had changed, in sc25 a
pair of animation and spell dictionaries, in others a coordinate pair. Several
are read back by the game's own code, so they could in principle influence later
behaviour, but nothing about them is visible in the frame at reset time.

Read carefully, this is not a defect and is not reported as one. ARC-AGI-3
documents no rules for any environment by design, so "a reset leaves an internal
counter alone" contradicts nothing. What it does bear on is a documented
assumption: the technical report's own state-graph figure begins "from the reset
state of a selected level", and published graph-based agents identify states by
hashing the frame. Frame identity and engine-state identity are not the same
relation here, and in seven of 25 public environments they disagree about
whether a reset returns to a canonical state. Anyone building on "the reset
state of a level" should know which of the two they mean.

**No level counter anomaly anywhere.** Across `actions_taken=479040` actions in
all 25 environments, no single action advanced the level counter by two and none
made it go backwards outside a full reset: `double_advance_actions=0`,
`level_regressions=0`. Together with the enumerations, finding F3's scorer edge
is now unreached in every public environment by both methods.

**Honest coverage.** Random play is a shallow, biased sample: it never won a
level anywhere, and in most environments it never left level 1. These results
hold over the states actually visited, `distinct_states_visited=225337` of them,
and are not a survey of the environments.

**Two of our own bugs, found on the way and fixed.** Both made the tool report
differences that were not in the games. First, containers keyed by objects were
ordered and hashed by the default `repr`, which carries a memory address, so a
level reset that re-clones sprites looked like a state change in cn04, s5i5 and
vc33; after the fix all three probe clean. Second, numpy scalars were hashed by
type rather than value, which merged states in g50t and wa30. Both now have
tests, and the whole sweep was re-run after each.

## Reference 2 — the human baselines

Every ARC-AGI-3 score is a ratio against `baseline_actions[level]`, documented
as the upper-median action count of first-time human players. Two checks were
possible.

**A lower-bound check that needs no replay.** A human cannot finish a level in
fewer actions than the level's optimum, so a published baseline must be at
least that optimum. Breadth-first search supplies it, and supplies a sound bound
even when it does not finish: expanding every state at depth d without reaching
a win proves no solution exists in d + 1 actions or fewer. Before running
anything, two things were confirmed from the shipped code and the numbers
themselves: the scorer pairs `baseline_actions[level_idx]` with that level's own
action count, and the published values are not monotone (ar25 is
`[32, 50, 75, 37, 89, 159, 233, 73]`), so they are per level and not cumulative.
A contradiction would therefore have been real.

There is none. Of `levels_checked=18` attempted across the six enumerable
environments, `consistent=6`, `impossible=0`, `not_established=12`.

| environment | level | optimum | published baseline |
|---|---|---|---|
| ls20 | 1 | 13 | 22 |
| ls20 | 2 | 45 | 123 |
| ls20 | 3 | 39 | 73 |
| tu93 | 1 | 18 | 19 |
| tu93 | 2 | 10 | 16 |
| tu93 | 3 | 19 | 34 |

Every optimum is replayed through the shipped game by the test suite and shown
actually to complete its level, so these are witnessed numbers rather than
search artefacts. The twelve remaining levels were stopped by the time or memory
cap, having completed depths between 8 and 16 against baselines between 26 and
183; that establishes nothing either way and is reported as such.

We then tried to resolve them by changing the search, and could not. The bound
needs a search complete to a stated depth, and breadth-first holds a whole layer
of game objects, so the obvious suspect was memory. We added depth-limited
depth-first search with shallowest-depth memoisation, which gives the same
guarantee while holding only the objects along one path, and an
iterative-deepening form that banks a bound after each completed depth. Memory
duly collapsed: on `g50t` level 1 the peak fell from about a gigabyte to under
150 MB, roughly sevenfold. The exact ratio varies between runs and is not quoted
as a figure. It resolved nothing. In the same time budget breadth-first reached
a greater depth than iterative deepening on both levels compared
(`reached_further=bfs`), because deepening re-explores. On levels breadth-first can finish it is strictly better:
both find `ls20` level 1's optimum of 13, and on level 2 breadth-first finds 45
where deepening times out at depth 28.

So the premise was wrong. The binding constraint is not memory but the size of
the state space at the depths these baselines live at, and no exhaustive search
we can write reaches depth 26, let alone 183. The twelve unresolved levels are
unresolved for a reason rather than for want of effort, and settling them would
need the human replays we could not locate, or a solver for these environments,
which is outside this audit's scope by its own rules. Breadth-first remains the
default because it resolves more; the depth-first modes stay available for a
level where memory rather than time is the wall.

Worth noting rather than flagging: tu93 level 1 has an optimum of 18 and a
published baseline of 19, so the upper-median first-time human played within one
action of optimal on an environment whose rules are not stated anywhere. It is
consistent, and it is the tightest margin in the set.

**The replays could not be located.** The 2026-04-14 announcement says the
Foundation open-sourced the Public Demo dataset including 342 human step-by-step
replays. Checked on 2026-09-04: the `arcprize` GitHub organisation lists
`github_repos=10`, none of them a human-replay dataset; the `arcprize`
HuggingFace author lists `huggingface_datasets=3`, of which the only
human-testing one is for ARC-AGI-2; and the single link the announcement gives is a shortener that did
not resolve for us (`announced_link_status=403`, and 429 on an earlier attempt).
`located=False`.

That is a statement about what these checks found on that date, not a claim that
the data does not exist. It is worth passing on because a broken or rate-limited
link is the kind of thing an owner would want to fix, and because until the
replays are reachable the baselines that every score depends on cannot be
checked against the plays that produced them.

**Observation, not a finding — a reported score and a reported level count can
come from different plays.** For an environment played more than once,
`EnvironmentScoreList` reports the maximum score over runs and the maximum
levels-completed over runs, taken independently. A planted pair where one play
is more efficient but reaches less far, and the other reaches further, produces
an environment whose reported score belongs to the first play and whose reported
level count belongs to the second. The score itself is a legitimate best-of, and
the documentation says the overall score is the average of the best score for
each environment, so nothing is miscomputed; the pairing displayed alongside it
is simply not from one run.

**F12 --- The harness spends the agent's action budget on resets the agent did
not choose, and no document says so.** After a game over the harness issues a
`RESET` of its own accord (`_forced_action_for_frame` returns `RESET` when the
state is `GAME_OVER` or `NOT_PLAYED`). That reset is counted by the harness and,
on the local path, charged by the scorer to the level in progress, exactly as
finding F9 describes for a chosen reset.

Measured on the toolkit's fixture game by driving the harness's own control
loop: an agent that loses the level three times and then solves it chooses 16
actions and is counted 19 (`forced=3 chosen=16`, `harness_counter=19`), and
level one is scored on all 19. Losing once costs one action, losing three times
costs three. With that level's baseline of four, the difference between being
scored on 19 actions and on the 16 the agent chose is a fall of about 29\% in
that level's contribution.

This is a property of the CLIENT. Whether the server charges such a reset is not
observable to us and is not claimed. Nor is the design wrong: after a game over
a reset is the only way to continue, so the harness has to send one. What is
missing is any statement to an entrant that it happens, that it consumes the
per-level action budget, and that it therefore lowers the score of a level the
agent died on --- over and above losing the progress. We searched the report and
the harness documentation and found nothing on forced resets or on resets
counting as actions. It compounds F9: the human baselines' treatment of resets
is unknown, and here the agent is charged for resets it never chose.

**Note, not a finding --- the construction reset is on the wire but is not a
counted action.** The environment wrapper issues a `RESET` when it is built, and
in the online path that is a request to the server like any other. Neither the
harness's counter nor the local scorecard counts it: the local scorer treats a
full reset as beginning a play rather than as an action. The same request shape
reaches the server, so the natural reading is that it begins the play there too.
We record the traffic (`construction=1` in every run, `on_wire` exceeding
`harness_counter` by exactly one) and leave the server's treatment unknown.

**Negative worth keeping: one intended action is sent exactly once.** The
classic way a client inflates its own action count is to resend after a lost
response, which would have the server count two actions for one intent. The
remote wrapper does not. Driven with a transport that records every attempt and
opens no socket, it makes exactly one attempt under a connection error, a read
timeout after the request was sent, a server error, and a well-formed empty
response: `max_attempts_per_intended_action=1`. On the three failures it returns
nothing rather than retrying, which ends that environment's run with an API
error. Whether a server would deduplicate a resend is not observable and is not
claimed; the point is that the client never produces one.

**Negative worth keeping: the run-level limits are the same for every shipped
entrant.** Besides the action budget, a run also stops on a wall-clock limit.
That limit is not in the report. It is, however, uniform: across
`configs=12` shipped model configurations, `runtime_overrides=['None']` and
`animation_overrides=['None']`, and every configuration sets the same action
multiplier (`uniform_multiplier=True`), so the base value of twelve hours per
environment applies to all of them. A cutoff that differed between entrants
would matter a great deal; one that is uniform and set at twelve hours for a
single environment is unlikely to bind. We exercised the branch by setting the
limit rather than by waiting: at zero the run exits on `TIME_BUDGET` having
taken no actions. Reported as an undocumented limit that we could not show has
an effect, rather than as a finding.

**Negative worth keeping: the frame cap subsamples, it does not truncate.** The
harness shows the agent at most seven frames per action. It selects them evenly
across the animation and always includes the last, so the settled frame an agent
must reason about is never dropped: `always_keeps_last=True` across every
combination probed, including a cap of one against twenty frames. Whether the
humans who set the baselines saw more is not establishable from the published
material, which does not describe what they were shown, so we do not make the
comparison.

**Negative worth keeping: a retried model call never reaches the environment.**
The harness retries a failed model call up to three times, which would spend
budget if a retry re-sent the action. It does not. The retry loop contains no
call that reaches the environment, and across all seven scripted runs the number
of environment calls equals the number of actions the harness counted
(`one_environment_call_per_counted_action=True`).

**Negative worth keeping: the budget boundary behaves as documented.** A level
that advances on the last action the budget permits is not cut off, and scores
that level in full; a game over on the last permitted action exits on the budget
with the level unscored.

**Negative worth keeping: reusing a guid does not merge two plays.** The card
resolves a guid by scanning its list backwards, which could have merged two runs
into one and mixed their action counts. Two plays sharing a guid are still
recorded as two plays with separate action counts, and the environment scores
the same as the control with distinct guids.

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
  around. The play probe reaches them for the reset and level-counter questions
  only; reachability remains open for all nineteen.
- Whether the internal state that survives a reset in seven environments
  changes any later outcome. It is read by the games' own code, but showing an
  actual behavioural difference would need a targeted differential per game.
- Reference 1 beyond ls20 level 2: the generator refuses levels 3–7 and names
  why — pushers (3–7), colour tiles (3–7), shape tiles (4–7), patrol areas
  (5–7), two goals (6), fog (7). Nothing is claimed about those levels. The
  other 24 public environments are identifier-obfuscated and undocumented; the
  preregistered rule selected ls20 (`INVENTORY.md`).
- Reference 2, the replay check itself: the 342 replays were not located (see
  above), so no baseline has been compared against the plays that produced it.
  Only the lower-bound check was possible.
- The lower-bound check on the twelve levels where the search was capped, and on
  every level of the nineteen click-based environments, where the method does
  not apply at all.
- Whether the published human baselines charge human resets as actions. This is
  what would settle F9, and it needs the replays.
- Anything at all about the server-side scorer behind the official leaderboard.
  It is not observable from outside, and every statement here is about the
  public toolkit at the pinned commit.
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
5. The optima are proved against the SHIPPED LOCAL environment at the pinned
   version. That is not necessarily the environment the human study measured,
   and a baseline consistent with the local optimum says nothing about how the
   number was gathered.
6. The play probe is random and shallow: it won nothing anywhere and mostly
   stayed on level 1, so its negatives cover the states it visited and no more.
7. A truncated enumeration is a sample of a larger graph, not a survey of it:
   the sweep's negatives hold over the states actually reached, which for four
   environments is the first 150,000 that depth-first search happened to visit.
8. The harness probe replaces the model call with a scripted stub; the loop,
   `is_done`, `_sync_level_progress`, forced RESET handling and
   `choose_action` are the harness's own code.
9. The fixture game `bt11` is the toolkit's test environment, not a public
   benchmark environment; the only public environment claims are about ls20
   levels 1 and 2, whose models we wrote from obfuscated source at the rule
   level. A rule we did not see would be one the model matched anyway on every
   reachable transition, so it is either unreachable on these levels or
   invisible in position, rotation, lives, steps, pickups and status.
10. Every number in this file is registered in `docs/claims.json` and checked
   by `../audit-kit/scripts/report_check.sh`; scripts and artefacts ship in
   this repository; the audited origins have Software Heritage save requests
   accepted (`artifacts/intake/swh_snapshot.log`).
11. What a reader must still trust: Dafny 4.11.0 and its JavaScript backend,
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
.venv/bin/python scripts/play_probe.py --max-actions 20000 --max-seconds 60 --seed 0
.venv/bin/python scripts/min_actions.py --levels 1 2 3 --max-states 400000 --max-seconds 120 --max-rss-mb 2500
.venv/bin/python scripts/replay_availability.py
.venv/bin/python scripts/score_pipeline_probe.py
.venv/bin/python scripts/aggregation_probe.py
.venv/bin/python scripts/wire_probe.py
.venv/bin/python scripts/limits_probe.py
.venv/bin/python scripts/search_comparison.py --games ls20 g50t --level 1
../audit-kit/scripts/report_check.sh docs/claims.json
```

## Credit

The ARC Prize Foundation publishes the toolkit, harness, agents, report and
docs under MIT and open documentation; that openness is what makes this audit
possible. Findings are shared with them first (`notice/notice.DRAFT.md`).
Contact: ibrahimnmian@gmail.com
