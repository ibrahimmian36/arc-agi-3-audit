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
    """The private address is assembled from parts here on purpose. Writing it
    out would put it in a repository that is released with the paper, which is
    the very thing this test exists to prevent."""
    text = (PAPER / "main.tex").read_text()
    private = "redacted@example.org"
    assert private not in text
    assert "ibrahimnmian@gmail.com" not in text or "millenniumresearch.ai" in text
    for word in ("Claude", "Anthropic", "Generated with", "Co-Authored"):
        assert word not in text, word


def test_the_paper_does_not_claim_a_disclosure_that_did_not_happen():
    """The paper once said findings were reported to the Foundation before
    publication. They were not: it is published without prior private notice.
    That sentence must never come back without someone deliberately doing it,
    because a false disclosure claim would discredit every honest finding here.
    The test asserts the paper states the true position and asserts a reason for
    it, rather than merely deleting the claim."""
    text = (PAPER / "main.tex").read_text()
    assert "[DATE]" not in text, "the disclosure placeholder is back"
    assert "without prior private notice" in text, \
        "the paper must state that it is published without prior notice"
    for claim in ("were reported to the ARC Prize Foundation",
                  "reported to the Foundation before publication",
                  "disclosed to the ARC Prize Foundation"):
        assert claim not in text, f"false disclosure claim present: {claim}"
    # The stated reason must survive too: everything audited is already public.
    assert "already public" in text


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
