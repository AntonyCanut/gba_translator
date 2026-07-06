"""Regression guard: Route 3 -> Dresco Town map connection must not be clobbered.

Root cause of the "Dresco Town invisible wall" bug (issue: cannot return from
Route 3 back down to Dresco Town):

Route 3's map header (ROM 0x777C00) points its ``connections`` field at the
``MapConnections`` struct at ROM 0x721344, whose connection-entry array lives just
before it at 0x72132C:

    0x72132C  entry0  dir=2 (NORTH) -> Flower Paradise (group 1, num 4)
    0x721338  entry1  dir=1 (SOUTH) -> Dresco Town     (group 3, num 71)   <- return path
    0x721344  MapConnections { count=2, arr=0x72132C }
    0x72134C  ability description text "Parent and child attack together."

The text extractor over-read: it began a "string" at 0x721340 (12 bytes *inside*
the connection data, which happen to decode as printable glyphs) instead of at the
real text start 0x72134C.  combined_fr.txt then carried a French translation keyed
to 0x721340, so the build wrote the French bytes on top of Route 3's SOUTH
connection to Dresco -> the return connection was destroyed and the player hit an
invisible wall on Route 3's south edge.  The fix moves the entry to the true text
start 0x72134C, leaving the connection block untouched.

This guard fails if any combined_fr.txt entry is keyed to an offset inside the
Route 3 connection block, which would re-introduce the corruption.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMBINED_FR = ROOT / "languages/fr/combined_fr.txt"

# Route 3 connection block that must never be written to by a text entry:
# connection-entry array (0x72132C..0x721343) + MapConnections struct (0x721344..0x72134B).
CONN_BLOCK_START = 0x72132C
CONN_BLOCK_END = 0x72134C  # exclusive; 0x72134C is the real description text start (writable)

# The specific over-read offset that caused the bug; must not reappear.
CLOBBER_OFFSET = 0x721340

_LINE_RE = re.compile(r"^(0x[0-9a-fA-F]+): (.*)$")


def _offsets(path: Path) -> set[int]:
    offsets: set[int] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _LINE_RE.match(line)
        if m:
            offsets.add(int(m.group(1), 16))
    return offsets


def test_combined_fr_present():
    assert COMBINED_FR.exists()


def test_no_entry_clobbers_route3_connection():
    offenders = sorted(
        o for o in _offsets(COMBINED_FR) if CONN_BLOCK_START <= o < CONN_BLOCK_END
    )
    assert not offenders, (
        "combined_fr.txt entries write into Route 3's map-connection block "
        f"[0x{CONN_BLOCK_START:X}, 0x{CONN_BLOCK_END:X}): "
        f"{[hex(o) for o in offenders]} — this destroys the Route 3 -> Dresco "
        "return connection and re-creates the invisible wall. Key the text to its "
        "real start 0x72134C instead."
    )


def test_specific_clobber_offset_absent():
    assert CLOBBER_OFFSET not in _offsets(COMBINED_FR), (
        f"0x{CLOBBER_OFFSET:X} is the over-read offset inside Route 3's connection "
        "data; it must not be a combined_fr.txt key (use 0x72134C for the text)."
    )
