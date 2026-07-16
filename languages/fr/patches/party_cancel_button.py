#!/usr/bin/env python3
"""Rename the party-menu bottom button « Annuler » → « Sortir » (issue #104 follow-up).

The Pokémon party list shows a persistent bottom-right button that closes the menu.
Unbound draws it from the generic ``gText_Cancel`` string ("Annuler" in FR), which is
*shared* with the Bag, Shop, PC and every other « Annuler » in the game — so the fix
must NOT edit that shared string (it would rename every Cancel to "Sortir"). Instead
we retarget only the party menu's own code literal.

Isolation (verified in mGBA)
----------------------------
The party-menu draw code loads its Cancel-string pointer from a **single code literal**
at ROM ``0x1211E8``. In the built FR ROM it points at the relocated shared "Annuler"
string (``0x08E58DB2``). Repointing *only* this literal changes the party bottom button
to "Sortir" and nothing else — every other « Annuler » keeps its shared string
(binary-search-confirmed: of the 18 sites that reference ``gText_Cancel``, only
``0x1211E8`` drives this button).

Fix
---
Write a dedicated "Sortir" string into the ROM's unused ``0xFF`` tail padding and repoint
the literal at ``0x1211E8`` to it. Self-contained (no coupling to any other translated
string), idempotent and self-healing. Runs in the ``build-fr`` post-build chain.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

# Code literal (in the Unbound party-menu draw routine) holding the Cancel pointer.
PARTY_CANCEL_PTR = 0x1211E8

# CFRU-encoded strings (+ 0xFF terminator). "Annuler" is the shared gText_Cancel the
# literal points at before patching; "Sortir" is the dedicated replacement.
ANNULER_BYTES = bytes.fromhex("bbe2e2e9e0d9e6ff")  # "Annuler"
SORTIR_BYTES = bytes.fromhex("cde3e6e8dde6ff")     # "Sortir"

# Dedicated home for the "Sortir" string: unused 0xFF ROM tail padding.
SORTIR_STR_OFFSET = 0x1FFFF80
SORTIR_CPU_ADDR = 0x08000000 + SORTIR_STR_OFFSET

ROM_BASE = 0x08000000


def apply(rom: bytearray) -> int:
    cur = struct.unpack_from("<I", rom, PARTY_CANCEL_PTR)[0]

    # Idempotent: already repointed to our own "Sortir" string.
    if (cur == SORTIR_CPU_ADDR
            and rom[SORTIR_STR_OFFSET:SORTIR_STR_OFFSET + len(SORTIR_BYTES)] == SORTIR_BYTES):
        return 0

    # Safety: the literal must currently point at the shared "Annuler" string.
    if not (ROM_BASE <= cur < 0x0A000000):
        print(f"  WARN party cancel: literal 0x{PARTY_CANCEL_PTR:07X} -> 0x{cur:08X} "
              f"is not a ROM pointer — skip", file=sys.stderr)
        return 0
    tgt = cur - ROM_BASE
    if bytes(rom[tgt:tgt + len(ANNULER_BYTES)]) != ANNULER_BYTES:
        print(f"  WARN party cancel: literal 0x{PARTY_CANCEL_PTR:07X} does not point at "
              f"« Annuler » (got {bytes(rom[tgt:tgt+8]).hex()}) — skip", file=sys.stderr)
        return 0

    # The target slot must be free (0xFF padding) or already hold our string.
    slot = bytes(rom[SORTIR_STR_OFFSET:SORTIR_STR_OFFSET + len(SORTIR_BYTES)])
    if slot != SORTIR_BYTES and any(b != 0xFF for b in slot):
        print(f"  WARN party cancel: tail slot 0x{SORTIR_STR_OFFSET:07X} is not free "
              f"(got {slot.hex()}) — skip", file=sys.stderr)
        return 0

    rom[SORTIR_STR_OFFSET:SORTIR_STR_OFFSET + len(SORTIR_BYTES)] = SORTIR_BYTES
    struct.pack_into("<I", rom, PARTY_CANCEL_PTR, SORTIR_CPU_ADDR)
    print(f"  party cancel button (literal 0x{PARTY_CANCEL_PTR:07X}): « Annuler » → « Sortir »")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path,
                    default=Path("output/roms/GenedRom-fr.gba"))
    args = ap.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    rom = bytearray(args.rom.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {args.rom}")
    n = apply(rom)
    if n:
        args.rom.write_bytes(rom)
    print(f"patch_party_cancel_button_fr: {n} button renamed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
