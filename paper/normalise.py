"""Render main.tex as plain text with LaTeX number formatting removed, so the
audit kit's claims checker can verify every figure in the paper against the log
that produced it. Reading the numbers by eye is not a check."""
import re
from pathlib import Path

here = Path(__file__).parent
# In the anonymised supplementary archive the named source is absent; the
# generated the journal source carries the same body, so the checkers read that.
source = here / "main.tex" if (here / "main.tex").exists() else here / "journal" / "journal.tex"
src = source.read_text()
t = src
t = re.sub(r"\\code\{([^{}]*)\}", r"\1", t)          # \code{x} -> x
t = re.sub(r"\\texttt\{([^{}]*)\}", r"\1", t)
t = re.sub(r"\\emph\{([^{}]*)\}", r"\1", t)
t = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", t)
t = t.replace("{,}", "")                              # 14{,}337 -> 14337
t = t.replace("$", "")                                # inline math delimiters
t = t.replace("\\_", "_").replace("\\%", "%").replace("\\&", "&")
t = re.sub(r"[ \t]+", " ", t)
Path(__file__).with_name("main.txt").write_text(t)
print(f"wrote main.txt ({len(t)} chars)")
