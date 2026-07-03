#!/usr/bin/env python3
"""Pokédex species-description table: location, decoding and 3-line wrapping.

Unbound (CFRU/FireRed) stores one ``PokedexEntry`` struct per species at a
fixed stride. The first field of each struct is a 32-bit little-endian
pointer to the species description text; the category label ("X Pokémon")
and the height/weight fields follow and are NOT touched here (the category
table is protected by :mod:`src.core.fixed_tables`).

The description is shown on the Pokédex info screen in a window that fits
**three lines** at most. The Spanish ROM proves the budget: every Spanish
description wraps into at most three lines, none wider than
:data:`DEX_LINE_WIDTH` pixels. French translations inherit the English
break positions and frequently spill onto a fourth line, so they must be
re-wrapped (and, when genuinely too long, shortened upstream) to respect
the three-line window.
"""

from __future__ import annotations

from typing import Iterator, List, NamedTuple, Optional

from src.core.dialogue_linewrap import (
    _feasible_partition,
    _minimax_partition,
    _split_words,
    line_width,
    word_width,
)
from src.core.text_codec import TextDecoder

# Struct table of PokedexEntry records. ``DEX_TABLE_BASE`` is the file
# offset of entry 0; each record is ``DEX_TABLE_STRIDE`` bytes and opens
# with the description pointer. Verified structurally against the source
# ROM (the same range backs the category labels in fixed_tables.py).
DEX_TABLE_BASE = 0x1A35800
DEX_TABLE_STRIDE = 36
DEX_TABLE_COUNT = 1024  # upper bound; invalid/garbage records are skipped

ROM_POINTER_BASE = 0x08000000
TERMINATOR = 0xFF

# Maximum visible lines of a Pokédex description and the usable pixel width
# of one line. 232 px is the widest line found across every Spanish
# description (the reference layout the window was designed for); wrapping
# to this width is guaranteed to fit on screen.
DEX_MAX_LINES = 3
DEX_LINE_WIDTH = 232

# A clean description is plain prose: printable Latin/French/German/Italian
# glyphs only, no leftover ``<0xNN>`` control tokens, with at least one space.
_ALLOWED = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    " .,!?:;'\"()/%+&-×º°ª¥♂♀"
    "àâçéèêëîïôœùûüÀÁÂÇÈÉÊËÎÏÔŒÙÚÛÑßíáóúñ"
    "äöüÄÖÜ"
    "ìòÌÒ"
)


class DexEntry(NamedTuple):
    """One Pokédex description slot located in the ROM."""

    index: int          # position in the struct table
    struct_offset: int  # file offset of the struct (pointer lives here)
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


def _decode(rom: bytes, offset: int, limit: int = 320) -> Optional[str]:
    """Decode a 0xFF-terminated Pokémon string, or ``None`` if implausible."""
    if offset is None or offset >= len(rom):
        return None
    end = rom.find(bytes([TERMINATOR]), offset)
    if end < 0 or end - offset > limit:
        return None
    return TextDecoder.decode_pokemon(rom[offset:end], preserve_unknown=True)


def is_description(text: Optional[str]) -> bool:
    """True when ``text`` is a real, decodable species description."""
    if not text or not (15 <= len(text) <= 300):
        return False
    if "<0x" in text:
        return False
    if " " not in text:
        return False
    return all(ch in _ALLOWED or ch == "\n" for ch in text)


def iter_entries(rom: bytes) -> Iterator[DexEntry]:
    """Yield every valid Pokédex description slot found in ``rom``."""
    for index in range(DEX_TABLE_COUNT):
        struct_offset = DEX_TABLE_BASE + index * DEX_TABLE_STRIDE
        text_offset = _deref(rom, struct_offset)
        if text_offset is None:
            continue
        text = _decode(rom, text_offset)
        if not is_description(text):
            continue
        yield DexEntry(index, struct_offset, text_offset, text)


def wrap_lines(
    text: str,
    max_lines: int = DEX_MAX_LINES,
    max_width: int = DEX_LINE_WIDTH,
) -> Optional[List[str]]:
    """Wrap ``text`` into the fewest lines (<= ``max_lines``) within width.

    Returns the list of lines, or ``None`` when the words cannot be laid
    out in ``max_lines`` lines without a line exceeding ``max_width`` —
    i.e. the description is too long for the window and must be shortened.
    """
    words = _split_words(text.replace("\n", " "))
    if not words:
        return [text]
    widths = [word_width(w) for w in words]
    for k in range(1, max_lines + 1):
        cuts = _feasible_partition(widths, k, max_width)
        if cuts is not None:
            return _join(words, cuts)
    return None


def rewrap(
    text: str,
    max_lines: int = DEX_MAX_LINES,
    max_width: int = DEX_LINE_WIDTH,
) -> str:
    """Re-wrap a description to <= ``max_lines`` lines, joined by ``\\n``.

    When the text genuinely cannot fit, it is laid out across exactly
    ``max_lines`` lines minimising the widest line (best effort) so the
    result never gains a fourth line; callers should shorten such texts.
    """
    lines = wrap_lines(text, max_lines, max_width)
    if lines is None:
        words = _split_words(text.replace("\n", " "))
        widths = [word_width(w) for w in words]
        lines = _join(words, _minimax_partition(widths, min(max_lines, len(words))))
    return "\n".join(lines)


def fits(text: str, max_lines: int = DEX_MAX_LINES, max_width: int = DEX_LINE_WIDTH) -> bool:
    """True when ``text`` can be shown within the ``max_lines``-line window."""
    return wrap_lines(text, max_lines, max_width) is not None


def _join(words: List[str], cuts: List[int]) -> List[str]:
    lines: List[str] = []
    start = 0
    for cut in [*cuts, len(words)]:
        lines.append(" ".join(words[start:cut]))
        start = cut
    return lines


__all__ = [
    "DexEntry",
    "DEX_MAX_LINES",
    "DEX_LINE_WIDTH",
    "iter_entries",
    "is_description",
    "wrap_lines",
    "rewrap",
    "fits",
    "line_width",
]
