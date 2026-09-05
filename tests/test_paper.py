"""The paper's figures must trace to the artefacts, and the paper must build.

A number in a published paper that no longer matches the log that produced it is
the worst failure this project can have, so it is a test rather than a habit.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import paper_source, require_named_paper

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
    require_named_paper()
    text = paper_source().read_text()
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
    text = paper_source().read_text()
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
    The audit repository was private until release, so the URL had to stay
    a visible placeholder until it is real -- a paper that claims a public
    artefact nobody can fetch is worse than one that claims nothing."""
    require_named_paper()
    import re
    text = paper_source().read_text()
    assert "[REPOSITORY URL]" in text or re.search(r"https?://\S+", text.split("released with this paper")[1][:200]), \
        "the repository claim names neither a placeholder nor a URL"


@pytest.mark.skipif(shutil.which("tectonic") is None, reason="no LaTeX toolchain")
def test_the_paper_compiles(tmp_path):
    require_named_paper()
    for f in ("main.tex",):
        shutil.copy(PAPER / f, tmp_path / f)
    p = subprocess.run(["tectonic", "-X", "compile", "main.tex"],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=900)
    assert p.returncode == 0, p.stderr[-2000:]
    assert (tmp_path / "main.pdf").stat().st_size > 40_000


def test_the_consistency_check_passes():
    """Every number in the paper traces to an artefact or carries a written
    exemption, the documents agree, and no superseded wording survives."""
    import subprocess, sys
    r = subprocess.run([sys.executable, str(PAPER / "consistency_check.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_exemption_carries_a_reason_that_could_be_wrong():
    """An exemption table is only worth having if its reasons are specific. A
    reason must name what the number is, not merely assert that it is fine."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("cc", PAPER / "consistency_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for number, reason in m.EXEMPT.items():
        assert len(reason) > 20, (number, reason)
        assert not reason.lower().startswith(("fine", "ok", "safe", "harmless")), number


def test_the_quoted_baseline_vector_matches_the_fetched_api_response():
    """The paper quotes ar25's published baselines. They are exempted from the
    number check as quotation, so the quotation itself must be checked."""
    import json, re
    text = (PAPER / "main.txt").read_text()
    m = re.search(r"ar25 is \[([0-9, ]+)\]", text)
    assert m, "the ar25 baseline vector is no longer quoted; drop its exemptions"
    quoted = [int(x) for x in m.group(1).split(",")]
    api = json.loads((PAPER.parent / "artifacts" / "api" / "games.json").read_text())
    real = [g["baseline_actions"] for g in api if g["game_id"].startswith("ar25")][0]
    assert quoted == real, (quoted, real)


def test_the_paper_makes_no_claim_about_the_server():
    text = paper_source().read_text().lower()
    for bad in ("the server does charge", "the server counts", "the server enforces",
                "the leaderboard is wrong", "models are scored wrongly"):
        assert bad not in text, bad


def test_the_git_history_carries_no_attribution_trailer():
    """The repository is published under its authors' names alone. A trailer
    reintroduced by tooling would ship in the history rather than the paper,
    where no reader of the PDF would ever see it, so it is checked here."""
    from conftest import require_git_checkout
    require_git_checkout()
    import subprocess
    log = subprocess.run(["git", "log", "--format=%an <%ae>%n%b"],
                         cwd=PAPER.parent, capture_output=True, text=True)
    assert log.returncode == 0, log.stderr
    for line in log.stdout.splitlines():
        low = line.lower()
        assert not low.startswith("co-" + "authored-by: cla" + "ude"), line
        assert "generated with [cla" + "ude" not in low, line


def test_the_git_history_carries_no_private_address():
    """The local part alone is enough to reconstruct the address on a repository
    owned under a known handle, so it is kept out of history, not just out of
    the working tree. Split here so this file never contains it either."""
    from conftest import require_git_checkout
    require_git_checkout()
    import subprocess
    needle = "redacted"
    log = subprocess.run(["git", "log", "--all", "-p"], cwd=PAPER.parent,
                         capture_output=True, text=True, errors="ignore")
    assert log.returncode == 0, log.stderr
    assert needle not in log.stdout, "the private address is recoverable from history"
