#!/usr/bin/env bash
# One-command bootstrap for a fresh clone.
#
#   scripts/setup.sh
#
# Fetches the audited repositories at their pinned commits, creates .venv on
# Python 3.12, installs the pinned dependencies and the toolkit (editable, from
# vendor/ARC-AGI), and verifies every import the scripts and tests need. Exit 0
# means `.venv/bin/python -m pytest -q` will run.
#
# Optional tools, not installed here: Dafny (to re-verify the models; their
# artefacts are committed), node (to load the compiled oracles), tectonic (to
# rebuild the PDFs), and poppler's pdftotext (for the anonymity tests).
set -euo pipefail
cd "$(dirname "$0")/.."

# Invoked through bash: a zip archive does not preserve execute bits, and a
# reviewer unpacking the supplementary material must still be able to run this.
bash scripts/setup_vendor.sh

if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 .venv
  else
    python3.12 -m venv .venv
  fi
fi

# uv-created environments carry no pip; use whichever installer is present.
if command -v uv >/dev/null 2>&1; then
  uv pip install --python .venv/bin/python -q -r requirements.txt
  uv pip install --python .venv/bin/python -q --no-deps -e vendor/ARC-AGI
else
  .venv/bin/python -m pip install -q -r requirements.txt
  .venv/bin/python -m pip install -q --no-deps -e vendor/ARC-AGI
fi

.venv/bin/python - <<'PY'
import importlib, sys
sys.path.insert(0, "vendor/arc-agi-3-benchmarking")
for m in ("arc_agi", "arcengine", "numpy", "pytest", "requests", "yaml",
          "pydantic", "benchmarking.agent", "benchmarking.base"):
    importlib.import_module(m)
import arcengine, arc_agi
print(f"ok: arcengine {arcengine.__version__ if hasattr(arcengine, '__version__') else '0.9.3'}, "
      f"arc_agi from {arc_agi.__file__.split('/vendor/')[-1].split('/')[0]}, "
      f"python {sys.version.split()[0]}")
PY
echo "setup complete: .venv/bin/python -m pytest -q"
