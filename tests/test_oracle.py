"""The compiled oracle reproduces the hand-computed documented values in
docs/PREREGISTRATION.md §1.2. A failure here means the model or the hand
arithmetic is wrong, never the shipped scorer."""
import json
from pathlib import Path

import pytest
from scorer_probe import run_oracle

ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "artifacts" / "oracle" / "scoring.js"
B = [10, 10, 10, 10, 10]
CASES = [
    ("P1", [10, 10, 10, 10, 10], [True] * 5, {"prose_nocut": 100.0, "eq_nocut": 100.0, "prose_cut": 100.0}),
    ("P2a", [9, 10, 10, 10, 10], [True] * 5, {"prose_nocut": 100.0, "eq_nocut": 100.0}),
    ("P2c", [5, 12, 12, 12, 20], [True, True, True, True, False], {"prose_nocut": 49.333333333, "eq_nocut": 50.483333333}),
    ("P3a", [50, 10, 10, 10, 10], [True] * 5, {"prose_nocut": 93.6, "prose_cut": 93.6}),
    ("P3b", [51, 10, 10, 10, 10], [True] * 5, {"prose_nocut": 93.589645012, "prose_cut": 0.0}),
    ("P5", [10, 0, 0, 0, 0], [True, False, False, False, False], {"prose_nocut": 6.666666667}),
    ("P6", [10, 10, 10, 10, 20], [True, True, True, True, False], {"prose_nocut": 66.666666667}),
    ("P7", [30, 0, 0, 0, 0], [False] * 5, {"prose_nocut": 0.0}),
    ("P9", [14, 10, 10, 10, 10], [True] * 5, {"prose_nocut": 96.734693878}),
]


@pytest.fixture(scope="module")
def oracle_rows(tmp_path_factory):
    assert ORACLE.exists(), "run scripts/check_model.sh first"
    fx = tmp_path_factory.mktemp("fx") / "fixtures.json"
    fx.write_text(json.dumps([dict(id=i, baselines=B, actions=a, completed=c) for i, a, c, _ in CASES]))
    out = run_oracle(ORACLE, fx)
    assert out["loaded"], out.get("error")
    return {r["id"]: r["readings"] for r in out["rows"]}


@pytest.mark.parametrize("cid,actions,completed,expect", CASES, ids=[c[0] for c in CASES])
def test_documented_values(oracle_rows, cid, actions, completed, expect):
    for reading, val in expect.items():
        got = float(oracle_rows[cid][reading]["env"]["pct"])
        assert abs(got - val) < 1e-6, (cid, reading, got, val)


def test_level_cap_readings_differ_only_above_baseline(oracle_rows):
    lv = oracle_rows["P2a"]
    assert float(lv["prose_nocut"]["levels"][0]["pct"]) == pytest.approx(115.0)
    assert float(lv["eq_nocut"]["levels"][0]["pct"]) == pytest.approx(123.456790123, abs=1e-6)
    assert float(lv["prose_nocut"]["levels"][1]["pct"]) == pytest.approx(100.0)
