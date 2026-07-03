#!/usr/bin/env python3
"""Guard the give-CS gift item (0x01B5, "TM112"/"VM112") struct — DE port.

Same fix as ``patch_givecs_gift_item_fr.py`` (split from B-98), ported to
German. The granted item's 44-byte entry at
``0x876074 + 0x01B5*44 = 0x87AB90`` is a fixed, never-repointed struct. Bytes
20-23 (the description pointer at ``+0x14``) target an English slot that is
empty (``0xFF``) in the source ROM, so the item never renders a bag
description on English. If any generic-language build pass ever writes a
translated (relocated) description into that slot — e.g. because the offset
also carries the shared move-description text for "Round", legitimately
translated elsewhere in ``combined_de.txt`` — the struct silently diverges
from English even though this item's obtain box only ever reads the static
item *name* cell, never this description.

Fix: restore the struct byte-for-byte from English, except the 2-byte name
prefix (``TM`` in German — Pokémon's official German TM abbreviation is
identical to English, so nothing needs to change there either way) which is
the localized cell. Idempotent: a no-op once the struct already matches.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

GBA_BASE = 0x08000000

ITEM_TABLE_BASE = 0x876074
ITEM_STRIDE = 44
GIVE_CS_ITEM_ID = 0x01B5
ITEM_ENTRY_OFF = ITEM_TABLE_BASE + GIVE_CS_ITEM_ID * ITEM_STRIDE

# Bytes 0-1 of the 14-byte name cell are the localized "TM" prefix (German
# keeps the same "TM" abbreviation as English); everything from byte 2 onward
# (digits, terminator, padding, item id, price, hold-effect, description
# pointer, pocket/type, field-use pointer, battle-use pointer...) must stay
# byte-identical to English.
NAME_PREFIX_LEN = 2


def apply_to_rom(rom: bytearray, en: bytes, dry_run: bool = False) -> int:
    en_tail = en[ITEM_ENTRY_OFF + NAME_PREFIX_LEN:ITEM_ENTRY_OFF + ITEM_STRIDE]
    cur_tail = rom[ITEM_ENTRY_OFF + NAME_PREFIX_LEN:ITEM_ENTRY_OFF + ITEM_STRIDE]
    if cur_tail == en_tail:
        return 0  # already correct (idempotent)

    if not dry_run:
        rom[ITEM_ENTRY_OFF + NAME_PREFIX_LEN:ITEM_ENTRY_OFF + ITEM_STRIDE] = en_tail

    print(
        f"  0x{ITEM_ENTRY_OFF + NAME_PREFIX_LEN:06X}..0x{ITEM_ENTRY_OFF + ITEM_STRIDE - 1:06X}  "
        f"give-CS item 0x{GIVE_CS_ITEM_ID:X} struct {cur_tail.hex()} -> {en_tail.hex()} "
        f"(restored to English; name prefix stays localized)",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path, help="pristine EN ROM")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rom = bytearray(args.rom.read_bytes())
    en = args.source.read_bytes()
    n = apply_to_rom(rom, en, dry_run=args.dry_run)
    if not args.dry_run and n:
        args.rom.write_bytes(rom)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_givecs_gift_item_de: {n} patch(es) applied{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
