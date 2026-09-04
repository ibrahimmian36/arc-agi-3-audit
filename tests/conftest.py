import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
FIXTURE_ENVS = ROOT / "vendor" / "ARC-AGI" / "test_environment_files"
