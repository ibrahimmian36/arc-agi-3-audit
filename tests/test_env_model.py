"""Reference 1 (ls20 level 1): the generated model verifies with no escape
constructs, the enumerated graph artefact is internally consistent, and the
scoped differential recorded zero disagreements. Slow parts (the enumeration,
~2 min) are not re-run here; their artefacts are checked and the trace
differential is re-run for byte identity."""
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "artifacts" / "env" / "ls20"
MODEL = ROOT / "model" / "ls20_level1.dfy"


def test_generated_model_matches_generator_output():
    before = MODEL.read_bytes()
    subprocess.run([str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "scripts" / "gen_level_model.py"), "--game", "ls20", "--level", "1"], check=True, capture_output=True)
    assert MODEL.read_bytes() == before, "model/ls20_level1.dfy was hand-edited or the generator changed"


def test_model_hygiene_and_verification():
    text = MODEL.read_text()
    for pat in ("assume", "{:axiom", "{:verify false", "{:extern", "expect "):
        assert pat not in text, pat
    p = subprocess.run([str(ROOT / "scripts" / "check_model.sh"), str(MODEL), str(ROOT / "artifacts" / "oracle_env")], capture_output=True, text=True, timeout=900)
    assert p.returncode == 0, p.stdout[-1500:]
    m = re.search(r"VERIFY_SUMMARY: verified=(\d+) errors=(\d+)", (ROOT / "artifacts" / "oracle_env" / "check_model.log").read_text())
    assert m and int(m.group(1)) >= 12 and int(m.group(2)) == 0


def test_graph_artifact_consistent():
    g = json.loads((ENV / "graph_L1.json").read_text())
    assert not g["truncated"]
    assert g["states"] == sum(g["states_by_lives"].values())
    assert g["win_reachable"] and g["win_states"] == 1
    assert g["reset_checked"] == g["reset_returns_to_start"] == 500
    assert 355.0 < g["inverse_p_win_random"] < 356.0
    edges = json.loads((ENV / "graph_L1_edges.json").read_text())
    assert len(edges["nodes"]) == g["states"] and len(edges["edges"]) == g["edges"]


def test_differential_recorded_zero_disagreements():
    d = json.loads((ENV / "differential_L1.json").read_text())
    assert d["graph_edges"]["disagreements"] == 0 and d["graph_edges"]["n"] == 56772
    assert d["traces"]["disagreements"] == 0 and d["traces"]["traces"] == 30


def test_trace_differential_byte_identical(tmp_path):
    import shutil, sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from env_probe import main as probe_main
    a = (ENV / "traces_L1.json").read_bytes(); b = (ENV / "differential_L1.json").read_bytes()
    probe_main(["--game", "ls20", "--level", "1"])
    assert (ENV / "traces_L1.json").read_bytes() == a
    assert (ENV / "differential_L1.json").read_bytes() == b


def test_enumerator_smoke_on_fixture():
    """The enumerator itself, on the toolkit's fixture game (4 actions solve level 1)."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import state_graph
    ROOT_ENVS = ROOT / "vendor" / "ARC-AGI" / "test_environment_files"
    orig = state_graph.ROOT
    try:
        # point make_game at the fixture directory
        def make_game(game, level_index):
            import logging
            from arc_agi import Arcade, OperationMode
            lg = logging.getLogger("sg"); lg.setLevel(logging.ERROR)
            arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(ROOT_ENVS), logger=lg)
            env = arc.make(game, save_recording=False)
            return env.info.game_id, env._game
        state_graph.make_game = make_game
        state_graph.ACTIONS = [3, 4]
        r = state_graph.enumerate_level("bt11", 0, 1000, 60, check_reset=True, max_reset_checks=50)
    finally:
        state_graph.ACTIONS = [1, 2, 3, 4]
    assert r["win_reachable"] and r["shortest_win_depth"] == 4 and not r["truncated"]
    assert r["reset_returns_to_start"] == r["reset_checked"] > 0
