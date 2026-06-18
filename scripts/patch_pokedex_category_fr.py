#!/usr/bin/env python3
"""Restore the space between the Pokédex category and the word "Pokémon" (FR).

The Pokédex info screen shows a species' category as ``<category> Pokémon``
(e.g. "Souris Pokémon" / "Mouse Pokémon").  The renderer draws the category
word into a scratch buffer and then prints a *separate* string —
``" Pokémon"`` — whose **leading space** is the only separator between the two
(the category buffer is right-aligned to end exactly where this suffix
begins).  That suffix is a fixed-address string at file offset ``0x415F8F``
which the dex code references by an absolute pointer.

In both the English and Spanish source ROMs the suffix is stored with its
leading space:

    00 ca e3 df 1b e1 e3 e2 ff   →   " Pokémon"

The French text-injection pipeline rewrote this fixed string block and dropped
the leading ``0x00`` (space) byte, leaving:

    ca e3 df 1b e1 e3 e2 ff ff   →   "Pokémon" (+ an empty trailing slot)

so the category and the word fused on screen as e.g. "SourisPokémon" /
"MousePokemon".  The fix restores the exact English/Spanish byte layout of the
9-byte slot — no pointer changes, no shifting of the adjacent "Ht"/"Wt"/"lbs."
labels at ``0x415F98``:

    0x415F8F:  ca e3 df 1b e1 e3 e2 ff ff   →   00 ca e3 df 1b e1 e3 e2 ff

This is a class-3 post-build patch (committed code, fixed offset, identical
byte length) so it is immune to ``combined_fr.txt`` / translation-JSON
regeneration.  A pointer aimed at the old ``0x415F90`` start still reads
"Pokémon" after the patch (that byte is unchanged), exactly as in the English
ROM, so every consumer of this string block keeps working.

Usage:
    python3 scripts/patch_pokedex_category_fr.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
from pathlib import Path

# File offset of the " Pokémon" suffix the Pokédex appends after the category.
CATEGORY_SUFFIX_OFFSET = 0x415F8F

# (offset, expected_old_bytes, replacement_new_bytes)
#   old: "Pokémon\xff" + trailing empty-string \xff  (FR pipeline, space lost)
#   new: " Pokémon\xff"                              (English/Spanish layout)
PATCHES: list[tuple[int, bytes, bytes]] = [
    (CATEGORY_SUFFIX_OFFSET,
     bytes.fromhex("cae3df1be1e3e2ffff"),
     bytes.fromhex("00cae3df1be1e3e2ff")),
]


def apply_patches(data: bytearray, patches: list = PATCHES) -> int:
    """Apply *patches* to *data* in-place; return the number applied.

    Each patch is length-preserving and idempotent: a slot already holding the
    replacement is skipped, and unexpected bytes raise ``ValueError`` so a
    layout change in the source block is never silently overwritten.
    """
    applied = 0
    for offset, old, new in patches:
        if len(old) != len(new):
            raise ValueError(f"0x{offset:X}: length mismatch ({len(old)} vs {len(new)})")
        current = bytes(data[offset: offset + len(old)])
        if current == new:
            continue  # already patched — idempotent
        if current != old:
            raise ValueError(
                f"0x{offset:X}: unexpected bytes {current.hex(' ')} "
                f"(expected {old.hex(' ')})"
            )
        data[offset: offset + len(new)] = new
        applied += 1
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"),
                        help="Built French ROM to patch in place")
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    if applied:
        args.rom.write_bytes(data)
    print(f"Pokédex category-space patch applied: {applied} (of {len(PATCHES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
