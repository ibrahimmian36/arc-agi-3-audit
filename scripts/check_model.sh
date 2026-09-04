#!/usr/bin/env bash
# Hygiene + verify + compile a Dafny model into a JavaScript oracle.
# Usage: check_model.sh [model.dfy] [out_dir]   (default: model/scoring.dfy artifacts/oracle)
# Exit 0 only if: no escape constructs, Dafny reports N verified / 0 errors with
# N > 0, and the compiled oracle loads under node. Log: artifacts/oracle/check_model.log
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${1:-$ROOT/model/scoring.dfy}"
OUT="$(cd "$(dirname "${2:-$ROOT/artifacts/oracle}")" 2>/dev/null && pwd)/$(basename "${2:-$ROOT/artifacts/oracle}")"
mkdir -p "$OUT"
STEM="$(basename "$MODEL" .dfy)"
LOG="$OUT/check_model.log"
DAFNY="${DAFNY_BIN:-$(command -v dafny || true)}"
mkdir -p "$OUT"
: > "$LOG"
fail=0

echo "== hygiene scan of $(basename "$MODEL")" | tee -a "$LOG"
for pat in 'assume' '{:axiom' '{:verify false' '{:extern' 'expect '; do
  n=$(grep -c -- "$pat" "$MODEL" || true)
  echo "  pattern '$pat': $n" | tee -a "$LOG"
  [ "$n" -eq 0 ] || fail=1
done

echo "== dafny verify" | tee -a "$LOG"
[ -n "$DAFNY" ] || { echo "  dafny not found (set DAFNY_BIN)" | tee -a "$LOG"; exit 2; }
"$DAFNY" --version | sed 's/^/  dafny version: /' | tee -a "$LOG"
VOUT=$("$DAFNY" verify "$MODEL" 2>&1); rc=$?
echo "$VOUT" | tail -3 | sed 's/^/  /' | tee -a "$LOG"
SUMMARY=$(echo "$VOUT" | grep -oE '[0-9]+ verified, [0-9]+ error' | tail -1)
NV=$(echo "$SUMMARY" | awk '{print $1}'); NE=$(echo "$SUMMARY" | awk '{print $3}')
echo "  VERIFY_SUMMARY: verified=${NV:-0} errors=${NE:-?} rc=$rc" | tee -a "$LOG"
{ [ "$rc" -eq 0 ] && [ "${NE:-1}" = "0" ] && [ "${NV:-0}" -gt 0 ]; } || fail=1

echo "== dafny build --target:js" | tee -a "$LOG"
rm -f "$OUT/$STEM.js" "$OUT/$STEM-js.dtr"
cp "$MODEL" "$OUT/$STEM.dfy"
( cd "$OUT" && "$DAFNY" build --target:js --no-verify "$STEM.dfy" 2>&1 | tail -2 | sed 's/^/  /' ) | tee -a "$LOG"
if [ -f "$OUT/$STEM.js" ]; then
  python3 - "$OUT/$STEM.js" <<'PY'
import re, sys
p = sys.argv[1]; t = open(p).read()
mods = re.findall(r'^let (\w+) = \(function\(\)', t, re.M)
exp = [m for m in mods if not m.startswith('_')] + [m for m in mods if m == '_dafny']
if 'module.exports' not in t:
    t += '\nmodule.exports = { ' + ', '.join(exp) + ' };\n'
    open(p, 'w').write(t)
print('  exported modules:', ', '.join(exp))
PY
  echo '{"type": "commonjs"}' > "$OUT/package.json"
  if [ ! -d "$OUT/node_modules/bignumber.js" ]; then
    SRC="$ROOT/../intentio/node_modules/bignumber.js"
    if [ -d "$SRC" ]; then mkdir -p "$OUT/node_modules" && cp -R "$SRC" "$OUT/node_modules/bignumber.js"; echo "  bignumber.js copied from intentio" | tee -a "$LOG"
    else (cd "$OUT" && npm install --no-audit --no-fund bignumber.js >/dev/null 2>&1) && echo "  bignumber.js installed via npm" | tee -a "$LOG"; fi
  fi
  node -e 'const m=require(require("path").resolve(process.argv[1])); if(!m._dafny) throw new Error("oracle exports missing"); console.log("  oracle loads: ok")' "$OUT/$STEM.js" 2>&1 | tee -a "$LOG" || fail=1
  shasum -a 256 "$OUT/$STEM.js" | sed 's/^/  sha256 /' | tee -a "$LOG"
else
  echo "  build produced no $STEM.js" | tee -a "$LOG"; fail=1
fi
echo "MODEL CHECK: $([ $fail -eq 0 ] && echo PASS || echo FAIL)" | tee -a "$LOG"
exit $fail
