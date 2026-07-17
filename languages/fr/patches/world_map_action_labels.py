#!/usr/bin/env python3
"""Abrège uniquement les actions de la carte mondiale (#111).

La carte réutilise la chaîne partagée ``gText_Cancel`` (« Annuler »), également
consommée par de nombreux autres menus. Les deux littéraux propres à la carte
sont donc redirigés vers une chaîne dédiée « Annul. » dans le padding final de
la ROM, sans modifier la chaîne partagée.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path


ROM_BASE = 0x08000000
ROM_LIMIT = 0x0A000000
CANCEL_LABEL_POINTERS = (0xA6CA2C, 0xA6CA64)

ANNULER_BYTES = bytes.fromhex("bbe2e2e9e0d9e6ff")
ANNUL_BYTES = bytes.fromhex("bbe2e2e9e0adff")
ANNUL_STR_OFFSET = 0x1FFFF70
ANNUL_CPU_ADDR = ROM_BASE + ANNUL_STR_OFFSET


def apply(rom: bytearray) -> int:
    """Redirige les deux libellés « Annuler » propres à la carte."""
    current_pointers = tuple(
        struct.unpack_from("<I", rom, pointer)[0]
        for pointer in CANCEL_LABEL_POINTERS
    )

    if (
        all(pointer == ANNUL_CPU_ADDR for pointer in current_pointers)
        and rom[ANNUL_STR_OFFSET:ANNUL_STR_OFFSET + len(ANNUL_BYTES)]
        == ANNUL_BYTES
    ):
        return 0

    for pointer_offset, target in zip(CANCEL_LABEL_POINTERS, current_pointers):
        if target == ANNUL_CPU_ADDR:
            continue
        if not (ROM_BASE <= target < ROM_LIMIT):
            print(
                f"  WARN world-map cancel: 0x{pointer_offset:07X} -> "
                f"0x{target:08X} n'est pas un pointeur ROM — abandon",
                file=sys.stderr,
            )
            return 0
        target_offset = target - ROM_BASE
        actual = bytes(rom[target_offset:target_offset + len(ANNULER_BYTES)])
        if actual != ANNULER_BYTES:
            print(
                f"  WARN world-map cancel: 0x{pointer_offset:07X} ne pointe pas "
                f"vers « Annuler » ({actual.hex()}) — abandon",
                file=sys.stderr,
            )
            return 0

    slot = bytes(rom[ANNUL_STR_OFFSET:ANNUL_STR_OFFSET + len(ANNUL_BYTES)])
    if slot != ANNUL_BYTES and any(byte != 0xFF for byte in slot):
        print(
            f"  WARN world-map cancel: emplacement 0x{ANNUL_STR_OFFSET:07X} "
            f"occupé ({slot.hex()}) — abandon",
            file=sys.stderr,
        )
        return 0

    rom[ANNUL_STR_OFFSET:ANNUL_STR_OFFSET + len(ANNUL_BYTES)] = ANNUL_BYTES
    patched = 0
    for pointer_offset, target in zip(CANCEL_LABEL_POINTERS, current_pointers):
        if target != ANNUL_CPU_ADDR:
            struct.pack_into("<I", rom, pointer_offset, ANNUL_CPU_ADDR)
            patched += 1
    print(f"  world-map cancel: {patched} pointeur(s) → « Annul. »")
    return patched


def main() -> int:
    """Applique le patch à la ROM française construite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        type=Path,
        default=Path("output/roms/GenedRom-fr.gba"),
    )
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")

    original = args.rom.read_bytes()
    if original[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {args.rom}")

    rom = bytearray(original)
    patched = apply(rom)
    if patched:
        Path(f"{args.rom}.bak").write_bytes(original)
        args.rom.write_bytes(rom)
    print(f"patch_world_map_action_labels_fr: {patched} pointeur(s) redirigé(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
