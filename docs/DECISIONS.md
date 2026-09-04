# Decisions and deviations (dated)

Every change to the preregistered plan, and every judgement call made before
the plan existed, is recorded here with its date and reason.

| date | decision | reason |
|---|---|---|
| 2026-09-03 | Audit kit version used is v0.2.1 (`git describe` in `../audit-kit`: `v0.2.1-2-g2515ea8`), not v0.1.0 as the initial brief said. | The kit moved on; the initial brief was stale. Only `report_check.sh`, `archive_snapshot.sh` and the honest-limits checklist apply; the Lean gates do not. |
| 2026-09-03 | The public environment source is NOT fetched in this session. The API listing call (`/api/games`) was also refused by the session's permission layer. | Fetching runs third-party code and needs the lead author's go; the anonymous key also only unlocks 3 of 25 public games (docs: available-games), so the full inventory needs the lead author's registered key. `INVENTORY.md` is generated with explicit BLOCKED rows until then. |
| 2026-09-03 | Phase 0 order changed: the scoring rule (reference 3) is modelled and probed FIRST, offline; the environment model (reference 1) is preregistered now but built after the fetch. | The scorer is fully checkable offline from the vendored code; the environments are not yet on disk. Same back-half method, applied to the artefact that is available. |
| 2026-09-03 | Two readings of the documented per-level cap are modelled: cap on the score (prose, docs, code) and cap on the ratio before squaring (report v2 Equation 1 as typeset). | The report's own prose and equation disagree; modelling both lets the differential say which one the code implements instead of us choosing. |
| 2026-09-03 | Harness cutoff probes run the harness's real `Agent.main` loop and real `BenchmarkingAgent.is_done` / `_sync_level_progress` / `choose_action`; only the model adapter is replaced by a scripted stub, constructed the way the harness's own unit tests construct the agent (`tests/unit/test_benchmarking_agent.py`). | A re-implementation of the loop would test our copy, not theirs. |
| 2026-09-03 | Dafny 4.11.0 installed via Homebrew (free, ~5 min). Located by `DAFNY_BIN` or PATH. | Needed for the model; no Dafny was present on the machine. |
| 2026-09-03 | No `Co-Authored-By` or "generated with" trailers on any commit in this repository. | Standing company rule (no Claude attribution on anything that may become public). |
| 2026-09-03 | Fixture environment `bt11` (the toolkit's own test game, `vendor/ARC-AGI/test_environment_files/game1`) is used to validate the recorder, reset semantics and harness probes before any public environment is on disk. | It is shipped by the toolkit for exactly this purpose; it is not a public benchmark environment and is never reported as one. |
