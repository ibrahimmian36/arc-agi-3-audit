import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
FIXTURE_ENVS = ROOT / "vendor" / "ARC-AGI" / "test_environment_files"

PUBLIC_ENVS = ROOT / "environment_files"


def require_public_environments():
    """The 25 public environments are fetched with an ARC API key by
    scripts/fetch_public_envs.py and are deliberately not redistributed. A
    fresh clone does not have them; tests that replay them say so rather than
    failing as if the repository were broken."""
    import pytest
    if not PUBLIC_ENVS.exists() or not any(PUBLIC_ENVS.iterdir()):
        pytest.skip("public environments not fetched (scripts/fetch_public_envs.py needs ARC_API_KEY)")


def require_git_checkout():
    """The history guards read the git repository; outside a checkout they
    say so rather than erroring."""
    import pytest, subprocess
    r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "true":
        pytest.skip("not a git checkout ")


def paper_source():
    return ROOT / "paper" / "main.tex"


def require_named_paper():
    import pytest
    if not (ROOT / "paper" / "main.tex").exists():
        pytest.skip("paper source absent")


def require_oracle():
    """The compiled oracles need node and bignumber.js, which
    scripts/check_model.sh installs beside them and which are not tracked."""
    import pytest, shutil
    if shutil.which("node") is None:
        pytest.skip("node not available")
    if not (ROOT / "artifacts" / "oracle" / "node_modules" / "bignumber.js").exists():
        pytest.skip("oracle runtime not installed (bash scripts/check_model.sh installs bignumber.js)")


def require_dafny():
    import pytest, shutil, os
    if shutil.which(os.environ.get("DAFNY_BIN", "dafny")) is None:
        pytest.skip("dafny not available (the models' artefacts are committed)")
