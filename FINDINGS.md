# FINDINGS — ARC-AGI-3 public-set audit, Phase 0 (scorer, harness, machinery)

Millennium Research, 2026-09-03. Status: the scoring rule (reference 3) and
the benchmarking harness's action budget are audited and written up below;
the environment model (reference 1) and the human-baseline replay (reference
2) are preregistered but BLOCKED on the one-time fetch of the public
environment source (see "Not done").

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

- Reference 1 (environment model, E1–E4, N = 30 traces) and the environment
  selection: the public environment source is not on disk. Fetching it
  downloads and executes third-party code with the ARC API, needs the lead author's go
  and her registered key (the anonymous key unlocks 3 of 25 public games), and
  the API call was also refused by this session's permission layer.
  `INVENTORY.md` carries explicit BLOCKED rows. Command for the lead author is in the
  status message.
- Reference 2 (baselines): recoverable per level from `metadata.json` once
  fetched; the statistic is documented (upper median of first-time players;
  the report v1 said second-best); the human replays (342 across the 25 public
  environments per the 2026-04-14 post) were not located or downloaded.
- F3's reachability in any public environment.
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
   benchmark environment; nothing about any public environment is claimed.
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
../audit-kit/scripts/report_check.sh docs/claims.json
```

## Credit

The ARC Prize Foundation publishes the toolkit, harness, agents, report and
docs under MIT and open documentation; that openness is what makes this audit
possible. Findings are shared with them first (`notice/notice.DRAFT.md`).
Contact: ibrahimnmian@gmail.com
