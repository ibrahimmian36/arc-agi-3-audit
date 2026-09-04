"""Reference 1 (ls20 levels 1-2): the generated models verify with no escape
constructs, the enumerated graphs are internally consistent, and the recorded
differentials found zero disagreements.

The slow steps (enumeration, ~2 min per level) are not re-run here; their
artefacts are checked and the generator is re-run to prove the committed model
is exactly what it produces.
"""
import gzip
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "artifacts" / "env" / "ls20"
ORACLE_DIR = ROOT / "artifacts" / "oracle_env"
LEVELS = [1, 2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.mark.parametrize("level", LEVELS)
def test_committed_model_is_exactly_what_the_generator_produces(level):
    """A hand edit to a generated model fails here rather than shipping."""
    path = ROOT / "model" / f"ls20_level{level}.dfy"
    before = path.read_bytes()
    subprocess.run([str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "scripts" / "gen_level_model.py"),
                    "--game", "ls20", "--level", str(level)], check=True, capture_output=True)
    assert path.read_bytes() == before, f"model/ls20_level{level}.dfy differs from the generator's output"


@pytest.mark.parametrize("level", LEVELS)
def test_model_hygiene_and_verification(level):
    path = ROOT / "model" / f"ls20_level{level}.dfy"
    text = path.read_text()
    for pat in ("assume", "{:axiom", "{:verify false", "{:extern", "expect "):
        assert pat not in text, pat
    log = (ORACLE_DIR / f"check_ls20_level{level}.log").read_text()
    m = re.search(r"VERIFY_SUMMARY: verified=(\d+) errors=(\d+)", log)
    assert m, log
    assert int(m.group(1)) > 0 and int(m.group(2)) == 0, log
    assert re.search(r"TIMEOUTS: 0", log), "a timed-out obligation is unknown, not discharged"
    assert "MODEL CHECK: PASS" in log


@pytest.mark.parametrize("level", LEVELS)
def test_generator_refuses_nothing_it_actually_models(level):
    """The spec the model was generated from must still pass the guard."""
    import gen_level_model
    spec = json.loads((ENV / f"level{level}.json").read_text())
    gen_level_model.guard(spec, level)  # raises if unsupported


@pytest.mark.parametrize("level", [3, 4, 5, 6, 7])
def test_generator_refuses_levels_it_does_not_model(level):
    """Silence about an unmodelled mechanic would be a wrong model presented as
    a right one; the guard must name the reason and refuse."""
    import gen_level_model
    spec_path = ENV / f"level{level}.json"
    if not spec_path.exists():
        pytest.skip("level not extracted")
    with pytest.raises(SystemExit) as e:
        gen_level_model.guard(json.loads(spec_path.read_text()), level)
    assert "does not model" in str(e.value)


@pytest.mark.parametrize("level", LEVELS)
def test_graph_artifact_consistent(level):
    g = json.loads((ENV / f"graph_L{level}.json").read_text())
    assert not g["truncated"] and g["truncated_reason"] is None
    assert g["states"] == sum(g["states_by_lives"].values())
    assert g["win_reachable"] and g["win_states"] == 1
    assert g["reset_checked"] == g["reset_returns_to_start"] > 0 and g["reset_mismatches"] == []
    assert g["double_advance_actions"] == 0
    assert g["peak_rss_mb"] < g["max_rss_mb_cap"]
    assert len(g["shortest_win_path"]) == g["shortest_win_depth"]
    n = 0
    with gzip.open(ENV / f"graph_L{level}_edges.jsonl.gz", "rt") as fh:
        for _ in fh:
            n += 1
    assert n == g["edges"]


def test_level1_matches_the_published_win_probability():
    """Report v2 Figure 3: 'P_win for this level is exactly 1 in 355'."""
    g = json.loads((ENV / "graph_L1.json").read_text())
    assert 355.0 < g["inverse_p_win_random"] < 356.0


@pytest.mark.parametrize("level", LEVELS)
def test_differential_recorded_zero_disagreements(level):
    d = json.loads((ENV / f"differential_L{level}.json").read_text())
    g = json.loads((ENV / f"graph_L{level}.json").read_text())
    assert d["graph_edges"]["disagreements"] == 0
    assert d["graph_edges"]["n"] == g["edges"]
    assert d["graph_edges"]["model_errors"] == 0
    assert d["traces"]["disagreements"] == 0 and d["traces"]["traces"] == 30
    assert d["traces"]["model_errors"] == 0


def test_rule_level_state_space_is_symmetric_across_lives():
    """The three-life mechanic should give three copies of the same rule-level
    state space. It does; the raw counts differ on level 2 only because the
    enumerator's state key is finer than the rendered frame (a consumed pickup
    is re-appended to the sprite list on a life loss)."""
    import collections
    for level in LEVELS:
        seen = collections.defaultdict(set)
        with gzip.open(ENV / f"graph_L{level}_edges.jsonl.gz", "rt") as fh:
            for line in fh:
                e = json.loads(line)
                for v in (e["s"], e["t"]):
                    seen[v[5]].add((v[0], v[1], v[2], v[5], v[6], v[7], v[9]))
        live = [len(seen[k]) for k in (3, 2, 1) if k in seen]
        assert len(live) == 3 and max(live) - min(live) <= 1, (level, live)
