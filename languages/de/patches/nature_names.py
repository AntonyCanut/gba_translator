#!/usr/bin/env python3
"""Translate the compact Pokémon nature-name table (starter gift, party menu…) to German.

See ``patch_nature_names_fr.py`` for the full root-cause writeup: the 25
nature names are packed back-to-back as ``0xFF``-terminated strings at
``0x463DBC``-``0x463E5D``, outside the main text region the generic pipeline
extracts from. Each name is referenced by exactly two live 25x4-byte pointer
tables (one at ``0x463E60`` used in code, an identical one at ``0x1FE65F4``
used by another screen); in the English ROM both tables' entry *i* point at
the same shared string.

This post-build patch relocates one ``0xFF``-terminated copy of each official
German nature name into free space and repoints both tables to it, so word
length is never budget-constrained by the (shorter) English original.

Unlike the French dedicated build, the **generic** German driver
(``build_language.py de``) has already relocated + repointed these tables by
the time this patch runs: ``combined_de.txt`` carries hand-added nature entries
that the generic reinserter applies first, so *no* table entry still points at
the original ``0x463DBC..`` offsets. A referrer-search keyed on those original
offsets therefore finds nothing and skips every name (the B-158 blocker).

So this patch works **by table index** instead: for each nature index 0..24 it
writes the official German name to fresh free space and rewrites entry *i* of
both pointer tables to it — authoritative and independent of whatever the
generic build left the pointers aimed at. Verification follows the live table
pointer and compares the exact encoded bytes (no whole-ROM substring search,
which gave false positives on common words and false negatives on umlauts).
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from languages.de.terminology import section as terminology_section  # noqa: E402
from src.core.text_codec import GERMAN_UMLAUT_CHARS, TextEncoder  # noqa: E402
from src.core.text_reinserter import FreeSpaceAllocator  # noqa: E402

ROM_POINTER_BASE = 0x08000000

# The two live 25×4-byte pointer tables that reference the nature-name strings.
# Both are entered by in-game nature index (0 = Hardy .. 24 = Quirky); in the
# English ROM entry *i* of each points at the same shared string.
POINTER_TABLES: tuple[int, ...] = (0x463E60, 0x1FE65F4)
NATURE_COUNT = 25

# English ROM offset (first byte of the EN string) -> official German nature
# name. Order matches the in-game nature index (0 = Hardy .. 24 = Quirky); the
# insertion order below IS the nature-index order the pointer tables use.
TARGETS: dict[int, str] = {
    0x463DBC: "Robust",  # Hardy
    0x463DC2: "Solo",    # Lonely
    0x463DC9: "Mutig",   # Brave
    0x463DCF: "Hart",    # Adamant
    0x463DD7: "Frech",   # Naughty
    0x463DDF: "Kühn",    # Bold
    0x463DE4: "Sanft",   # Docile
    0x463DEB: "Locker",  # Relaxed
    0x463DF3: "Pfiffig", # Impish
    0x463DFA: "Lasch",   # Lax
    0x463DFE: "Scheu",   # Timid
    0x463E04: "Hastig",  # Hasty
    0x463E0A: "Ernst",   # Serious
    0x463E12: "Froh",    # Jolly
    0x463E18: "Naiv",    # Naive
    0x463E1E: "Mäßig",   # Modest
    0x463E25: "Mild",    # Mild
    0x463E2A: "Ruhig",   # Quiet
    0x463E30: "Zaghaft", # Bashful
    0x463E38: "Hitzig",  # Rash
    0x463E3D: "Still",   # Calm
    0x463E42: "Zart",    # Gentle
    0x463E49: "Forsch",  # Sassy
    0x463E4F: "Sacht",   # Careful
    0x463E57: "Kauzig",  # Quirky
}

OFFICIAL_NATURES = terminology_section("natures")
if list(TARGETS.values()) != list(OFFICIAL_NATURES.values()):
    raise ValueError("German nature table diverges from official_terminology.yaml")


def find_referrers(rom: bytes, offset: int) -> list[int]:
    """Every ROM cell holding a 32-bit LE pointer to ``ROM_POINTER_BASE+offset``."""
    needle = struct.pack("<I", ROM_POINTER_BASE + offset)
    return [m.start() for m in re.finditer(re.escape(needle), rom)]


def _table_pointer(rom: bytes, table: int, index: int) -> int:
    """Live 32-bit pointer stored at entry ``index`` of ``table``."""
    return struct.unpack_from("<I", rom, table + 4 * index)[0]


def apply(
    rom: bytearray,
    names: list[str] | None = None,
    tables: tuple[int, ...] = POINTER_TABLES,
    reserved_rom: bytes | None = None,
) -> dict:
    """Repoint every nature-name pointer-table entry, by index, at a fresh copy
    of the official German name.

    The generic German build has already relocated + repointed these tables
    (from ``combined_de.txt``), so we cannot key on the original English string
    offsets. We instead walk each table by index and overwrite entry *i* of
    every table with a pointer to a newly-allocated German string, mirroring the
    English ROM's shared-string layout (both tables' entry *i* point at the same
    copy). Idempotent: an entry already pointing at the correct German bytes is
    left untouched.
    """
    if names is None:
        names = list(TARGETS.values())
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    stats = {"relocated": 0, "repointed": 0, "failed": 0, "skipped": 0}

    for index, text in enumerate(names):
        encoded = TextEncoder.encode(text, "pokemon", skip_aliases=GERMAN_UMLAUT_CHARS)

        # Already correct (re-run on an already-patched ROM)? Leave it alone.
        current = _table_pointer(rom, tables[0], index) - ROM_POINTER_BASE
        if 0 <= current <= len(rom) - len(encoded) and (
            rom[current : current + len(encoded)] == encoded
        ):
            stats["skipped"] += 1
            continue

        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            stats["failed"] += 1
            continue
        rom[new_offset : new_offset + len(encoded)] = encoded
        pointer = struct.pack("<I", new_offset + ROM_POINTER_BASE)
        for table in tables:
            cell = table + 4 * index
            rom[cell : cell + 4] = pointer
            stats["repointed"] += 1
        stats["relocated"] += 1

    return stats


def verify(
    rom: bytes,
    names: list[str] | None = None,
    tables: tuple[int, ...] = POINTER_TABLES,
) -> list[tuple[int, str]]:
    """Return problems, following each table's live pointer and comparing the
    exact encoded bytes (no whole-ROM substring search — that gave false
    positives on common words and false negatives on umlaut encodings)."""
    if names is None:
        names = list(TARGETS.values())
    bad: list[tuple[int, str]] = []
    for index, text in enumerate(names):
        # incl. 0xFF terminator; skip_aliases keeps ü/ä/ö on their glyph slots
        # (0xF1-0xF6) instead of the ASCII-fallback aliases other languages use.
        want = TextEncoder.encode(text, "pokemon", skip_aliases=GERMAN_UMLAUT_CHARS)
        pointers = [_table_pointer(rom, table, index) for table in tables]
        if len(set(pointers)) != 1:
            bad.append(
                (tables[1] + 4 * index, f"index {index}: pointer tables disagree")
            )
            continue
        off = pointers[0] - ROM_POINTER_BASE
        got = rom[off : off + len(want)]
        if got != want:
            bad.append(
                (
                    tables[0] + 4 * index,
                    f"index {index}: «{text}» not correctly repointed",
                )
            )
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
    print(f"   - Names relocated:        {stats['relocated']}")
    print(f"   - Pointers repointed:     {stats['repointed']}")
    if stats["skipped"]:
        print(f"   - Already correct (skip): {stats['skipped']}")
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
