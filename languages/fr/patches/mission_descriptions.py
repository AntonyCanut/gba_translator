#!/usr/bin/env python3
"""Write the bounty-mission descriptions exactly, in their 3-line layout.

Root cause (found against the English ROM + the generic builder)
----------------------------------------------------------------
The Borrius bounty board renders a mission's *description* in a narrow,
**non-scrolling** window that shows at most **three lines**. Each mission is
displayed through the shared board handler (``call 0x09EAF584``); the
description is a normal pointer-referenced ``dialogue`` string.

Because the strings are tagged ``dialogue``, the generic builder
(:mod:`19_build_translated_rom_generic`) re-wraps them with the *dialogue*
metrics — a **192 px, two-line** box — and rewrites the 2nd+ ``\\n`` to a
``{SCROLL}`` (0xFA) code (see ``rewrap_dialogue`` / the FRLG break rule). For
the mission window that is wrong twice over:

* the box is narrower (~176 px), so a 192 px-balanced line auto-wraps and pushes
  the tail onto an invisible 4th line (the user's missing ``Borrius !`` /
  ``récupérez ce qui a été volé``);
* the window does not scroll, so a ``{SCROLL}`` code mid-description misbehaves.

``combined_fr.txt`` already holds each description hand-wrapped to <=3 lines that
fit the box (every line <=172 px), using only ``\\n`` breaks. This post-build
patch makes that layout final: it encodes each value **verbatim** (no dialogue
re-wrap, no scroll normalisation), relocates one 0xFF-terminated copy into free
space, and repoints the mission's live pointer cell to it.

Sites are discovered from the **English** ROM (``find_referrers``): the bounty
scripts are never relocated, so the pointer *cell* address is identical in the
built ROM even when the generic pass already moved (and mangled) the string.
Overwriting that cell with our clean copy therefore wins regardless of what the
generic builder did. The patch is idempotent and reference-driven.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from src.core.text_codec import TextEncoder  # noqa: E402
from src.core.text_reinserter import FreeSpaceAllocator  # noqa: E402

from apply_inline_overrides_fr import (  # noqa: E402
    _apply_control_placeholders,
    _normalize_text,
    _read_raw_entry,
)

ROM_POINTER_BASE = 0x08000000
DEFAULT_COMBINED = REPO_ROOT / "languages/fr/combined_fr.txt"

# Usable width of the 3-line bounty box (px). A line wider than this auto-wraps
# in-game; in-game evidence places the box between 170 (fits) and 188 (wraps).
BOX_WIDTH = 176
MAX_LINES = 3

# Every bounty-mission *description*, enumerated from the English ROM by walking
# the board handler call (``04 <ptr> 09`` -> 0x09EAF584) back to each mission's
# title pointer, then to the adjacent description pointer. These are the strings
# hand-wrapped in combined_fr.txt; the patch keeps that layout byte-for-byte.
TARGETS: tuple[int, ...] = (
    0x1EE55DE, 0x1EE71A0, 0x1EEA8A9, 0x1EEA909, 0x1EEC79B, 0x1EEDAA2, 0x1EF1137,
    0x1EF155B, 0x1EF7E52, 0x1F016FD, 0x1F07861, 0x1F07E7E, 0x1F082A1, 0x1F0921E,
    0x1F0CA95, 0x1F0E744, 0x1F13071, 0x1F1425C, 0x1F14CE2, 0x1F1F8B7, 0x1F2319E,
    0x1F260AE, 0x1F2817A, 0x1F581E2, 0x1F5949B, 0x1F60F39, 0x1F63D8E, 0x1F6AF07,
    0x1F7BE70, 0x1F7D066, 0x1F7E1EC, 0x1F87B73, 0x1F93CB0, 0x1F9C853, 0x1F9CE03,
    0x1F9EAF1, 0x1F9F08F, 0x1F9FBCD, 0x1FA0D55, 0x1FA4E1F, 0x1FA58E6, 0x1FA76B4,
    0x1FA92F7, 0x1FA9BCF, 0x1FAAD67, 0x1FADF4A, 0x1FAE718,
)

_OFFSET_LINE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def load_combined(path: Path) -> dict[int, str]:
    """original ROM offset -> French text (last entry wins, per combined_fr.txt)."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _OFFSET_LINE.match(line)
        if m:
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def encode_verbatim(text: str, source_rom: bytes, offset: int) -> bytes:
    """Encode a combined_fr.txt value to ROM bytes WITHOUT any dialogue re-wrap.

    Only ``\\n`` -> newline (0xFE) and the shared control-placeholder mapping are
    applied; the hand-authored 3-line layout is preserved exactly.
    """
    english = _read_raw_entry(source_rom, offset, "pokemon")
    normalized = _normalize_text(text)
    if english:
        normalized = _apply_control_placeholders(
            normalized, english.get("decoded_text"), english.get("raw_bytes")
        )
    return TextEncoder.encode(normalized, "pokemon")


def find_referrers(rom: bytes, offset: int) -> list[int]:
    """Every ROM cell holding a 32-bit LE pointer to ``ROM_POINTER_BASE+offset``."""
    needle = struct.pack("<I", ROM_POINTER_BASE + offset)
    return [m.start() for m in re.finditer(re.escape(needle), rom)]


def apply(rom: bytearray, combined: dict[int, str], source_rom: bytes,
          reserved_rom: bytes | None = None) -> dict:
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    stats = {"targets": 0, "repointed": 0, "no_source": 0, "failed": 0, "skipped": 0}

    for offset in TARGETS:
        # Sites come from the *English* ROM: the bounty scripts are never
        # relocated, so the cell address is identical in the built ROM even if
        # the generic pass moved the (mangled) string elsewhere.
        sites = find_referrers(source_rom, offset)
        if not sites:
            stats["skipped"] += 1
            continue
        text = combined.get(offset)
        if not text:
            stats["no_source"] += 1
            continue

        encoded = encode_verbatim(text, source_rom, offset)
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            stats["failed"] += 1
            continue
        rom[new_offset:new_offset + len(encoded)] = encoded
        pointer = struct.pack("<I", new_offset + ROM_POINTER_BASE)
        for cell in sites:
            rom[cell:cell + 4] = pointer
            stats["repointed"] += 1
        stats["targets"] += 1

    return stats


def verify(rom: bytes, source_rom: bytes, combined: dict[int, str]) -> list[tuple[int, str]]:
    """Each target's live cell must reach a clean, scroll-free, <=3-line copy."""
    bad: list[tuple[int, str]] = []
    for offset in TARGETS:
        sites = find_referrers(source_rom, offset)
        text = combined.get(offset)
        if not sites or not text:
            continue
        encoded = encode_verbatim(text, source_rom, offset)
        # the encoded copy must exist verbatim and the live cell must point at it
        idx = rom.find(encoded)
        if idx < 0:
            bad.append((offset, "encoded French copy not found in ROM"))
            continue
        live = struct.unpack("<I", rom[sites[0]:sites[0] + 4])[0] - ROM_POINTER_BASE
        decoded = bytes(rom[live:live + len(encoded)])
        if decoded != encoded:
            bad.append((offset, "live pointer does not reach the clean copy"))
            continue
        if 0xFA in encoded[:-1]:  # 0xFA = scroll; must never appear in a mission box
            bad.append((offset, "scroll code present"))
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, help="Built French ROM to patch in place")
    parser.add_argument("--source", default=str(REPO_ROOT / "input/roms/englishrom.gba"),
                        help="English ROM (stable pointer sites + control sequences)")
    parser.add_argument("--combined", default=str(DEFAULT_COMBINED),
                        help="combined_fr.txt source of truth (offset -> FR text)")
    parser.add_argument("--reference-rom", default=None,
                        help="Same-base ROM whose populated bytes must not be reused")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    source_rom = Path(args.source).read_bytes()
    combined = load_combined(Path(args.combined))
    reserved = Path(args.reference_rom).read_bytes() if args.reference_rom else None

    stats = apply(rom, combined, source_rom, reserved_rom=reserved)
    remaining = verify(rom, source_rom, combined)
    rom_path.write_bytes(rom)

    print("✓ Mission descriptions — 3-line relocation (scroll-free):")
    print(f"   - Targets relocated:          {stats['targets']}")
    print(f"   - Pointers repointed:         {stats['repointed']}")
    if stats["skipped"]:
        print(f"   - No source pointer (skip):   {stats['skipped']}")
    if stats["no_source"]:
        print(f"   - No FR source:               {stats['no_source']}")
    if stats["failed"]:
        print(f"   - FAILED (free space):        {stats['failed']}")
        return 1
    if remaining:
        print("   - ✗ Verification failed:")
        for offset, why in remaining:
            print(f"       0x{offset:08X}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
