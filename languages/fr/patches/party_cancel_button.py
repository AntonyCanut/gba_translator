#!/usr/bin/env python3
"""Rename menu exit actions « Annuler » → « Sortir » (issues #104 and #168).

The Pokémon party list and the Player PC's Item Storage submenu both expose exit actions.
Unbound draws them from the generic ``gText_Cancel`` string ("Annuler" in FR), which is
shared with every real cancellation action — so the fix must NOT edit that shared string.
Instead, retarget only the two menu pointers that semantically mean "Exit".

Isolation (verified in mGBA)
----------------------------
The party-menu draw code uses the literal at ROM ``0x1211E8``. The Player PC action table
uses the entry at ``0x402218``. Repointing only these sites changes both exit actions to
"Sortir" while every other « Annuler » keeps the shared string.

Fix
---
Write a dedicated "Sortir" string into the ROM's unused ``0xFF`` tail padding and repoint
the two sites to it. Self-contained, idempotent and self-healing. Runs in the ``build-fr``
post-build chain.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

# Code literal (in the Unbound party-menu draw routine) holding the Cancel pointer.
PARTY_CANCEL_PTR = 0x1211E8

# gFameCheckerText_Cancel entry in sMenuActions_ItemPc (Player PC Item Storage).
PLAYER_PC_CANCEL_PTR = 0x402218

EXIT_POINTERS = (PARTY_CANCEL_PTR, PLAYER_PC_CANCEL_PTR)

# CFRU-encoded strings (+ 0xFF terminator). "Annuler" is the shared gText_Cancel the
# literal points at before patching; "Sortir" is the dedicated replacement.
ANNULER_BYTES = bytes.fromhex("bbe2e2e9e0d9e6ff")  # "Annuler"
SORTIR_BYTES = bytes.fromhex("cde3e6e8dde6ff")     # "Sortir"

# Dedicated home for the "Sortir" string: unused 0xFF ROM tail padding.
SORTIR_STR_OFFSET = 0x1FFFF80
SORTIR_CPU_ADDR = 0x08000000 + SORTIR_STR_OFFSET

ROM_BASE = 0x08000000


def apply(rom: bytearray) -> int:
    current = {
        pointer_site: struct.unpack_from("<I", rom, pointer_site)[0]
        for pointer_site in EXIT_POINTERS
    }
    slot = bytes(rom[SORTIR_STR_OFFSET:SORTIR_STR_OFFSET + len(SORTIR_BYTES)])

    # Idempotent: every exit action already points to our own "Sortir" string.
    if all(pointer == SORTIR_CPU_ADDR for pointer in current.values()) and slot == SORTIR_BYTES:
        return 0

    # Safety: each site must already target our string or the shared "Annuler" string.
    for pointer_site, pointer in current.items():
        if pointer == SORTIR_CPU_ADDR and slot == SORTIR_BYTES:
            continue
        if not (ROM_BASE <= pointer < 0x0A000000):
            print(f"  WARN menu exit: pointer 0x{pointer_site:07X} -> 0x{pointer:08X} "
                  f"is not a ROM pointer — skip", file=sys.stderr)
            return 0
        target = pointer - ROM_BASE
        actual = bytes(rom[target:target + len(ANNULER_BYTES)])
        if actual != ANNULER_BYTES:
            print(f"  WARN menu exit: pointer 0x{pointer_site:07X} does not target "
                  f"« Annuler » (got {actual.hex()}) — skip", file=sys.stderr)
            return 0

    # The target slot must be free (0xFF padding) or already hold our string.
    if slot != SORTIR_BYTES and any(b != 0xFF for b in slot):
        print(f"  WARN menu exit: tail slot 0x{SORTIR_STR_OFFSET:07X} is not free "
              f"(got {slot.hex()}) — skip", file=sys.stderr)
        return 0

    rom[SORTIR_STR_OFFSET:SORTIR_STR_OFFSET + len(SORTIR_BYTES)] = SORTIR_BYTES
    changed = 0
    for pointer_site, pointer in current.items():
        if pointer != SORTIR_CPU_ADDR:
            struct.pack_into("<I", rom, pointer_site, SORTIR_CPU_ADDR)
            print(f"  menu exit (pointer 0x{pointer_site:07X}): « Annuler » → « Sortir »")
            changed += 1
    return changed


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
    print(f"patch_party_cancel_button_fr: {n} exit label(s) renamed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
