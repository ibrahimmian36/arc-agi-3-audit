#!/usr/bin/env bash
# Rebuild the vendored public repositories at the commits pinned in
# vendor/PINS.json. They are not redistributed here: this fetches them from
# their own upstreams, so a reader reproduces from the same sources we did.
#
# Idempotent. Run before the test suite or either checker: some evidence lives
# in these trees rather than in artifacts/, so the checkers need them present.
set -euo pipefail
cd "$(dirname "$0")/.."
PINS=vendor/PINS.json
[ -f "$PINS" ] || { echo "missing $PINS" >&2; exit 1; }

fetch() {
  local name="$1" url="$2"
  local sha
  sha=$(python3 -c "import json;print(json.load(open('$PINS'))['commits']['$name'])")
  if [ -d "vendor/$name/.git" ]; then
    local have
    have=$(git -C "vendor/$name" rev-parse HEAD)
    if [ "$have" = "$sha" ]; then echo "ok       $name $sha"; return; fi
    echo "repin    $name $have -> $sha"
  else
    echo "clone    $name $sha"
    git init -q "vendor/$name"
    git -C "vendor/$name" remote add origin "$url"
  fi
  # Depth 1 at the exact commit: the whole history is neither needed nor small.
  git -C "vendor/$name" fetch -q --depth 1 origin "$sha"
  git -C "vendor/$name" checkout -q --detach FETCH_HEAD
  echo "at       $name $(git -C "vendor/$name" rev-parse HEAD)"
}

fetch ARC-AGI                https://github.com/arcprize/ARC-AGI.git
fetch arc-agi-3-benchmarking https://github.com/arcprize/arc-agi-3-benchmarking.git
fetch ARC-AGI-3-Agents       https://github.com/arcprize/ARC-AGI-3-Agents.git
echo "vendor ready; pins asserted by tests/test_pins.py"
