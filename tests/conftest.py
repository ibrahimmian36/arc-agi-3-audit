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
    """The history guards and the archive test read the git repository. A
    reviewer running the suite from the unpacked supplementary archive has no
    .git, and those tests say so rather than erroring."""
    import pytest, subprocess
    r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "true":
        pytest.skip("not a git checkout (e.g. the unpacked supplementary archive)")
