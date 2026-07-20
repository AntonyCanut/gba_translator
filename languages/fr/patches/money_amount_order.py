#!/usr/bin/env python3
"""Move the POKEDOLLAR symbol after every dynamic French amount.

The engine builds several money strings (Trainer Card, shop, PC, mart, bag…)
from a shared rodata template at file offset 0x41697A:

    B7 FD 02 FF   ->  "¥" + {STR_VAR_1} + terminator   (English order: ¥1234)

Official French Pokémon games print the amount *before* the currency glyph
(1234¥), unlike English. This template lives well below the main text
region (0x1F00000-0x1F80000), so it is never captured by the translation
pipeline (absent from `combined_fr.txt`, the injection JSON and the Spanish
extract) — a class-3 fix, patched in place exactly like
`patch_status_abbrevs_fr.py`.

The swap is a straight byte permutation of the same 4-byte cell — no pointer
relocation needed, since "{STR_VAR_1}¥" is exactly as long as "¥{STR_VAR_1}":

    FD 02 B7 FF   ->  {STR_VAR_1} + "¥" + terminator   (French order: 1234¥)

Some scripted French messages embed their own amount variable instead of using
that template, including messages without a pointer that bypass the translation
injector.  They can contain formatting control codes between the POKEDOLLAR
glyph and the variable, for example ``¥{COLOR}{STR_VAR_2}{COLOR}``.  Those
byte sequences are patched in the final ROM as well, preserving the formatting
around the amount.

Idempotent: skips sequences that already use French order.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TEMPLATE_OFFSET = 0x41697A
ENGLISH_ORDER = bytes([0xB7, 0xFD, 0x02, 0xFF])
FRENCH_ORDER = bytes([0xFD, 0x02, 0xB7, 0xFF])

POKEDOLLAR = 0xB7
EXT_CTRL = 0xFC
VAR_CTRL = 0xFD
MONEY_VARIABLES = {0x02, 0x03, 0x04}


def _variable_after_formatting(data: bytearray, start: int) -> int | None:
    """Return the variable-control offset following a POKEDOLLAR glyph.

    The only permitted bytes between the glyph and a money variable are
    ``FC 01 xx`` formatting controls.  Limiting the match to those controls
    prevents accidental rewrites of arbitrary binary data.
    """
    cursor = start + 1
    while cursor + 2 < len(data) and data[cursor] == EXT_CTRL:
        if data[cursor + 1] != 0x01:
            return None
        cursor += 3
    if (
        cursor + 1 < len(data)
        and data[cursor] == VAR_CTRL
        and data[cursor + 1] in MONEY_VARIABLES
    ):
        return cursor
    return None


def apply_inline_money_orders(data: bytearray) -> int:
    """Move currency glyphs after formatted money variables in-place."""
    patched = 0
    for offset, value in enumerate(data):
        if offset == TEMPLATE_OFFSET or value != POKEDOLLAR:
            continue
        variable_offset = _variable_after_formatting(data, offset)
        if variable_offset is None:
            continue
        variable = data[variable_offset:variable_offset + 2]
        # Remove the leading glyph, then insert it immediately after FD xx.
        # The formatting controls stay around both the value and the glyph.
        data[offset:variable_offset + 2] = (
            data[offset + 1:variable_offset] + variable + bytes([POKEDOLLAR])
        )
        patched += 1
    return patched


def apply(data: bytearray) -> int:
    current = bytes(data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)])
    if current == ENGLISH_ORDER:
        data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)] = FRENCH_ORDER
        template_patches = 1
    elif current == FRENCH_ORDER:
        template_patches = 0
    else:
        raise ValueError(
            f"money template at 0x{TEMPLATE_OFFSET:06X} unexpected: {current.hex()}"
        )
    return template_patches + apply_inline_money_orders(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, required=True)
    args = ap.parse_args()
    data = bytearray(args.rom.read_bytes())
    n = apply(data)
    if n:
        args.rom.write_bytes(data)
    print(f"patch_money_amount_order_fr: {n} patch(es) applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
