#!/usr/bin/env python3
"""Move-description table: location, decoding and 5-line wrapping.

Unbound (CFRU/FireRed) stores move descriptions behind a pointer table
``gMoveDescriptionPointers`` indexed by move number. Each 32-bit
little-endian entry points to a 0xFF-terminated description string shown on
the « Capacités connues » summary screen.

That window fits **five lines** at most, each line under
:data:`MOVE_LINE_WIDTH` pixels. The Spanish ROM proves the budget: every
Spanish move description wraps into at most five lines, none wider than
142 px (the widest Spanish line — the reference layout the window was
designed for). French translations inherit the English break positions and
routinely spill onto a sixth line or past the right edge, so they must be
re-wrapped (and, when genuinely too verbose, shortened upstream) to respect
the five-line window — exactly the strategy :mod:`src.core.pokedex` uses for
the three-line Pokédex window.

The generic windowed-wrap helpers (:func:`wrap_lines`, :func:`rewrap`,
:func:`fits`) and the prose check (:func:`is_description`) are shared with
:mod:`src.core.pokedex`; only the table layout and window budget differ.
"""

from __future__ import annotations

from typing import Iterator, NamedTuple, Optional

from src.core.pokedex import is_description
from src.core.pokedex import fits as _fits
from src.core.pokedex import rewrap as _rewrap
from src.core.pokedex import wrap_lines as _wrap_lines
from src.core.text_codec import TextDecoder

# Pointer table of move descriptions, indexed by move number. Located and
# verified against the FR ROM: desc[1] = Écras'Face, desc[44] = Morsure,
# desc[88] = Jet-Pierres. The decoded text reproduces the in-game summary
# screen byte for byte, confirming this is the table the screen reads.
MOVE_DESCRIPTION_TABLE = 0x99F190
MOVE_COUNT = 894  # entry 0 is "no move"; valid moves run 1..893

ROM_POINTER_BASE = 0x08000000
TERMINATOR = 0xFF

# Maximum visible lines of a move description and the usable pixel width of
# one line. 142 px is the widest line found across every Spanish move
# description; wrapping to this width is guaranteed to fit on screen.
MOVE_MAX_LINES = 5
MOVE_LINE_WIDTH = 142


class MoveEntry(NamedTuple):
    """One move-description slot located in the ROM."""

    index: int          # move number (position in the pointer table)
    struct_offset: int  # file offset of the pointer table cell
    text_offset: int    # file offset the pointer dereferences to
    text: str           # decoded description


def _deref(rom: bytes, offset: int) -> Optional[int]:
    """Return the file offset a 4-byte ROM pointer at ``offset`` points to."""
    if offset + 4 > len(rom):
        return None
    value = int.from_bytes(rom[offset:offset + 4], "little")
    if ROM_POINTER_BASE <= value < ROM_POINTER_BASE + 0x02000000:
        return value - ROM_POINTER_BASE
    return None


def _decode(rom: bytes, offset: Optional[int], limit: int = 320) -> Optional[str]:
    """Decode a 0xFF-terminated Pokémon string, or ``None`` if implausible."""
    if offset is None or offset >= len(rom):
        return None
    end = rom.find(bytes([TERMINATOR]), offset)
    if end < 0 or end - offset > limit:
        return None
    return TextDecoder.decode_pokemon(rom[offset:end], preserve_unknown=True)


def wrap_lines(text: str):
    """Wrap ``text`` to the move window, or ``None`` if it cannot fit."""
    return _wrap_lines(text, MOVE_MAX_LINES, MOVE_LINE_WIDTH)


def rewrap(text: str) -> str:
    """Re-wrap ``text`` to <= 5 lines within the move window width."""
    return _rewrap(text, MOVE_MAX_LINES, MOVE_LINE_WIDTH)


def fits(text: str) -> bool:
    """True when ``text`` fits the five-line move-description window."""
    return _fits(text, MOVE_MAX_LINES, MOVE_LINE_WIDTH)


def struct_offset(index: int) -> int:
    """File offset of the pointer table cell for move ``index``."""
    return MOVE_DESCRIPTION_TABLE + index * 4


def iter_entries(rom: bytes, count: int = MOVE_COUNT) -> Iterator[MoveEntry]:
    """Yield every valid move-description slot found in ``rom``.

    Entry 0 ("no move") and slots whose pointer does not dereference to a
    real prose description (unused move numbers) are skipped.
    """
    for index in range(1, count):
        soff = struct_offset(index)
        text_offset = _deref(rom, soff)
        if text_offset is None:
            continue
        text = _decode(rom, text_offset)
        if not is_description(text):
            continue
        yield MoveEntry(index, soff, text_offset, text)


__all__ = [
    "MoveEntry",
    "MOVE_DESCRIPTION_TABLE",
    "MOVE_COUNT",
    "MOVE_MAX_LINES",
    "MOVE_LINE_WIDTH",
    "struct_offset",
    "iter_entries",
    "is_description",
    "wrap_lines",
    "rewrap",
    "fits",
]
