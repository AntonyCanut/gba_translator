"""Regression guard for the "X and Y aren't compatible" TM/tutor message.

At 0x416DC2, the source text is a two-page message: page 1 states the
incompatibility, `\\p` clears the box, page 2 states the move can't be
learned. The `\\p` token was misplaced one segment too late — after the
second `{STR_VAR_2}` instead of right after "compatibles."/"zusammen." —
so page 1 ended up holding 3 lines of content in a 2-line box, and the
extra line got overwritten mid-render (seen in-game as garbled text like
"Florizarre et Poing Feu ne sont pas comp" / "b.orizarre... Poing Feu").

Pinned here: the FR (and DE, same bug) `\\p` sits immediately after the
first sentence, matching the EN/ES structure, so page 1 is exactly the
"X et Y ne sont pas compatibles." sentence and nothing else.
"""

from __future__ import annotations

import re
from pathlib import Path

OFFSET = 0x416DC2
COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
COMBINED_DE = Path(__file__).resolve().parent.parent / "languages/de/combined_de.txt"


def _last_entry(path: Path, offset: int) -> str:
    """Parse a combined_*.txt file; for duplicate offsets the LAST entry wins."""
    entry = None
    line_re = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
    target = f"{offset:06X}"
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = line_re.match(raw)
        if m and m.group(1).upper() == target:
            entry = m.group(2)
    assert entry is not None, f"offset {offset:#x} not found in {path}"
    return entry


def test_fr_page_break_precedes_second_variable():
    text = _last_entry(COMBINED_FR, OFFSET)
    assert "\\p" in text, f"missing page-break token: {text!r}"
    i_break = text.index("\\p")
    i_first_var2 = text.index("{STR_VAR_2}")
    i_second_var2 = text.index("{STR_VAR_2}", i_first_var2 + 1)
    assert i_first_var2 < i_break < i_second_var2, (
        f"page break must sit between the two {{STR_VAR_2}} uses, "
        f"right after the first sentence: {text!r}"
    )
    assert text.index("compatibles.") < i_break, (
        f"page break must come after 'compatibles.': {text!r}"
    )


def test_de_page_break_precedes_second_variable():
    text = _last_entry(COMBINED_DE, OFFSET)
    assert "\\p" in text, f"missing page-break token: {text!r}"
    i_break = text.index("\\p")
    i_first_var2 = text.index("{STR_VAR_2}")
    i_second_var2 = text.index("{STR_VAR_2}", i_first_var2 + 1)
    assert i_first_var2 < i_break < i_second_var2, (
        f"page break must sit between the two {{STR_VAR_2}} uses, "
        f"right after the first sentence: {text!r}"
    )
    assert text.index("zusammen.") < i_break, (
        f"page break must come after 'zusammen.': {text!r}"
    )
