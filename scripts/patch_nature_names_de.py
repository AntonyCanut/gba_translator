#!/usr/bin/env python3
"""Translate the compact Pokémon nature-name table (starter gift, party menu…) to German.

See ``patch_nature_names_fr.py`` for the full root-cause writeup: the 25
nature names are packed back-to-back as ``0xFF``-terminated strings at
``0x463DBC``-``0x463E5D``, outside the main text region the generic pipeline
extracts from. Each name has exactly two live pointer referrers (a 25x4-byte
table at ``0x463E60`` used in code, and a second identical 25x4-byte table at
``0x1FE65F4`` used by another screen).

This post-build patch relocates one ``0xFF``-terminated copy of each official
German nature name into free space and repoints every live referrer to it, so
word length is never budget-constrained by the (shorter) English original.
Reference-driven and idempotent, exactly like the French version.
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

# English ROM offset (first byte of the EN string) -> official German nature
# name. Order matches the in-game nature index (0 = Hardy .. 24 = Quirky).
TARGETS: dict[int, str] = {
    0x463DBC: "Robust",     # Hardy
    0x463DC2: "Einsam",     # Lonely
    0x463DC9: "Mutig",      # Brave
    0x463DCF: "Hart",       # Adamant
    0x463DD7: "Frech",      # Naughty
    0x463DDF: "Kühn",       # Bold
    0x463DE4: "Sanftmut",   # Docile
    0x463DEB: "Locker",     # Relaxed
    0x463DF3: "Schelmisch", # Impish
    0x463DFA: "Nachlässig", # Lax
    0x463DFE: "Ängstlich",  # Timid
    0x463E04: "Hastig",     # Hasty
    0x463E0A: "Ernst",      # Serious
    0x463E12: "Froh",       # Jolly
    0x463E18: "Naiv",       # Naive
    0x463E1E: "Bescheiden", # Modest
    0x463E25: "Mild",       # Mild
    0x463E2A: "Still",      # Quiet
    0x463E30: "Schüchtern", # Bashful
    0x463E38: "Hitzig",     # Rash
    0x463E3D: "Ruhig",      # Calm
    0x463E42: "Zart",       # Gentle
    0x463E49: "Pfiffig",    # Sassy
    0x463E4F: "Vorsichtig", # Careful
    0x463E57: "Wunderlich", # Quirky
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
    or whose relocated copy doesn't decode to the expected German text."""
    bad: list[tuple[int, str]] = []
    for offset, text in TARGETS.items():
        if find_referrers(rom, offset):
            bad.append((offset, "still points to original"))
            continue
        encoded = TextEncoder.encode(text, "pokemon")[:-1]  # drop 0xFF
        if encoded not in rom:
            bad.append((offset, f"German text «{text}» not found in ROM"))
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, help="Built German ROM to patch in place")
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

    print("✓ Nature names (DE) — relocation + repointing:")
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
