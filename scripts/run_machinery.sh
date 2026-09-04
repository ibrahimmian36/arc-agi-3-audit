#!/usr/bin/env bash
# Machinery checks M1-M7 on the toolkit's fixture game bt11 (docs/PREREGISTRATION.md §2),
# written as deterministic artefacts under artifacts/recorder/. M8 (byte identity) is
# tests/test_recorder.py::test_m8_byte_identity and the re-run diff in the ledger.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
ENVS="$ROOT/vendor/ARC-AGI/test_environment_files"
OUT="$ROOT/artifacts/recorder"
mkdir -p "$OUT"
S1="ACTION3,ACTION3,ACTION3,ACTION3"
rec() { "$PY" "$ROOT/scripts/record_trace.py" --environments-dir "$ENVS" --game bt11 --actions "$2" --out "$OUT/$1.json" 2>/dev/null | sed "s/^/$1 /"; }
rec m1_parity "ACTION3,ACTION3,RESET,$S1,ACTION3,ACTION3,RESET,ACTION3,ACTION3,ACTION3,ACTION3,ACTION3,ACTION3,ACTION3,ACTION3,ACTION4,ACTION4,ACTION4,ACTION4,ACTION4,ACTION4"
rec m2_reset_before_action "RESET,RESET"
rec m3_level_reset_retains_progress "$S1,ACTION3,ACTION3,RESET"
ALL=$(python3 -c "print(','.join(['ACTION3']*72))")
rec m4_reset_after_win "$ALL,RESET"
rec m5_game_over_then_reset "$S1,ACTION4,ACTION4,ACTION4,ACTION4,ACTION4,ACTION4,ACTION4,ACTION4,RESET"
rec m6_unavailable_action "ACTION1,ACTION2,ACTION5"
rec m7_never_solves "$(python3 -c "print(','.join((['ACTION4']*3+['RESET'])*7+['ACTION4','ACTION4']))")"
"$PY" - "$OUT" <<'PY'
import json, sys, pathlib
out = pathlib.Path(sys.argv[1]); files = sorted(out.glob("m*.json"))
ok = all(json.loads(f.read_text())["parity"]["counts_agree"] for f in files)
print(f"SUMMARY traces={len(files)} parity_all_agree={ok}")
PY
