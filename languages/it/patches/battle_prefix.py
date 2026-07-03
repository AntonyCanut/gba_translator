#!/usr/bin/env python3
"""Guard the battle wild/foe name-prefix cells for Italian (report-only).

``patch_battle_prefix_fr.py`` replaces two 108-byte Thumb code caves so the
engine appends " sauvage" / " adverse" AFTER the Pokémon's name instead of
printing the prefix it naturally loads BEFORE the name — because French
grammar puts the adjective after the noun. Italian has the same
adjective-after-noun grammar ("Pidgey selvatico", not "Selvatico Pidgey"), so
strictly idiomatic Italian would need the same suffix-cave rewrite.

That ASM cave port is deliberately NOT done here: it is a distinct, higher-risk
chunk of work (hand-encoded Thumb opcodes, register-allocation-sensitive, and
only verifiable by playing an actual battle in mGBA) — out of scope for this
slice. See the follow-up ticket for porting ``patch_battle_prefix_fr.py``'s
cave to Italian.

Current state of the three prefix cells, translated by the normal
pointer-extracted-text pipeline (the ``inline`` step) from
``languages/it/combined_it.txt``:
  * 0xA4C636 (wild prefix)   -> "Il Pokémon selvatico" (renders as
    "Il Pokémon selvatico PIDGEY" — grammatically readable, if a little
    verbose, since the phrase already carries its own "Pokémon" noun)
  * 0xA4C64C (trainer prefix)-> "Il Pokémon avversario" (same pattern)
  * 0xA4C61A (trainer prefix)-> not yet present in combined_it.txt, so this
    cell still holds the English source text

What this script does: verify, after the build, that those three cells are
still valid 0xFF-terminated strings (i.e. the generic pipeline's
translation/relocation did not leave a dangling, unterminated cell — the
same collision risk ``audit_translation_collisions.py`` screens for
elsewhere). This is report-only: it never mutates the ROM and never fails
the build, matching the ``collision_check`` step's contract.

Usage:
    python3 languages/it/patches/battle_prefix.py --rom output/roms/GenedRom-it.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The three prefix cells Italian relies on the normal translated-text pipeline
# for (see languages/it/combined_it.txt for the actual Italian strings).
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
        print(
            "  battle-prefix cells OK (Italian phrases carry their own word "
            "order; the FR-style suffix cave is a follow-up, not applied here)"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    n = apply_to_rom(rom)
    print(f"patch_battle_prefix_it: {n} patch(es) applied (report-only guard)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
