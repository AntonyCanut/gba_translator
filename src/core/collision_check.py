#!/usr/bin/env python3
"""Detect inter-cell text collisions in a translated Pokémon Unbound ROM.

Motivation
----------
The generic builder (:mod:`src.translators.19_build_translated_rom_generic`)
writes many translated strings *in place*, one after another, in packed
description tables (~0x920000-0xA40000) where the source strings sit back to
back with no padding between them. A translated string written there must be
terminated by ``0xFF`` *before* the start of the next live cell; otherwise the
game, reading the first cell through its live pointer, runs straight past the
missing terminator into the next cell. Two descriptions fuse on screen and, in
the worst case, an unterminated CFRU string reads to a random ``0xFF`` far
away and freezes (see the ``diagnosing-unbound-freezes`` skill).

A second failure mode is the *phantom* cell: the string scanner captured an
offset that no pointer actually addresses (0 referents even in the English
ROM). The game never reads it through a pointer, but writing a longer
translation there overruns the terminator and clobbers the leading bytes of a
real, pointer-addressed neighbour.

This module is deliberately language-agnostic and works purely on bytes, so the
same audit protects the French, German and Italian builds:

* :func:`build_pointer_index` — one pass over a reference (English) ROM,
  mapping every in-ROM pointer value to the sites that hold it (all four byte
  alignments, matching a raw 4-byte little-endian referent search).
* :func:`has_live_pointer` — does *any* plausible pointer address this cell?
  Cells with none are phantom.
* :func:`live_target` — where the cell's pointer points in the *built* ROM
  (itself → written in place, elsewhere → relocated and repointed).
* :func:`find_collisions` — for every in-place / phantom cell, verify a ``0xFF``
  terminator exists before the next occupied offset; report an overrun
  otherwise. This is the "compare against the next entry's offset" check.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .text_codec import TextDecoder

ROM_BASE = 0x08000000
TERMINATOR = 0xFF


def build_pointer_index(rom: bytes) -> Dict[int, List[int]]:
    """Map ``target_offset -> [sites]`` for every in-ROM pointer in ``rom``.

    A *site* is the byte position of a 4-byte little-endian word whose value is
    ``0x08000000 + target_offset`` and lands inside the ROM. All four byte
    alignments are scanned (a raw referent search, exactly like the manual
    ``0x08000000+offset`` little-endian scan used to prove phantom cells), but
    only in-range values are kept, so the index stays small.
    """
    n = len(rom)
    lo, hi = ROM_BASE, ROM_BASE + n
    index: Dict[int, List[int]] = {}
    for align in range(4):
        end = n - ((n - align) % 4)
        segment = rom[align:end]
        for k, (value,) in enumerate(struct.iter_unpack('<I', segment)):
            if lo <= value < hi:
                index.setdefault(value - ROM_BASE, []).append(align + k * 4)
    return index


def _is_ewram_word(rom: bytes, pos: int) -> bool:
    if pos < 0 or pos + 4 > len(rom):
        return False
    value = struct.unpack_from('<I', rom, pos)[0]
    return 0x02000000 <= value < 0x02040000


def plausible_sites(rom: bytes, offset: int, sites: Iterable[int]) -> List[int]:
    """Filter raw referent sites down to those that can really reference text.

    Mirrors :meth:`SmartReinserter._plausible_pointer_sites`: a genuine text
    reference is 4-byte aligned (literal pools, pointer tables) or sits right
    after a script opcode / EWRAM word that takes a text pointer. Random
    ``0x08xxxxxx`` words inside Thumb code are rejected, so a code word that
    merely happens to equal a cell's address does not make it look "live".
    """
    kept: List[int] = []
    for site in sites:
        if site < 0 or site + 4 > len(rom):
            continue
        plausible = (
            site % 4 == 0
            or (site >= 2 and rom[site - 2] == 0x0F and rom[site - 1] == 0x00)
            or (site >= 2 and rom[site - 2] == 0x85 and rom[site - 1] <= 0x0F)
            or (site >= 1 and rom[site - 1] == 0x67)
            or (site >= 6 and rom[site - 6] == 0x5C)
            or (site >= 10 and rom[site - 10] == 0x5C)
            or (site >= 4 and _is_ewram_word(rom, site - 4))
        )
        if plausible:
            kept.append(site)
    return kept


def has_live_pointer(
    index: Dict[int, List[int]],
    offset: int,
    *,
    en_rom: Optional[bytes] = None,
    require_plausible: bool = True,
) -> bool:
    """Whether any pointer addresses ``offset``.

    With ``require_plausible`` (and ``en_rom`` supplied) only sites that pass
    :func:`plausible_sites` count, which is the strict definition used to prove
    a cell is a phantom. Without it, any raw referent counts.
    """
    sites = index.get(offset)
    if not sites:
        return False
    if require_plausible and en_rom is not None:
        return bool(plausible_sites(en_rom, offset, sites))
    return True


def live_target(built_rom: bytes, site: int) -> Optional[int]:
    """Return the ROM offset the pointer at ``site`` currently points to."""
    if site < 0 or site + 4 > len(built_rom):
        return None
    value = struct.unpack_from('<I', built_rom, site)[0]
    if ROM_BASE <= value < ROM_BASE + len(built_rom):
        return value - ROM_BASE
    return None


def _terminator_index(rom: bytes, offset: int, limit: int) -> int:
    """Index of the first ``0xFF`` at/after ``offset``, or -1 within ``limit``."""
    end = min(len(rom), offset + limit)
    idx = rom.find(bytes([TERMINATOR]), offset, end)
    return idx


@dataclass
class Collision:
    """One in-place cell whose string overruns into the next occupied cell."""

    offset: int
    next_offset: int
    kind: str  # 'in_place' | 'phantom'
    decoded: str = ''
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            'offset': f"0x{self.offset:X}",
            'next_offset': f"0x{self.next_offset:X}",
            'kind': self.kind,
            'decoded': self.decoded,
            **self.extra,
        }


def find_collisions(
    built_rom: bytes,
    offsets: Iterable[int],
    *,
    en_index: Optional[Dict[int, List[int]]] = None,
    en_rom: Optional[bytes] = None,
    source_rom: Optional[bytes] = None,
    region: Optional[tuple] = None,
    decode_limit: int = 400,
) -> List[Collision]:
    """Report cells whose in-place string is not terminated before its neighbour.

    ``offsets`` is the full set of occupied cell offsets (e.g. every offset in a
    ``combined_<code>.txt``); consecutive offsets define the "next entry"
    boundary each string must terminate before.

    A cell is only flagged when its bytes are actually read in place:

    * If a live pointer still targets the cell in ``built_rom`` (``en_index`` +
      ``en_rom`` supplied) it is read in place → check it.
    * If no pointer addresses it, it is a *phantom*; its bytes were written but
      may still corrupt the neighbour they overrun → check it, flagged
      ``kind='phantom'``.
    * If the cell was relocated (its pointer now targets free space), the
      in-place bytes are dead and never read → skipped, no false positive.

    When ``source_rom`` (the English source) is supplied, an overrun is only
    reported if the source had a ``0xFF`` terminator inside the gap that the
    build destroyed — i.e. the translation genuinely fused two cells that were
    separate in English. Overruns where the source *also* has no terminator in
    the gap are not real cell boundaries (``next_offset`` is an interior
    fragment of one long string / binary blob the combined file happens to
    list) and are dropped. This is the precise, low-false-positive definition.

    Each collision is also annotated with ``next_is_live`` (does a live pointer
    address the overrun neighbour) and ``source_had_terminator``.
    """
    occupied = sorted(set(offsets))
    lo = hi = None
    if region is not None:
        lo, hi = region
    collisions: List[Collision] = []

    def _is_live(o: int) -> bool:
        if en_index is None:
            return True  # no reference ROM → cannot tell, treat as live
        sites = en_index.get(o) or []
        if en_rom is not None:
            sites = plausible_sites(en_rom, o, sites)
        return bool(sites)

    for i, offset in enumerate(occupied[:-1]):
        next_offset = occupied[i + 1]
        if lo is not None and not (lo <= offset < hi):
            continue

        kind = 'in_place'
        if en_index is not None:
            sites = en_index.get(offset) or []
            if en_rom is not None:
                sites = plausible_sites(en_rom, offset, sites)
            if not sites:
                kind = 'phantom'
            else:
                # In place only if at least one live pointer still targets it;
                # relocated cells (repointed to free space) are dead in place.
                if not any(live_target(built_rom, s) == offset for s in sites):
                    continue

        span = next_offset - offset
        term = _terminator_index(built_rom, offset, span)
        if term != -1:
            continue

        # Precise gate: the source must have had a real boundary here that the
        # build destroyed. Without a source ROM we cannot tell, so keep it.
        source_had_terminator = True
        if source_rom is not None:
            # An empty source cell (its very first byte is already the
            # terminator) never held text: the offset is unused / free space in
            # the English ROM. The generic builder's relocator reuses free 0xFF
            # runs, so a relocated — and properly terminated — string can
            # legitimately span such a phantom offset. That is free-space reuse,
            # not a destroyed cell boundary, so it is not a real collision.
            # (A genuinely fused live cell has source text at ``offset`` and is
            # still caught below.)
            if offset < len(source_rom) and source_rom[offset] == TERMINATOR:
                continue
            source_had_terminator = _terminator_index(source_rom, offset, span) != -1
            if not source_had_terminator:
                continue

        decoded = TextDecoder.decode_pokemon(
            bytes(built_rom[offset:offset + min(span, decode_limit)]),
            preserve_unknown=True,
        )
        collisions.append(
            Collision(offset=offset, next_offset=next_offset, kind=kind,
                      decoded=decoded,
                      extra={'gap_bytes': span,
                             'next_is_live': _is_live(next_offset),
                             'source_had_terminator': source_had_terminator})
        )
    return collisions
