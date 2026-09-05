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
