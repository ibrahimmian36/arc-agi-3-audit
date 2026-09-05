# Preregistration — ARC-AGI-3 audit, Phase 0

Written and committed 2026-09-03 BEFORE any probe, model or differential was
run. Later changes are dated in `docs/DECISIONS.md` and disclosed in
`FINDINGS.md`.

Scope: the public ARC-AGI-3 set, the public toolkit and harness, the published
scoring rule. Not in scope, ever: the 55 semi-private and 55 private
environments, any attempt to recover, probe, scrape or infer them, anything
that violates the competition rules or licences, any agent whose purpose is to
score rather than to audit.

Reject-only: every automated component below either reports a disagreement or
reports "no disagreement". Nothing certifies.

## 0. The documented rule (what the artefacts are checked against)

Sources, pinned: technical report v2 (arXiv 2603.24621v2, revised 2026-04-17;
identified by hash in `artifacts/docs/SNAPSHOT.md`; not redistributed), docs.arcprize.org `methodology`
page (fetched 2026-09-03), the toolkit README changelog 0.9.7 (2026-04-14,
vendored at `vendor/ARC-AGI/README.md`), the human-dataset blog post
(2026-04-14).

D1 Per-level score. Report v2 §4.1 Equation (1) as typeset:
   `S = min(1.15, h/a)^2`. Report v2 prose (§4.2 "Cap the maximum per-level
   score") and the docs: the per-level score is capped at 1.15 (115%). The
   toolkit changelog 0.9.7: "level cap from 100% to 115%". Two readings:
   - D1-prose: `S = min(1.15, (h/a)^2)`  (max 115%)
   - D1-eq:    `S = (min(1.15, h/a))^2`  (max 132.25%)
   Both are modelled. The report v1 rule `min(1, h/a)^2` is superseded and is
   not a target.
D2 Human baseline h: the upper-median action count of first-time human
   players per level (report v2 §4.1; docs). Delivered per environment as
   `baseline_actions[l]` in `metadata.json` (toolkit `_download_game`).
D3 Weights: level l has weight l (1-indexed); an n-level environment has total
   weight n(n+1)/2 (report v2 §4.1; docs).
D4 Environment score: `E = min( sum_{l<=k} w_l / W , sum_l w_l S_l / W )`, k =
   number of levels completed, levels sequential, S_l = 0 for uncompleted
   levels (report v2 §4.1 and §4.2 "Per-environment cap"; docs: 4 of 5 levels
   caps at 66.7%).
D5 Total score: mean of environment scores over the set (report v2 §4.1).
D6 Action cutoff: "we impose an action budget of five times the human-baseline
   median action count per level ... the agent is terminated after 5n actions"
   (report v2 §4.3.1). The docs methodology page and competition-mode page do
   not mention it.
D7 Multiple plays: "Average of the best score for each environment" (docs
   scorecards page).
D8 Resets: humans "were allowed to reset the current level at any time"
   (report v2 §5.1). Nothing found in report or docs says whether a RESET
   counts as an action for the agent, or what GAME_OVER costs.

Where the rule is implemented (shipped artefacts under test):
- `vendor/ARC-AGI/arc_agi/scorecard.py`: `EnvironmentScoreCalculator.add_level`
  / `to_score`, `EnvironmentScorecard._calculate_score`, and the `Card`
  bookkeeping that turns a play into per-level action counts.
- `vendor/arc-agi-3-benchmarking/benchmarking/agent.py`: per-level budgets
  `ceil(baseline * MAX_ACTIONS_BASELINE_MULTIPLIER)`; `is_done` stops when the
  level counter reaches the budget; all shipped model configs set the
  multiplier to 5.0.
- `arcengine 0.9.3` (PyPI, pinned by the toolkit): `handle_reset`,
  `full_reset`, `level_reset`, `next_level`, `_set_action`.

## 1. Reference 3 — the scorer

### 1.1 Model (Dafny, `model/scoring.dfy`)

Functions `LevelScoreProse`, `LevelScoreEq`, `EnvScore(weights, scores,
completed)` over exact rationals. Properties to be VERIFIED (not tested):

- S1 `LevelScoreProse(h,a) <= 1.15`; S1' `LevelScoreEq(h,a) <= 1.3225`.
- S2 `LevelScore(h,h) = 1` (both readings).
- S3 `a1 <= a2  ==>  LevelScore(h,a1) >= LevelScore(h,a2)` (both readings).
- S4 `EnvScore <= CompletedShare(k) <= 1`.
- S5 all levels completed at exactly baseline ==> `EnvScore = 1`.
- S6 `k = 0 ==> EnvScore = 0`.

Hygiene bar: no `assume`, no `{:axiom}`, no `{:verify false}`, no `{:extern}`;
Dafny reports N verified, 0 errors, N > 0. Checked by `scripts/check_model.sh`
and `tests/test_model_hygiene.py`.

The model is compiled to JavaScript (`artifacts/oracle/scoring.js`) and called
from Node through `scripts/differential.cjs` (scrubbed environment, timeout,
console silenced, single marker line), the pattern from
`intentio/phase1/refloop/differential.cjs` and `check_reference.py`.

### 1.2 Planted traces (Card level) and predictions

Each probe plants a `Card` (the toolkit's own per-play bookkeeping: `actions`,
`actions_by_level`, `resets`, `states`, `levels_completed`) and an
`EnvironmentInfo` with `baseline_actions`, runs the shipped
`EnvironmentScorecard.from_scorecard`, and compares the environment score and
the per-level scores against the oracle under each reading. Tolerance: 1e-6
absolute on scores in [0, 132.25]. Unless stated, n = 5, baselines
`[10,10,10,10,10]`, W = 15, state WIN, single play.

| id | planted level actions | documented value | predicted shipped value | if they differ, reading |
|---|---|---|---|---|
| P1 exact baseline | [10,10,10,10,10] | E = 100; levels 100 | 100 | (agree) |
| P2a fewer than baseline | [9,10,10,10,10] | prose: L1 = 115, E = min(100, 101.0) = 100; eq: L1 = 123.46, E = 100 | L1 = 115, E = 100 | code follows prose; eq differs at level score only → documentation (equation vs prose) |
| P2b much fewer, incomplete | [5,10,10,10], L5: 20 actions, not completed, NOT_FINISHED | prose: L1 = 115, E = min(66.67, 67.67) = 66.67; eq: L1 = 132.25, E = 66.67 | 66.67 | (agree at E) |
| P2c distinguishing readings | [5,12,12,12], L5: 20 actions, not completed | prose: E = (115 + 69.444·9)/15 = 49.33; eq: E = (132.25 + 625)/15 = 50.48 | 49.33 | code follows prose; eq differs → documentation |
| P3a exactly at 5x cutoff | [50,10,10,10,10] | L1 = 4.0, E = 93.6 (the 50th action is allowed by the harness; the report's "after 5n" is read as permitting the 5n-th action) | 93.6 | (agree) |
| P3b one action over cutoff | [51,10,10,10,10] | with D6 as a scoring rule: L1 never completed, k = 0, E = 0; without D6: E = 93.59 | 93.59 (the scorer has no cutoff) | documentation: the cutoff is a harness run policy, not a scorer rule; scorecards produced outside the harness are scored without it |
| P4 reset mid-level | L1: 4 actions, RESET, 10 actions (Card actions 15); [15,10,10,10,10] | D8 silent on whether RESET counts; if it counts: L1 = 44.44, E = 96.30 | 96.30 (Card counts RESET as an action) | documentation: reset accounting unstated |
| P5 level-weight edge | [10], L2–L5 not attempted, NOT_FINISHED | E = min(1/15, 1/15)·100 = 6.667 | 6.667 (`add_level` is passed `level_idx + 1`, 1-based) | if 0 → environment-scorer defect (0-based weights); initial lead 2 |
| P6 unsolved final level | [10,10,10,10], L5: 20 actions not completed | E = min(66.67, 66.67) = 66.67 | 66.67 | (agree) |
| P7 never solves | 30 actions, 0 levels | E = 0 | 0 | (agree) |
| P8 double advance | one action completes L1 and L2: actions_by_level [(2,10),(3,20),(4,30),(5,40)], WIN, levels_completed 5 | D4 with k = 5 and L1+L2 sharing 10 actions is undefined; charitable reading L1 = 10, L2 = 0 actions → E = 100 | 66.67 (the 4th entry is paired with L4; L5 is scored as not completed although the state is WIN) | scorer edge, documentation silent; reachability in any public environment is a Phase 1 static check (`next_level()` twice in one step) |
| P9 GAME_OVER then reset | L1: 3 actions → GAME_OVER, RESET (level reset), 10 actions; Card L1 = 14 | D8 silent; if RESET counts and progress is retained: L1 = 51.02, E = 96.73 | 96.73 | documentation: GAME_OVER cost unstated |
| P10 multiple plays | play 1: [10] only; play 2: [10,10,10,10,10] | D7: 100 | 100 (`max` over runs) | (agree) |
| P11 baseline length mismatch | baselines 5, Card has 6 level entries | undefined | 0 with message "Human baseline actions size mismatch" | recorded, not a finding |

Bar: the shipped scorer agrees with D1-prose on all of P1, P2a–c, P3a, P5, P6,
P7, P10 (n = 9). Predicted disagreements: P3b (cutoff), P8 (double advance).
P4, P9 are bookkeeping facts to record, not disagreements. Three readings of
the outcome:
- All nine agree, P3b and P8 as predicted → the scorer implements the
  documented prose rule; the findings are documentation items (equation vs
  prose; cutoff location; reset and GAME_OVER accounting unstated; double
  advance unhandled). This is the expected "nothing wrong in the scorer" result
  and is written up with the same care.
- Any of the nine disagrees → read by hand; classify environment-scorer defect
  / documentation defect / our model wrong; be quickest to conclude the last.
- P8 agrees (E = 100) → our reading of `_calculate_score` was wrong; record.

### 1.3 Harness cutoff probes (fixture `bt11`, baselines [4,8,16,20,24])

The harness's real `Agent.main`, `BenchmarkingAgent.is_done`,
`_sync_level_progress`, `_forced_action_for_frame` and `choose_action` run
unmodified against the toolkit in OFFLINE mode; only the model adapter is a
scripted stub. Budgets with multiplier 5.0: [20, 40, 80, 100, 120]. The
harness forces a RESET on the first frame (NOT_PLAYED) and after GAME_OVER,
and counts both in its per-level counter. `bt11` level 1 completes after 4
consecutive ACTION3 on an 8x8 grid; a RESET after the first action is a level
reset; ACTION4 ×4 loses.

| id | script (after the forced initial RESET) | documented (D6: "terminated after 5n = 20 actions") | predicted harness | predicted Card actions on L1 |
|---|---|---|---|---|
| H1 one over | 4 × [ACTION3, ACTION3, ACTION3, RESET], then ACTION3 ×4 | 20 actions then stop | executes initial RESET + 16 + 3 = 20, refuses the 21st; L1 not completed; exit ACTION_BUDGET | 19 (the initial RESET is not counted by the Card; level RESETs are) |
| H2 exactly at | 3 × [ACTION4, ACTION4, ACTION4, RESET], ACTION4, ACTION4, RESET, then ACTION3 ×4 | the 20th action may complete the level | the 20th action completes L1; loop continues to L2 | 19 → L1 score (4/19)^2 = 4.43 |
| H4 level 2 exactly at | ACTION3 ×4 (L1), then 8 × [ACTION4, ACTION4, ACTION4, RESET], then ACTION3 ×8 | 40 | L2 completes on its 40th action | L2 = 40 → 4.0 |
| H5 level 2 one over | as H4 with one extra ACTION4 before the solving run | 40 then stop | refuses the 41st; L2 not completed | L2 = 40 |
| H6 GAME_OVER path | ACTION4 ×4 (lose), forced RESET, ACTION3 ×4 | silent | L1 completes; harness counter 10 | 9 → (4/9)^2 = 19.75 |

Reading: H1/H2 as predicted → the harness enforces the documented 5x budget per
level, one action stricter on level 1 than the scorer's count because the
mandatory initial RESET is charged to level 1 by the harness and not by the
Card. Documentation item (is the initial RESET an action?), effect ≤ 1 action
on level 1, direction: against the agent. If the harness executes 21 → harness
defect. If the harness enforces only the total → harness/documentation defect.

## 2. Machinery validation on the fixture (before any public environment)

The "right after starting" checkpoint, run on `bt11` because no public
environment is on disk yet, and re-run on the chosen public environment after
the fetch.

| id | trace | prediction |
|---|---|---|
| M1 recorder parity | scripted 25-action trace incl. 2 level RESETs | our count of non-initial actions = Card `actions`; harness counter = ours + 1 |
| M2 reset before any action | RESET, RESET | second RESET: `full_reset` true (engine `_action_count == 0`) |
| M3 level reset retains progress | solve L1, 2 actions on L2, RESET | `levels_completed` stays 1, `full_reset` false, `resets` = 1 |
| M4 reset after WIN | solve all 5, RESET | `full_reset` true; Card starts a new play (`total_plays` 2) |
| M5 GAME_OVER then RESET | ACTION4 ×4, RESET | state NOT_FINISHED, `levels_completed` unchanged, `full_reset` false |
| M6 unavailable action | ACTION1 (not in `available_actions` [3,4]) | engine accepts it, counts it as an action, state unchanged; the docs state no rule → documentation item |
| M7 never solves | 30 × ACTION4/RESET | E = 0 |
| M8 byte identity | run M1 twice | identical artefact bytes (wall-clock fields excluded from our artefacts by construction) |

## 3. Reference 1 — one public environment (built after the fetch)

Selection rule, fixed now: among the 25 public environments, the one with the
fewest lines of transition logic in its shipped `.py` that has >= 6 levels and
whose mechanic is documented in the report or docs (ls20 is documented in the
report's §"graph" discussion and is the first candidate). The choice and the
line counts go in `INVENTORY.md` (generated) before modelling.

Model properties (Dafny, verified, same hygiene bar):
- E1 every level is reachable from its start state by some action sequence.
- E2 no available action leaves the legal state space.
- E3 `level_reset` restores the level's start state; `full_reset` restores the
  game's start state; state stored outside the level (instance attributes not
  reinitialised in `on_set_level`) is called out explicitly.
- E4 determinism: two fresh instances with the same seed and the same trace
  produce identical frames and state.

Differential bar: N = 30 recorded traces (10 scripted, 20 random with seeds
0..19, length 200, OFFLINE), zero disagreements between the compiled model and
the shipped implementation on state, `levels_completed` and `full_reset` after
every action. Readings: zero disagreements → "no disagreement on N = 30" (not
a certification); a disagreement → read by hand, classify environment defect /
documentation defect / our model wrong.

## 4. Reference 2 — human baselines

Questions, answered from artefacts only: are per-level baselines recoverable
(prediction: yes, `metadata.json.baseline_actions` after the fetch; the docs
API schema for `/api/games` omits the field while the toolkit reads it, to be
checked on the real response); what statistic they are (documented: upper
median of first-time players; the report v1 said second-best); do they replay
(the human-dataset post says 342 replays across 25 environments were released;
locating and replaying them is Phase 1, only if the recordings are public and
their licence permits).

## 5. Numbers and artefacts

Every number above and in `FINDINGS.md` is produced by a script into
`artifacts/` and registered in `docs/claims.json`; `audit-kit/scripts/report_check.sh`
must pass on the final state. Re-runs must be byte-identical.
