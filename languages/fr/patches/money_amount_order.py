#!/usr/bin/env python3
"""Move the POKEDOLLAR symbol after the amount in the money-display template.

The engine builds every on-screen money string (Trainer Card, shop, PC,
mart, bag…) from a single shared rodata template at file offset 0x41697A:

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

Idempotent: skips if already patched, and self-heals if re-run over a ROM
patched by an older/target order.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TEMPLATE_OFFSET = 0x41697A
ENGLISH_ORDER = bytes([0xB7, 0xFD, 0x02, 0xFF])
FRENCH_ORDER = bytes([0xFD, 0x02, 0xB7, 0xFF])


def apply(data: bytearray) -> int:
    current = bytes(data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)])
    if current == FRENCH_ORDER:
        return 0
    if current != ENGLISH_ORDER:
        raise ValueError(
            f"money template at 0x{TEMPLATE_OFFSET:06X} unexpected: {current.hex()}"
        )
    data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)] = FRENCH_ORDER
    return 1


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
