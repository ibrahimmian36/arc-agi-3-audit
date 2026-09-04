"""The vendored clones are exactly the pinned commits; an audit on moved code is not the audit that was preregistered."""
import json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_vendor_clones_match_pins():
    pins = json.loads((ROOT / "vendor" / "PINS.json").read_text())["commits"]
    for repo, sha in pins.items():
        head = subprocess.check_output(["git", "-C", str(ROOT / "vendor" / repo), "rev-parse", "HEAD"], text=True).strip()
        assert head == sha, repo
