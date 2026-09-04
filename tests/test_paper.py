"""The paper's figures must trace to the artefacts, and the paper must build.

A number in a published paper that no longer matches the log that produced it is
the worst failure this project can have, so it is a test rather than a habit.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"


def test_every_figure_in_the_paper_traces_to_an_artefact():
    p = subprocess.run([sys.executable, str(PAPER / "verify_numbers.py")],
                       capture_output=True, text=True, cwd=str(PAPER), timeout=300)
    assert p.returncode == 0, p.stdout[-3000:]
    assert "PAPER CHECK: PASS" in p.stdout


def test_the_paper_names_no_private_address_and_no_tool_attribution():
    text = (PAPER / "main.tex").read_text()
    assert "REDACTED" not in text
    for word in ("Claude", "Anthropic", "Generated with", "Co-Authored"):
        assert word not in text, word


def test_the_disclosure_placeholder_is_still_present_or_filled_with_a_date():
    """The paper states that findings were reported to the Foundation before
    publication. That sentence must not ship with an unfilled placeholder
    silently removed, nor be true only by assertion: either the marker is there,
    so nobody can post it by accident, or a real date replaced it."""
    import re
    text = (PAPER / "main.tex").read_text()
    assert "team@arcprize.org" in text
    line = [l for l in text.splitlines() if "before publication" in l or "[DATE]" in l]
    assert line, "the disclosure sentence is missing"
    joined = " ".join(line)
    assert "[DATE]" in joined or re.search(r"\d{1,2}\s+\w+\s+2026", joined), \
        "the disclosure date is neither a visible placeholder nor a real date"


def test_the_repository_claim_is_not_made_before_the_repository_exists():
    """The paper says its artefacts are reproducible from a released repository.
    The audit repository is private until the lead author releases it, so the URL must stay
    a visible placeholder until it is real -- a paper that claims a public
    artefact nobody can fetch is worse than one that claims nothing."""
    import re
    text = (PAPER / "main.tex").read_text()
    assert "[REPOSITORY URL]" in text or re.search(r"https?://\S+", text.split("released with this paper")[1][:200]), \
        "the repository claim names neither a placeholder nor a URL"


@pytest.mark.skipif(shutil.which("tectonic") is None, reason="no LaTeX toolchain")
def test_the_paper_compiles(tmp_path):
    for f in ("main.tex",):
        shutil.copy(PAPER / f, tmp_path / f)
    p = subprocess.run(["tectonic", "-X", "compile", "main.tex"],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=900)
    assert p.returncode == 0, p.stderr[-2000:]
    assert (tmp_path / "main.pdf").stat().st_size > 40_000
