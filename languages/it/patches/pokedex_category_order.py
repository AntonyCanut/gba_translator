#!/usr/bin/env python3
"""Swap the Pokédex category/«Pokémon» order to the official Italian form.

Port of ``patch_pokedex_category_order_fr.py``. See that module's docstring
for the full reverse-engineering of ``PrintMonInfo`` at 0x105800: the info
routine renders the category buffer first and the fixed `` Pokémon`` suffix
second (``Mausratte Pokémon``-style, i.e. category-then-brand), matching the
English layout. Italian Pokédex convention puts the brand name first, exactly
like French and German: ``Pokémon Rattata``. Since "Pokémon" is spelled
identically in Italian (it is not a translated word — the brand name is
unchanged across every localisation), this patch is functionally identical to
the French/German ones: same instruction swap, same fixed suffix bytes
(``Pokémon`` already lives at 0x415F8F in every generic build, untouched by
the translation pipeline).

Every patch verifies the bytes it expects and is idempotent (an already-
patched slot is skipped without error).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# (offset, accepted_old_forms, replacement_new_bytes) — file offsets = ROM addr − 0x08000000.
# Every accepted form and the replacement are the same length (length-preserving).
PATCHES: list[tuple[int, tuple[bytes, ...], bytes]] = [
    # 1. print #1 string arg: category buffer → suffix pointer (ldr r2,[pc,#0x30])
    (0x10588C, (b"\x02\xaa",), b"\x0c\x4a"),
    # 2. width advance arg: category buffer → suffix pointer (ldr r1,[pc,#0x28])
    (0x105896, (b"\x02\xa9",), b"\x0a\x49"),
    # 3. print #2 string arg: suffix pointer → category buffer (add r2,sp,#8)
    (0x1058A4, (b"\x06\x4a",), b"\x02\xaa"),
    # 4. suffix → "Pokémon " (trailing space); accepts both historical source forms
    (0x415F8F,
     (b"\x00\xca\xe3\xdf\x1b\xe1\xe3\xe2\xff",   # " Pokémon"        (EN/ES layout)
      b"\xca\xe3\xdf\x1b\xe1\xe3\xe2\xff\xff"),  # "Pokémon" + empty (raw generic-build pipeline)
     b"\xca\xe3\xdf\x1b\xe1\xe3\xe2\x00\xff"),   # "Pokémon "
]


def apply_patches(data: bytearray, patches: list = PATCHES) -> int:
    """Apply *patches* to *data* in-place; return the number applied.

    Each entry is ``(offset, accepted_old_forms, new)``.  A slot already holding
    *new* is skipped (idempotent); a slot matching any accepted old form is
    rewritten to *new*; anything else raises ``ValueError`` so an unexpected
    layout change is never silently overwritten.
    """
    applied = 0
    for offset, olds, new in patches:
        for old in olds:
            if len(old) != len(new):
                raise ValueError(f"0x{offset:X}: length mismatch ({len(old)} vs {len(new)})")
        current = bytes(data[offset: offset + len(new)])
        if current == new:
            continue  # already patched — idempotent
        if current not in olds:
            expected = " | ".join(o.hex(' ') for o in olds)
            raise ValueError(
                f"0x{offset:X}: unexpected bytes {current.hex(' ')} "
                f"(expected one of {expected})"
            )
        data[offset: offset + len(new)] = new
        applied += 1
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-it.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    if applied:
        args.rom.write_bytes(data)
    print(f"Pokédex category-order patch applied: {applied} (of {len(PATCHES)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
