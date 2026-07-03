#!/usr/bin/env python3
"""Guard the give-CS gift item (0x01B5, "TM112"/"CT112") struct.

Ticket "give-CS (Éclate-Roc) item-gift struct diverges from English — risk of
freeze" (split from B-98). ``verify_user_rom_givecs.py`` flags the granted
item's 44-byte entry at ``0x876074 + 0x01B5*44 = 0x87AB90`` as DIVERGENT from
English: bytes 20-23 (the description pointer at ``+0x14``) hold a relocated
French address instead of the English value.

Root cause
----------
The English slot the description pointer targets (``0x08A3A77D``) is empty —
an immediate ``0xFF`` — in the source ROM, so the item never renders a bag
description on English. ``apply_inline_overrides_fr.py`` still writes the
French translation that ``combined_fr.txt`` happens to carry for that offset
(it is also the shared move-description text for "Round", legitimately
translated elsewhere), which overflows the zero-byte English slot. By the time
``patch_tm_item_descriptions_fr.py`` runs, item 0x01B5 matches its ``CT``/``CS``
machine-name prefix (the FR item name was correctly localized "TM112" →
"CT112") and the now-unterminated description is swept up and relocated like
any other overflowing TM/HM description — even though this specific item's
docstring already called out that it should stay untouched (its obtain box
renders the static item *name*, never this description).

The relocated copy is itself well-formed (terminated, no dangling control
code) so this is not a live freeze today, but it leaves the gift item's struct
silently diverged from the documented/tested invariant
(``tests/e2e/fr/test_object_gain_sequence.py::test_give_cs_item_struct_matches_english``)
and one relocation slot away from repeating the original "pas de gain d'objet"
freeze class if a future build pass relocates the same text less carefully.

Fix
---
This item's description is provably dead code on the gift path (only its name
cell is read there) and matches no real in-game use the project exercises, so
the safest fix is the same one already used elsewhere for protected fixed-
offset structs: restore the struct byte-for-byte from English, except the
2-byte name prefix (``TM`` → ``CT``) which is the intentional localization.
Idempotent: a no-op once the struct already matches.
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

# Bytes 0-1 of the 14-byte name cell are the localized "TM" -> "CT" prefix
# (feat c4fb226); everything from byte 2 onward (digits, terminator, padding,
# item id, price, hold-effect, description pointer, pocket/type, field-use
# pointer, battle-use pointer...) must stay byte-identical to English.
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
        f"(restored to English; name prefix stays FR)",
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
    print(f"patch_givecs_gift_item_fr: {n} patch(es) applied{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
