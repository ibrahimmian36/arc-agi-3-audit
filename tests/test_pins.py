"""The vendored clones are exactly the pinned commits; an audit on moved code is not the audit that was preregistered."""
import json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_vendor_clones_match_pins():
    pins = json.loads((ROOT / "vendor" / "PINS.json").read_text())["commits"]
    for repo, sha in pins.items():
        head = subprocess.check_output(["git", "-C", str(ROOT / "vendor" / repo), "rev-parse", "HEAD"], text=True).strip()
        assert head == sha, repo


def test_a_fresh_clone_can_rebuild_the_vendored_trees():
    """The repository claims reproducibility. Found in the Phase 10 clean-clone
    pass: `vendor/` is deliberately not redistributed, one claim's evidence
    lives there, and nothing rebuilt it. The setup script closes that, and
    Reproduce must name it as the first step or the gap silently returns."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "setup_vendor.sh"
    assert script.exists(), "scripts/setup_vendor.sh is missing"
    body = script.read_text()
    pins = json.loads((root / "vendor" / "PINS.json").read_text())["commits"]
    for name in pins:
        assert name in body, f"{name} is pinned but not fetched by the setup script"
    assert "--depth 1" in body, "the clone must stay shallow"
    reproduce = (root / "FINDINGS.md").read_text()
    reproduce = reproduce[reproduce.index("## Reproduce"):]
    first = [l for l in reproduce.splitlines()
             if l.startswith((".venv/", "scripts/", "bash scripts/"))]
    assert first and first[0] == "bash scripts/setup.sh", \
        "the bootstrap must be the first command in Reproduce"
    assert "bash scripts/setup_vendor.sh" in (root / "scripts" / "setup.sh").read_text(), \
        "the bootstrap must fetch the vendored sources"


def test_the_shipped_claims_checker_is_the_kit_s_own():
    """scripts/report_check.sh is a verbatim copy of the audit kit's checker,
    shipped so a stranger can run it. It must never drift from the original:
    whenever the kit is present beside this repository, the two are compared
    byte for byte below the header that records the copy's origin."""
    from conftest import require_git_checkout
    require_git_checkout()
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    ours = (root / "scripts" / "report_check.sh").read_text().splitlines()
    kit = root.parent / "audit-kit" / "scripts" / "report_check.sh"
    body_start = next(i for i, l in enumerate(ours) if l.startswith("# Millennium Research audit kit"))
    assert body_start > 0, "the origin header is missing"
    if not kit.exists():
        import pytest
        pytest.skip("audit kit not present beside the repository; cannot compare")
    theirs = kit.read_text().splitlines()
    assert ours[body_start:] == theirs[1:], "scripts/report_check.sh has drifted from the kit"
