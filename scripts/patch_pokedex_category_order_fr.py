#!/usr/bin/env python3
"""Swap the Pokédex category/«Pokémon» order to the official French form.

After ``patch_pokedex_categories_fr.py`` the species category is in French but
the on-screen order is still English: ``Souris Pokémon`` (category first, fixed
suffix `` Pokémon`` second).  The official French Pokédex layout is the reverse:
``Pokémon Souris`` (``Pokémon`` first, category second).

──────────────────────────────────────────────────────────────────────────
How the info routine (PrintMonInfo at 0x105800) renders the line
──────────────────────────────────────────────────────────────────────────

The routine copies the category string into a stack buffer at ``sp+8`` and then
renders two pieces, advancing the x cursor (r6) between them::

    0810588C  add  r2, sp, #8        ; r2 = category buffer
    0810588E  adds r3, r6, #0        ; x = r6 (initial)
    08105890  bl   0x81047C8         ; print #1  -> category at x
    08105896  add  r1, sp, #8        ; r1 = category buffer
    0810589A  bl   0x8005ED4         ; GetStringWidth(category)
    0810589E  adds r0, r6, r0        ; r6 += width(category)
    081058A4  ldr  r2, [pc, #0x18]   ; r2 = &" Pokémon"  (literal @0x1058C0)
    081058AE  adds r3, r6, #0        ; x = advanced r6
    081058B0  bl   0x81047C8         ; print #2  -> " Pokémon" after the category

So print #1 = category, advance by category width, print #2 = `` Pokémon``.
Result: ``Souris Pokémon``.

To obtain ``Pokémon Souris`` we keep the exact same structure (print at r6,
advance r6 by the *first* string's width, print at the advanced r6) and only
swap **which string is first**:

  * print #1 must render ``Pokémon`` (the suffix) → its string arg becomes the
    suffix pointer instead of the category buffer;
  * the width measured for the advance must be the suffix width → the
    ``GetStringWidth`` argument becomes the suffix pointer too;
  * print #2 must render the category → its string arg becomes the buffer.

The suffix pointer already lives in the literal pool at 0x1058C0
(``0x08415F8F`` → `` Pokémon``).  Both `` add rX, sp, #8 `` instructions are
replaced by ``ldr rX, [pc, #imm]`` re-using that same literal (no new literal,
no relocation):

  1. 0x10588C  ``add r2, sp, #8`` (02 AA) → ``ldr r2, [pc, #0x30]`` (0C 4A)
               print #1 now points at the suffix.
  2. 0x105896  ``add r1, sp, #8`` (02 A9) → ``ldr r1, [pc, #0x28]`` (0A 49)
               width advance now measures the suffix.
  3. 0x1058A4  ``ldr r2, [pc, #0x18]`` (06 4A) → ``add r2, sp, #8`` (02 AA)
               print #2 now points at the category buffer.

Both ``ldr`` resolve to 0x1058C0 (PC-relative, word-aligned): for #1
Align(0x105890,4)+0x30 = 0x1058C0; for #2 Align(0x105898,4)+0x28 = 0x1058C0.

──────────────────────────────────────────────────────────────────────────
The suffix string (this patch is the single authority for it)
──────────────────────────────────────────────────────────────────────────

The fixed suffix at 0x415F8F must end up as ``Pokémon `` — a **trailing**
space, so it reads correctly *before* the category::

    CA E3 DF 1B E1 E3 E2 00 FF   "Pokémon "   (trailing space, target)

Two earlier source states of this 9-byte slot are accepted (it used to render
*after* the category, hence the historical leading space):

    00 CA E3 DF 1B E1 E3 E2 FF   " Pokémon"            (EN/ES layout)
    CA E3 DF 1B E1 E3 E2 FF FF   "Pokémon" + empty     (raw FR pipeline, space lost)

Accepting both means this patch fully subsumes the old
``patch_pokedex_category_fr.py`` (which only restored the leading space): the
space and the order are now fixed together, in one place.  The byte length —
and therefore the ``0x08415F8F`` pointer in the literal pool — is unchanged.

Every patch verifies the bytes it expects and is idempotent (an already-patched
slot is skipped without error).  Run by ``make build-fr`` after
``patch_pokedex_categories_fr.py``.

Usage:
    python3 scripts/patch_pokedex_category_order_fr.py --rom output/roms/GenedRom-fr.gba
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
      b"\xca\xe3\xdf\x1b\xe1\xe3\xe2\xff\xff"),  # "Pokémon" + empty (raw FR pipeline)
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
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    if applied:
        args.rom.write_bytes(data)
    print(f"Pokédex category-order patch applied: {applied} (of {len(PATCHES)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
