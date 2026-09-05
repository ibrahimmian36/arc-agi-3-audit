#!/usr/bin/env bash
# VERBATIM COPY of scripts/report_check.sh from the Millennium Research audit kit,
# v0.2.1 (git describe: v0.2.1-2-g2515ea8), shipped here so the claims check runs
# from this repository alone. tests/test_pins.py asserts this file is byte-identical
# to the kit's whenever the kit is present, so it cannot drift.
#
# Millennium Research audit kit — report number enforcement.
#
# A report may not finalize unless every load-bearing number in it is tied
# to a shipped log. Convention: the audit ships a claims.json next to the
# report — a list of {"value": "...", "report": "path", "log": "path",
# "pattern": "regex that must match a line in log containing the value"}.
# This script verifies, for each claim: (a) the value literally appears in
# the report, (b) the pattern matches in the log, (c) the value appears on
# a matched log line. Exit 0 iff all claims verify.
#
# Usage: report_check.sh <claims.json>
set -u
[ $# -eq 1 ] || { echo "usage: report_check.sh <claims.json>"; exit 2; }

python3 - "$1" << 'EOF'
import json, re, sys, os
claims_path = sys.argv[1]
base = os.path.dirname(os.path.abspath(claims_path))
claims = json.load(open(claims_path))
fails = 0
for i, c in enumerate(claims):
    val, rep, log, pat = c["value"], c["report"], c["log"], c["pattern"]
    rp = rep if os.path.isabs(rep) else os.path.join(base, rep)
    lp = log if os.path.isabs(log) else os.path.join(base, log)
    ok, why = True, []
    try:
        if val not in open(rp, encoding="utf-8", errors="replace").read():
            ok = False; why.append(f"value not in report {rep}")
    except OSError as e:
        ok = False; why.append(f"report unreadable: {e}")
    try:
        lines = [l for l in open(lp, encoding="utf-8", errors="replace") if re.search(pat, l)]
        if not lines:
            ok = False; why.append(f"pattern not found in log {log}")
        elif not any(val in l for l in lines):
            ok = False; why.append(f"value absent from matched log lines (first match: {lines[0].strip()[:90]})")
    except OSError as e:
        ok = False; why.append(f"log unreadable: {e}")
    print(f"[{'ok' if ok else 'FAIL'}] claim {i}: {val!r} <- {log} :: {pat}"
          + ("" if ok else "  (" + "; ".join(why) + ")"))
    fails += 0 if ok else 1
print(f"REPORT CHECK: {'PASS' if fails == 0 else f'FAIL ({fails} unverified claims)'}")
sys.exit(0 if fails == 0 else 1)
EOF
