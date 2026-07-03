#!/usr/bin/env python3
"""Guard the battle wild/foe name-prefix cells for German (report-only).

``patch_battle_prefix_fr.py`` replaces two 108-byte Thumb code caves so the
engine appends " sauvage" / " adverse" AFTER the Pokémon's name instead of
printing the prefix it naturally loads BEFORE the name — because French
grammar puts "sauvage"/"adverse" after the noun. That cave hack is a
word-order rewrite specific to French; it is not needed for German.

German keeps the same prefix-before-name order the engine already uses
("Das wilde PIDGEY", "Der gegnerische Rüpel sendet PIDGEY!"), so the
translations for these prefix cells — already present in
``languages/de/combined_de.txt`` at 0xA4C61A ("Der Gegner"), 0xA4C636
("wild"), 0xA4C64C ("Der Gegner") — are written in place by the normal
pointer-extracted-text pipeline (the ``inline`` step). No code cave, no
reordering, no post-build byte patch is required to get correct German
output here.

What this script does instead: verify, after the build, that those three
cells are still valid 0xFF-terminated strings (i.e. the generic pipeline's
translation/relocation did not leave a dangling, unterminated cell — the
same collision risk ``audit_translation_collisions.py`` screens for
elsewhere). This is report-only: it never mutates the ROM and never fails
the build, matching the ``collision_check`` step's contract.

Usage:
    python3 scripts/patch_battle_prefix_de.py --rom output/roms/GenedRom-de.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The three prefix cells German relies on the normal translated-text pipeline
# for (see languages/de/combined_de.txt for the actual German strings).
PREFIX_CELLS = [
    (0xA4C61A, "trainer foe prefix (1)"),
    (0xA4C636, "wild Pokémon prefix"),
    (0xA4C64C, "trainer foe prefix (2)"),
]

_MAX_SCAN = 64  # a translated prefix cell must terminate well within this


def check_cell(rom: bytes, offset: int, label: str) -> bool:
    window = rom[offset: offset + _MAX_SCAN]
    if 0xFF not in window:
        print(
            f"  WARN 0x{offset:06X} ({label}): no 0xFF terminator within "
            f"{_MAX_SCAN} bytes — possible overflow/corruption",
            file=sys.stderr,
        )
        return False
    return True


def apply_to_rom(rom: bytes) -> int:
    """Report-only check. Always returns 0 (no bytes are ever written)."""
    ok = True
    for offset, label in PREFIX_CELLS:
        ok &= check_cell(rom, offset, label)
    if ok:
        print("  battle-prefix cells OK (German uses natural prefix word order, no cave needed)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    n = apply_to_rom(rom)
    print(f"patch_battle_prefix_de: {n} patch(es) applied (report-only guard)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
