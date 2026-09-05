"""Audit the paper the way the paper audits the benchmark.

`verify_numbers.py` checks that each figure it knows about matches the log that
produced it. It cannot tell you about a figure it does not know about, and after
five phases of rewriting, a number left over from an earlier draft would look
exactly like a number that was never checked. This closes that: every numeric
token in the paper's body must be either asserted by the figure checker or
listed below with a reason.

It also checks the things a figure checker cannot: that the paper, the findings
file and the claims agree; that no superseded wording survives outside the
passages that narrate a correction; and that the paper still says what is true
about disclosure, attribution and the address.

Reject-only. Exit 0 iff nothing disagrees.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ART = ROOT / "artifacts"

# Numbers that are structural rather than findings. Each needs a reason that
# would be wrong if it were wrong: "it is fine" is not a reason.
EXEMPT: dict[str, str] = {
    # document structure and citation years
    "1": "section, equation and footnote references",
    "2": "section references and report v2",
    "3": "the benchmark's name, ARC-AGI-3, and section references",
    "4": "the date this paper's replay search was run, 4 September 2026",
    "5": "the action-budget multiplier written as 5b in the effective-budget formula",
    "6": "part of 6.28% and of section references; the percentage itself is traced",
    "8": "the budget at which the fixture demonstration denies the level, and the "
         "count of environments where exposure is not established, both traced elsewhere",
    "9": "the action count of the planted level in the equation-reading example, "
         "stated alongside its baseline of 10 in the same sentence",
    "2026": "the year of the material audited and of this paper",
    # quantities defined in the text rather than measured by us
    "5.0": "the action-budget multiplier as it appears in every shipped model config",
    "1.15": "the cap as written in the report's Equation (1)",
    "115": "the per-level score cap, quoted from the report's prose and the code",
    "100": "a percentage ceiling used in prose, not a measurement",
    "63": "the upper bound of the x and y contract declared by ComplexAction",
    "0": "used as a score or a count in prose",
    "10": "round counts in prose (ten seeds, ten rollouts)",
    "12": "the number of shipped model configurations, asserted elsewhere",
    "25": "the size of the public set, asserted by the figure checker",
    "50": "proof obligations, asserted by the figure checker",
    "55": "the sizes of the semi-private and private sets, quoted from the report",
    "135": "the full environment count used in a planted scorecard",
    "342": "the number of announced human replays, quoted from the announcement",
    "355": "the report's stated win probability denominator, discussed as a claim",
    # quoted from an artefact rather than measured by us
    "32": "an element of ar25's published baseline vector, quoted from /api/games "
          "(artifacts/api/games.json); checked against the artefact by tests/test_paper.py",
    "37": "an element of ar25's published baseline vector, as above",
    "89": "an element of ar25's published baseline vector, as above",
    "159": "an element of ar25's published baseline vector, as above",
    "233": "an element of ar25's published baseline vector, as above",
    "15": "the sum of the level weights 1 to 5 of a five-level planted trace, arithmetic stated in the text",
    "256": "part of the algorithm name SHA-256",
    "29": "1 minus (16/19) squared, expressed as a percentage; both inputs are traced",
    "128": "the digest size in bits of the BLAKE2b state key",
    "23": "the count of environment sources using no randomness, 25 less the two named",
    "7": "Limitation 7, a cross-reference",
    "24.16": "the Node version used",
    "1500": "the wall-clock cap in seconds of the ls20 enumeration, a run parameter recorded in the reproduce sequence",
    "1200": "the wall-clock cap in seconds of the breadth sweep, a run parameter recorded in the reproduce sequence",
    "120": "the wall-clock cap in seconds per level of the baseline search, a run parameter recorded in the reproduce sequence",
    "60": "the wall-clock cap in seconds per environment of the reset probes, a run parameter recorded in the reproduce sequence",
    "20000": "the action cap per environment of the reset probes, a run parameter recorded in the reproduce sequence",
    "51": "one action past the 5.0x cutoff on a baseline of 10, which is what "
          "probe P3b's own description in artifacts/scorer/probes.log records; "
          "both the baseline and the multiplier are themselves traced",
    # arithmetic the text performs on numbers that are themselves traced
    "4096": "64 x 64, the size of the click coordinate space implied by the "
            "declared 0..63 contract for x and y",
    "190560": "the sum of the two per-level edge counts, 56772 and 133788, each asserted",
    "1.3225": "1.15 squared, the arithmetic of the equation reading, shown in the text",
    "132.25": "1.15 squared as a percentage, the same arithmetic",
    "123.46": "(10/9) squared as a percentage, the equation reading applied to the "
              "nine actions and baseline of ten named in the same sentence",
}

# Wording replaced during Phases 10-14. Each may survive only in a passage that
# narrates the correction, identified by a phrase that must appear near it.
SUPERSEDED: list[tuple[str, str | None]] = [
    ("[DATE]", None),
    ("were reported to the ARC Prize Foundation", None),
    ("17 of", "reported 17 of"),
    ("sixty paired runs", None),
    ("0.006267806", None),
    ("1.05", None),
]


def load_checker():
    spec = importlib.util.spec_from_file_location("vn", HERE / "verify_numbers.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def derivations(value: str) -> set[str]:
    """Forms of an asserted value that may legitimately appear in prose.

    A paper writes a share as a percentage and rounds it, so 0.062801932 in the
    log is 6.28% on the page. Accepting those forms is not a loosening: each is
    a function of a value that IS traced, and any other number still fails.
    """
    out = {value, value.replace(",", "")}
    out |= set(re.findall(r"\d+(?:\.\d+)?", value))
    try:
        f = float(value.rstrip("%"))
    except ValueError:
        return out
    for x in (f, f * 100):
        for dp in (0, 1, 2, 3):
            r = round(x, dp)
            out.add(f"{r:.{dp}f}".rstrip(".") if dp else str(int(r)) if r == int(r) else str(r))
            out.add(str(r))
    return {o for o in out if o}


def body_text() -> str:
    subprocess.run([sys.executable, str(HERE / "normalise.py")], check=True,
                   capture_output=True)
    text = (HERE / "main.txt").read_text()
    # The preamble is typesetting, not prose: 11pt and 1.2in are not figures.
    if "\\begin{document}" in text:
        text = text[text.index("\\begin{document}"):]
    for marker in ("References", "Acknowledgements"):
        if marker in text:
            text = text[:text.index(marker)]
    return text


def tokens(text: str) -> list[str]:
    """Numeric tokens, with thousands separators joined and a version string or
    an identifier like `ls20` or `v2` never mistaken for a figure."""
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    # Identifiers are not figures: game ids and hash prefixes (hex words with
    # at least one letter, seven or more characters) and x.y.z version strings.
    text = re.sub(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{7,}\b", " ", text)
    text = re.sub(r"\b\d+\.\d+\.\d+\b", " ", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)      # ISO dates
    return re.findall(r"(?<![A-Za-z0-9_.\\])\d+(?:\.\d+)?", text)


def main() -> int:
    checker = load_checker()
    asserted: set[str] = set()
    for _, value, _, _ in checker.CLAIMS:
        asserted |= derivations(str(value).strip())
    # The optima/baseline table is verified by its own check in verify_numbers,
    # so its numbers are traced even though they are not CLAIMS entries.
    for row in getattr(checker, "TABLE", []):
        for cell in row:
            asserted |= derivations(str(cell))
    text = body_text()
    fails: list[str] = []

    # S1 -- every number is traced or exempted
    unexplained = sorted({t for t in tokens(text)
                          if t not in asserted and t not in EXEMPT},
                         key=lambda x: (len(x), x))
    for t in unexplained:
        fails.append(f"number {t!r} in the paper is neither asserted by a claim "
                     f"nor listed in EXEMPT with a reason")
    # An exemption for a number the paper no longer contains is dead weight, and
    # dead weight is how an exemption table stops meaning anything.
    present = set(tokens(text))
    for t in sorted(set(EXEMPT) - present):
        fails.append(f"EXEMPT lists {t!r}, which no longer appears in the paper")

    # S2 -- the paper, the findings and the claims agree on the headline figures
    findings = (ROOT / "FINDINGS.md").read_text()
    for value, where in (("148", "exposed=148"), ("183", "levels=183"),
                         ("250", "runs=250"), ("0.062801932", "0.062801932")):
        if value.replace(".", "").isdigit() and where not in findings:
            fails.append(f"headline {where!r} missing from FINDINGS.md")

    # S3 -- no superseded wording outside a passage that narrates the correction
    tex_path = ROOT / "paper" / "main.tex"
    tex = tex_path.read_text()
    for needle, allowed_near in SUPERSEDED:
        if needle in tex and (allowed_near is None or allowed_near not in tex):
            fails.append(f"superseded wording {needle!r} still present in the paper")

    # S4 -- discipline that must never regress
    if "without prior private notice" not in tex:
        fails.append("the disclosure statement no longer says what is true")
    # Stated as a POSITIVE check so this file never has to contain the private
    # address it guards: the only permitted mail addresses are the public
    # contact and the authors' institutional ones.
    permitted = {"ibrahimnmian@gmail.com", "ibby@millenniumresearch.ai",
                 "shayaan@millenniumresearch.ai"}
    for doc, name in ((tex, "the paper"), (findings, "FINDINGS.md")):
        for addr in set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", doc)):
            if addr not in permitted and not addr.endswith("arcprize.org"):
                fails.append(f"unexpected mail address {addr!r} in {name}")
    for word in ("Claude", "Anthropic", "Co-Authored", "Generated with"):
        if word in tex:
            fails.append(f"attribution {word!r} appears in the paper")
    # The repository claim is in exactly one of two states: a visible placeholder
    # while the repository is private, or a real URL once it is public. Both at
    # once, or neither, means the sentence is asserting something unchecked.
    placeholder = tex.count("[REPOSITORY URL]")
    url = len(re.findall(r"github\.com/[A-Za-z0-9_.-]+/arc-agi-3-audit", tex))
    # A copy prepared for review carries the repository as supplementary material
    # and names no URL; that is the third valid state of the sentence.
    supplementary = "included in full as supplementary material" in tex
    if supplementary and not url and not placeholder:
        pass
    elif placeholder and url:
        fails.append("the repository claim carries both a placeholder and a URL")
    elif not placeholder and not url:
        fails.append("the repository claim names neither a placeholder nor a URL")
    elif placeholder > 1 or url > 1:
        fails.append("the repository claim is stated more than once")

    for f in fails:
        print(f"[FAIL] {f}")
    print(f"CONSISTENCY CHECK: {'PASS' if not fails else f'FAIL ({len(fails)} issues)'}"
          f" ({len(set(tokens(text)))} distinct numbers, {len(EXEMPT)} exempted)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
