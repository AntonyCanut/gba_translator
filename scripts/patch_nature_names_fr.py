#!/usr/bin/env python3
"""Translate the compact Pokémon nature-name table (starter gift, party menu…).

Root cause (found statically against the English ROM):

The 25 nature names ("Hardy", "Lonely", "Brave", …) are packed back-to-back
as ``0xFF``-terminated strings at ``0x463DBC``-``0x463E5D`` — well below the
main text region (``0x1F00000``-``0x1F80000``) the generic pipeline extracts
from, and outside the extractor's scan. Each name has exactly two live
pointer referrers (a 25×4-byte table at ``0x463E60`` used in code, and a
second identical 25×4-byte table at ``0x1FE65F4`` used by another screen).

Some translators had already hand-added a handful of these offsets straight
into ``combined_fr.txt``; the generic build applied them **in place** (never
relocating, since no extraction entry exists to relocate from), budgeted to
the *English* string's original byte length. Any French word longer than its
English original was silently dropped as "too long", so the built ROM still
shows English for words like "Hardy", "Bold", "Lax", "Timid", "Hasty",
"Jolly", "Modest", "Quiet", "Rash", "Calm" and "Sassy" — this is exactly the
"nature not translated" bug seen when receiving the starter Pokémon
("Il a la nature Hardy.").

This post-build patch closes the gap properly: relocate one ``0xFF``-terminated
copy of each official French nature name into free space and repoint **every**
live referrer to it, so word length is never budget-constrained. The patch is
reference-driven (it scans the whole ROM for live pointers to each original
English offset) and idempotent — an offset no longer pointed at (already
relocated by a previous run) is skipped.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.core.text_codec import TextEncoder  # noqa: E402
from src.core.text_reinserter import FreeSpaceAllocator  # noqa: E402

ROM_POINTER_BASE = 0x08000000

# English ROM offset (first byte of the EN string) -> official French nature
# name. Order matches the in-game nature index (0 = Hardy .. 24 = Quirky).
TARGETS: dict[int, str] = {
    0x463DBC: "Hardi",     # Hardy
    0x463DC2: "Solo",      # Lonely
    0x463DC9: "Brave",     # Brave
    0x463DCF: "Rigide",    # Adamant
    0x463DD7: "Mauvais",   # Naughty
    0x463DDF: "Timide",    # Bold
    0x463DE4: "Docile",    # Docile
    0x463DEB: "Relax",     # Relaxed
    0x463DF3: "Malin",     # Impish
    0x463DFA: "Lâche",     # Lax
    0x463DFE: "Craintif",  # Timid
    0x463E04: "Pressé",    # Hasty
    0x463E0A: "Sérieux",   # Serious
    0x463E12: "Jovial",    # Jolly
    0x463E18: "Naïf",      # Naive
    0x463E1E: "Modeste",   # Modest
    0x463E25: "Doux",      # Mild
    0x463E2A: "Discret",   # Quiet
    0x463E30: "Pudique",   # Bashful
    0x463E38: "Foufou",    # Rash
    0x463E3D: "Calme",     # Calm
    0x463E42: "Gentil",    # Gentle
    0x463E49: "Malpoli",   # Sassy
    0x463E4F: "Prudent",   # Careful
    0x463E57: "Bizarre",   # Quirky
}


def find_referrers(rom: bytes, offset: int) -> list[int]:
    """Every ROM cell holding a 32-bit LE pointer to ``ROM_POINTER_BASE+offset``."""
    needle = struct.pack("<I", ROM_POINTER_BASE + offset)
    return [m.start() for m in re.finditer(re.escape(needle), rom)]


def apply(
    rom: bytearray,
    targets: dict[int, str] | None = None,
    reserved_rom: bytes | None = None,
) -> dict:
    if targets is None:
        targets = TARGETS
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    stats = {"targets": 0, "repointed": 0, "failed": 0, "skipped": 0}

    for offset, text in targets.items():
        referrers = find_referrers(rom, offset)
        if not referrers:
            stats["skipped"] += 1
            continue

        encoded = TextEncoder.encode(text, "pokemon")
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            stats["failed"] += 1
            continue
        rom[new_offset : new_offset + len(encoded)] = encoded
        pointer = struct.pack("<I", new_offset + ROM_POINTER_BASE)
        for cell in referrers:
            rom[cell : cell + 4] = pointer
            stats["repointed"] += 1
        stats["targets"] += 1

    return stats


def verify(rom: bytes) -> list[tuple[int, str]]:
    """Return targets whose live pointer(s) still reach the English original,
    or whose relocated copy doesn't decode to the expected French text."""
    bad: list[tuple[int, str]] = []
    for offset, text in TARGETS.items():
        if find_referrers(rom, offset):
            bad.append((offset, "still points to original"))
            continue
        encoded = TextEncoder.encode(text, "pokemon")[:-1]  # drop 0xFF
        if encoded not in rom:
            bad.append((offset, f"French text «{text}» not found in ROM"))
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, help="Built French ROM to patch in place")
    parser.add_argument(
        "--reference-rom",
        default=None,
        help="Same-base ROM whose populated bytes must not be reused as free space",
    )
    args = parser.parse_args()

    rom_path = Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    reserved = Path(args.reference_rom).read_bytes() if args.reference_rom else None

    stats = apply(rom, reserved_rom=reserved)
    remaining = verify(rom)
    rom_path.write_bytes(rom)

    print("✓ Nature names — relocation + repointing:")
    print(f"   - Targets relocated:      {stats['targets']}")
    print(f"   - Pointers repointed:     {stats['repointed']}")
    if stats["skipped"]:
        print(f"   - Already relocated (skip): {stats['skipped']}")
    if stats["failed"]:
        print(f"   - FAILED (free space):    {stats['failed']}")
        return 1
    if remaining:
        print("   - ✗ Verification failed:")
        for offset, why in remaining:
            print(f"       0x{offset:08X}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
