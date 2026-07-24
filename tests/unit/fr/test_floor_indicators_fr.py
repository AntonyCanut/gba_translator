"""Source-of-truth guard for the floor-indicator translations (issue #27 / #100).

The small floor-change popup shown in caves and buildings (1F, 2F, ... B4F)
is served by a 15-entry string table at EN ROM offsets 0x41803A-0x418069,
reached by six duplicate pointer tables (ascending / descending / ritual
look-ups). Because every French label is *longer* than its English original
("RDC" > "1F", "1E" > "2F", ...), the build must relocate these strings into
free space and repoint all six tables.

That relocation turned out to be fragile: several rebuilds silently reverted
the popup to English ("1F"), and one build merged two labels into "RDC1E"
(a dropped 0xFF terminator) — which is exactly what issue #100 reported as
"les étages ne sont pas traduits dans la dernière version".

This test pins the living combined_fr.txt entries so a future bulk rewrite,
a stale-CSV rebuild, or a careless edit cannot drop or change them at the
source. The built-ROM counterpart lives in
`tests/test_regression_texts.py::test_floor_indicators_translated_fr`
(marked `rom`) and verifies all six pointer tables actually resolve.
"""

from __future__ import annotations

import re
from pathlib import Path

COMBINED_FR = Path(__file__).resolve().parents[3] / "languages/fr/combined_fr.txt"

# Same line grammar the build loader uses (scripts/apply_combined_fr.py).
_LINE_RE = re.compile(r"^\s*0x([0-9a-fA-F]+)\s*:\s*(.*)$")

# EN string offset -> expected French label.
# Pattern requested in issue #27/#100: 1F -> RDC, then n F -> (n-1) E,
# and basement floors B1F..B4F -> -1..-4 (French elevator convention).
EXPECTED_FLOORS = {
    0x41803A: "RDC",
    0x41803D: "1E",
    0x418040: "2E",
    0x418043: "3E",
    0x418046: "4E",
    0x418049: "5E",
    0x41804C: "6E",
    0x41804F: "7E",
    0x418052: "8E",
    0x418055: "9E",
    0x418059: "10E",
    0x41805D: "-1",
    0x418061: "-2",
    0x418065: "-3",
    0x418069: "-4",
}


def _load_last_wins(path: Path) -> dict[int, str]:
    """Mirror the build's last-wins parsing of combined_fr.txt."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LINE_RE.match(line)
        if not match:
            continue
        mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def test_floor_indicators_persisted_in_combined_fr():
    mapping = _load_last_wins(COMBINED_FR)

    for offset, expected in EXPECTED_FLOORS.items():
        assert offset in mapping, (
            f"Floor label at {offset:#x} is missing from combined_fr.txt — "
            f"the floor popup will fall back to English (issue #100)."
        )
        assert mapping[offset] == expected, (
            f"Floor label at {offset:#x} should be {expected!r}, "
            f"got {mapping[offset]!r}."
        )


def test_no_english_floor_token_survives_in_french_text():
    """Floors are also written *inside* place descriptions — none may stay English.

    The reporter's last #100 screenshot showed a floor glued to a location name;
    the same English tokens were still spelled out in the Cube collection texts
    (Zygarde cells, tablets, emeralds), the Trainer-Tips signs, the item-location
    hints and the department-store directory. They must all follow the same
    convention as the pop-up: ``1F -> RDC``, ``nF -> (n-1)E``, ``BnF -> -n``.
    """
    mapping = _load_last_wins(COMBINED_FR)
    # `\n`, `\l`, `\p` are literal two-character escapes in combined_fr.txt: the
    # trailing letter must not be mistaken for a word character before a token.
    escapes = re.compile(r"\\[nlp]")
    token = re.compile(r"(?<![A-Za-z0-9])(?:B[1-4]F|(?:[1-9]|1[01])F)(?![A-Za-z0-9])")

    offenders = {
        offset: text
        for offset, text in mapping.items()
        if offset not in EXPECTED_FLOORS and token.search(escapes.sub(" ", text))
    }
    assert not offenders, "English floor tokens left in French text: " + ", ".join(
        f"{offset:#x} ({text[:60]!r})" for offset, text in sorted(offenders.items())
    )


def test_floor_labels_have_no_stray_terminator_or_whitespace():
    """Guard against the "RDC1E" merge class of corruption at the source.

    A trailing space or an accidental concatenation in the source line is the
    kind of edit that produces a merged / mis-terminated label in the ROM.
    """
    mapping = _load_last_wins(COMBINED_FR)

    for offset, expected in EXPECTED_FLOORS.items():
        value = mapping.get(offset, "")
        assert value == value.strip(), (
            f"Floor label at {offset:#x} has stray whitespace: {value!r}"
        )
        # Each label is a single short token — never a merge of two labels.
        assert "\n" not in value, f"Floor label at {offset:#x} must be single-line"
        assert len(value) <= 3, (
            f"Floor label at {offset:#x} is unexpectedly long ({value!r}); "
            f"a merge like 'RDC1E' would look like this."
        )
