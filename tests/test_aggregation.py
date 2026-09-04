"""Which code path scores a run, and what happens to the denominator.

These decide the scope of the audit's aggregation finding, so they are asserted
rather than described. No test here opens a socket: the remote paths are
exercised with a transport that raises on any request.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGG = ROOT / "artifacts" / "aggregation"
sys.path.insert(0, str(ROOT / "scripts"))

import aggregation_probe as AP  # noqa: E402
from score_pipeline_probe import MOVE, linear_play  # noqa: E402

B5 = [10, 10, 10, 10, 10]


def test_local_and_remote_modes_are_identified_by_running_them():
    """offline and normal compute the score locally; online and competition
    fetch it. The official harness constructs the toolkit in online mode, so the
    local arithmetic never runs for an official run -- which is the real reason
    the finding does not reach it, and a stronger one than full-set coverage."""
    rows = {r["mode"]: r["score_produced_by"] for r in AP.mode_table()}
    assert set(rows) == {"offline", "normal", "online", "competition"}
    assert rows["offline"].startswith("local") and rows["normal"].startswith("local")
    assert rows["online"].startswith("remote") and rows["competition"].startswith("remote")


def test_the_official_harness_uses_the_remote_mode():
    """Read from the harness itself rather than asserted in prose."""
    swarm = (ROOT / "vendor" / "arc-agi-3-benchmarking" / "benchmarking" / "swarm.py").read_text()
    assert "Arcade(operation_mode=OperationMode.ONLINE)" in swarm


def test_the_toolkits_quickstart_uses_the_local_mode_and_prints_the_score():
    """The exposure is not hypothetical: the toolkit's own minimal example
    constructs Arcade() -- the default, which is normal -- plays one game and
    prints scorecard.score."""
    readme = (ROOT / "vendor" / "ARC-AGI" / "README.md").read_text()
    example = readme.split("Minimal Example")[1].split("Rendering Options")[0]
    assert "arc_agi.Arcade()" in example
    assert "get_scorecard()" in example and "scorecard.score" in example
    assert "operation_mode" not in example


def test_an_environment_that_produces_no_card_leaves_the_denominator():
    perfect = linear_play([10] * 5)
    three = ("aa00", "bb00", "cc00")
    r = AP.build({g: [perfect] for g in three}, list(three) + ["dd00"], {})
    assert len(r["environments"]) == 3, "the fourth environment produced no card"
    assert r["total"] == pytest.approx(100.0)
    assert sum(r["environments"].values()) / 4 == pytest.approx(75.0)


def test_an_environment_that_scores_zero_stays_in_the_denominator():
    """The distinction the finding turns on: a card that exists and scores zero
    is counted, a card that never exists is not."""
    perfect = linear_play([10] * 5)
    nothing = [dict(action=MOVE, levels=0) for _ in range(20)]
    three = ("aa00", "bb00", "cc00")
    r = AP.build({**{g: [perfect] for g in three}, "dd00": [nothing]},
                 list(three) + ["dd00"], {})
    assert len(r["environments"]) == 4
    assert r["total"] == pytest.approx(75.0)


def test_an_environment_opened_but_never_played_stays_in_the_denominator():
    perfect = linear_play([10] * 5)
    three = ("aa00", "bb00", "cc00")
    r = AP.build({g: [perfect] for g in three}, list(three) + ["dd00"], {}, start_only=("dd00",))
    assert len(r["environments"]) == 4 and r["total"] == pytest.approx(75.0)


def test_zero_environments_scores_zero_without_dividing_by_zero():
    r = AP.build({}, [], {})
    assert r["total"] == 0.0 and r["environments"] == {}


def test_a_version_only_difference_in_the_game_id_scores_zero_with_a_message():
    r = AP.build({"aa00-v1": [linear_play([10] * 5)]}, ["aa00-v2"], {"aa00-v2": B5})
    assert r["environments"]["aa00-v1"] == 0.0
    assert "No Matching EnvironmentInfo" in (r["messages"]["aa00-v1"] or "")
    control = AP.build({"aa00-v1": [linear_play([10] * 5)]}, ["aa00-v1"], {"aa00-v1": B5})
    assert control["environments"]["aa00-v1"] == pytest.approx(100.0)


def test_two_plays_sharing_a_guid_are_not_merged():
    """A negative worth keeping: the card resolves a guid by scanning backwards,
    which could have merged two runs. It does not."""
    p = [q for q in AP.secondary_probes() if q["id"] == "S3"][0]
    r = AP.run_secondary(p)
    assert r["total_plays"] == 2
    assert len(r["actions"]) == 2 and r["actions"][0] != r["actions"][1]


def test_probe_artefacts_are_reproducible(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    AP.main(["--out", str(a)]); AP.main(["--out", str(b)])
    assert (a / "aggregation.json").read_bytes() == (b / "aggregation.json").read_bytes()
    assert (a / "aggregation.log").read_bytes() == (b / "aggregation.log").read_bytes()


def test_committed_artefact_matches_the_script():
    d = json.loads((AGG / "aggregation.json").read_text())
    d3 = [r for r in d["denominator"] if r["id"] == "D3"][0]
    assert d3["environments_in_scorecard"] == 3 and d3["set_size"] == 4
    assert d3["toolkit_total"] == pytest.approx(100.0)
    assert d3["documented_total"] == pytest.approx(75.0)
    modes = {r["mode"]: r["score_produced_by"] for r in d["modes"]}
    assert modes["online"].startswith("remote")
