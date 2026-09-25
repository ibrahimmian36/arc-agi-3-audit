"""The replay reader, tested on synthetic files before it meets real ones.

Every edge a recording can present is exercised here without the dataset:
an empty file, a file with one record, a truncated final line, a blank line,
a line that is not JSON in the middle of good ones, and a line large enough
that reading the file whole would be the wrong design.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from replays import shape, stream_jsonl  # noqa: E402


def write(tmp_path: Path, name: str, data: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_empty_file_yields_nothing(tmp_path):
    assert list(stream_jsonl(write(tmp_path, "e.jsonl", b""))) == []


def test_single_record(tmp_path):
    p = write(tmp_path, "one.jsonl", json.dumps({"a": 1}).encode() + b"\n")
    assert list(stream_jsonl(p)) == [(1, {"a": 1})]


def test_truncated_final_line_is_skipped_and_earlier_lines_kept(tmp_path, capsys):
    p = write(tmp_path, "t.jsonl", b'{"a": 1}\n{"a": 2}\n{"a": 3, "cut": tr')
    assert [r for _, r in stream_jsonl(p)] == [{"a": 1}, {"a": 2}]
    assert "partial final line" in capsys.readouterr().err


def test_blank_lines_are_ignored(tmp_path):
    p = write(tmp_path, "b.jsonl", b'{"a": 1}\n\n   \n{"a": 2}\n')
    assert [r for _, r in stream_jsonl(p)] == [{"a": 1}, {"a": 2}]


def test_a_bad_line_in_the_middle_loses_only_itself(tmp_path, capsys):
    p = write(tmp_path, "bad.jsonl", b'{"a": 1}\nnot json\n{"a": 3}\n')
    out = list(stream_jsonl(p))
    assert out == [(1, {"a": 1}), (3, {"a": 3})]
    assert "bad.jsonl:2" in capsys.readouterr().err


def test_line_numbers_are_the_file_s_own(tmp_path):
    p = write(tmp_path, "n.jsonl", b'\n{"a": 1}\n\n{"a": 2}\n')
    assert [n for n, _ in stream_jsonl(p)] == [2, 4]


def test_a_large_line_is_read_without_holding_the_file(tmp_path):
    """A frame-bearing record is tens of kilobytes; a file is thousands of them.
    The reader must be a generator, so memory is bounded by one line."""
    big = {"frame": [[0] * 64 for _ in range(64)] * 8, "k": "v"}
    line = json.dumps(big).encode() + b"\n"
    p = write(tmp_path, "big.jsonl", line * 50)
    gen = stream_jsonl(p)
    n, first = next(gen)
    assert n == 1 and len(first["frame"]) == 512
    assert hasattr(gen, "__next__")           # a generator, not a list


def test_shape_describes_structure_and_never_content():
    s = shape({"guid": "3f80c449-secret", "frame": [[[1, 2, 3]]], "state": "WIN", "n": 4})
    assert "3f80c449" not in s and "WIN" not in s
    assert "guid: str" in s and "frame: [1 × [1 × [3 × int]]]" in s


def test_shape_bounds_its_own_output():
    wide = {f"k{i}": i for i in range(40)}
    s = shape(wide)
    assert s.endswith("…}") and s.count(":") == 12


# ── the recording parser ────────────────────────────────────────────────────
from replays import RESET, parse_recording, per_level_counts, card_counts  # noqa: E402


def _frame(action, levels, state="NOT_FINISHED", full_reset=False, gid="ls20-9607627b"):
    return {"data": {"game_id": gid, "frame": [[[0]]], "state": state, "levels_completed": levels,
                     "win_levels": 7, "action_input": {"id": action, "data": {}},
                     "guid": "g", "full_reset": full_reset, "available_actions": [1]}}


def _card(gid, actions, abl, resets, levels, state):
    return {"data": {"won": 0, "played": 1, "total_actions": actions, "levels_completed": levels,
                     "cards": {gid: {"game_id": gid, "total_plays": 1, "guids": ["g"],
                                     "levels_completed": [levels], "states": [state],
                                     "actions": [actions], "actions_by_level": [abl],
                                     "resets": [resets], "total_actions": actions}}}}


def _run(frames):
    return parse_recording((i + 1, f) for i, f in enumerate(frames))


def test_empty_recording():
    rec = _run([])
    assert rec["game_id"] is None and rec["plays"] == [[]] and rec["card"] is None
    assert per_level_counts([])["charged"] == {}


def test_construction_reset_is_not_charged():
    rec = _run([_frame(RESET, 0), _frame(1, 0), _frame(2, 1)])
    c = per_level_counts(rec["plays"][0])
    assert c["charged"] == {0: 2} and c["uncharged"] == {0: 2} and c["resets"] == {}
    assert c["completed"] == [0]


def test_level_never_completed_is_not_credited():
    rec = _run([_frame(RESET, 0), _frame(1, 0), _frame(1, 0)])
    c = per_level_counts(rec["plays"][0])
    assert c["completed"] == [] and c["charged"] == {0: 2}


def test_one_reset_counts_charged_not_uncharged():
    frames = [_frame(RESET, 0), _frame(1, 0), _frame(1, 0, "GAME_OVER"), _frame(RESET, 0), _frame(3, 1)]
    c = per_level_counts(_run(frames)["plays"][0])
    assert c["charged"] == {0: 4} and c["uncharged"] == {0: 3} and c["resets"] == {0: 1}


def test_reset_after_win_lands_on_next_level():
    frames = [_frame(RESET, 0), _frame(1, 1), _frame(RESET, 1), _frame(1, 2, "WIN")]
    c = per_level_counts(_run(frames)["plays"][0])
    assert c["charged"] == {0: 1, 1: 2} and c["resets"] == {1: 1} and c["completed"] == [0, 1]
    assert c["final_state"] == "WIN"


def test_two_levels_in_one_frame_both_credited():
    c = per_level_counts(_run([_frame(RESET, 0), _frame(1, 2)])["plays"][0])
    assert c["completed"] == [0, 1] and c["charged"] == {0: 1}


def test_full_reset_splits_plays():
    frames = [_frame(RESET, 0), _frame(1, 1), _frame(RESET, 0, full_reset=True), _frame(1, 0)]
    rec = _run(frames)
    assert len(rec["plays"]) == 2 and len(rec["plays"][0]) == 2 and len(rec["plays"][1]) == 2
    assert per_level_counts(rec["plays"][1])["charged"] == {0: 1}


def test_card_is_recognised_and_decoded():
    gid = "ls20-9607627b"
    frames = [_frame(RESET, 0), _frame(1, 0), _frame(1, 1), _frame(RESET, 1), _frame(1, 2)]
    frames.append(_card(gid, 4, [[1, 2], [2, 4]], 1, 2, "NOT_FINISHED"))
    rec = _run(frames)
    assert rec["card"] is not None and len(rec["plays"]) == 1 and len(rec["plays"][0]) == 5
    cc = card_counts(rec["card"], gid)
    assert cc == [dict(actions=4, per_level=[2, 2], resets=1, levels_completed=2, state="NOT_FINISHED")]
    mine = per_level_counts(rec["plays"][0])
    assert [mine["charged"][l] for l in mine["completed"]] == cc[0]["per_level"]


def test_card_for_other_game_is_ignored():
    assert card_counts(_card("x", 1, [], 0, 0, "WIN")["data"], "ls20-9607627b") == []
    assert card_counts(None, "ls20-9607627b") == []


def test_non_frame_non_card_lines_are_skipped():
    rec = _run([{"data": {"note": 1}}, _frame(RESET, 0), {"timestamp": "t"}, _frame(1, 1)])
    assert len(rec["plays"][0]) == 2


def test_action_names_are_normalised():
    from replays import action_id
    assert action_id("RESET") == 0 and action_id("ACTION6") == 6 and action_id(3) == 3
    import pytest
    with pytest.raises(ValueError):
        action_id("ACTION9")


def test_old_schema_recording_is_flagged_and_counted():
    frames = [_frame("ACTION1", 0), _frame("ACTION1", 1), _frame("RESET", 1), _frame("ACTION2", 2)]
    rec = _run(frames)
    assert rec["old_schema"] is True
    c = per_level_counts(rec["plays"][0])
    # no construction line: the first action is a real one and is charged
    assert c["charged"] == {0: 2, 1: 2} and c["resets"] == {1: 1}


# ── the replay checker's classifier and trap counter (no environment needed) ─
def test_replay_classifier():
    from replay_check import classify
    full = dict(steps=10, frames_ok=10, state_ok=10)
    assert classify(full, None) == "full_default"
    assert classify(dict(steps=10, frames_ok=9, state_ok=9), full) == "full_levelonly"
    assert classify(dict(steps=10, frames_ok=9, state_ok=9), dict(steps=10, frames_ok=8, state_ok=10)) == "frame_only"
    assert classify(dict(steps=10, frames_ok=9, state_ok=9), dict(steps=10, frames_ok=8, state_ok=9)) == "divergent"
    assert classify(dict(steps=0, frames_ok=0, state_ok=0), dict(steps=0, frames_ok=0, state_ok=0)) == "divergent"


# ── the budget applied to human play (Phase 19) ─────────────────────────────
def test_human_budget_tallies_forced_and_voluntary_resets():
    from human_budget import level_tallies
    f = lambda a, l, s="NOT_FINISHED": dict(action=a, levels=l, state=s, full_reset=False, line=0)
    # construction, two moves, a death, the reset that follows it, a winning move
    assert level_tallies([f(0, 0), f(1, 0), f(1, 0, "GAME_OVER"), f(0, 0), f(2, 1)]) == [(0, 4, 1)]
    # a reset not preceded by a game over is charged but is not a forced one
    assert level_tallies([f(0, 0), f(1, 0), f(0, 0), f(2, 1)]) == [(0, 3, 0)]
    # a frame that completes two levels credits the second with nothing
    assert level_tallies([f(0, 0), f(1, 2)]) == [(0, 1, 0), (1, 0, 0)]
    # a level never completed produces no tally
    assert level_tallies([f(0, 0), f(1, 0), f(1, 0)]) == []
