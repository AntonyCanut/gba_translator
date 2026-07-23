#!/usr/bin/env python3
"""Stabilise le bandeau d'action de la carte mondiale (#111 / #131).

Le bandeau de déplacement est chargé par le littéral ``0x9FB64``. La source
FR courte existe à ``0x418E77``, mais le build générique peut conserver une
ancienne cellule terminée par « Annul. » ou laisser le littéral pointer vers
une relocalisation périmée. Le correctif source seul ne survit donc pas à tous
les rebuilds.

Ce patch post-build réécrit la cellule canonique, qui tient dans son emplacement
original, puis repointe inconditionnellement le seul littéral du bandeau vers
elle. Il est déterministe, idempotent et ne touche pas les autres libellés
« Annul. » de la carte ni le « Annuler » partagé du menu Équipe.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


ROM_BASE = 0x08000000
WORLD_MAP_HINT_POINTER = 0x9FB64
WORLD_MAP_HINT_OFFSET = 0x418E77
WORLD_MAP_HINT_CPU_ADDR = ROM_BASE + WORLD_MAP_HINT_OFFSET

# {DPAD_ANY}Dépl. {SE_SHOP}OK {B_BUTTON}Annul + terminateur CFRU.
WORLD_MAP_HINT_BYTES = bytes.fromhex(
    "f80cbe1be4e0ad00f800c9c500f801bbe2e2e9e0ff"
)


def apply(rom: bytearray) -> int:
    """Restaure la cellule courte et son pointeur vivant.

    Returns:
        Nombre d'éléments modifiés (cellule et/ou pointeur).
    """
    minimum_size = max(
        WORLD_MAP_HINT_POINTER + 4,
        WORLD_MAP_HINT_OFFSET + len(WORLD_MAP_HINT_BYTES),
    )
    if len(rom) < minimum_size:
        raise ValueError(
            f"ROM trop courte ({len(rom)} octets, minimum {minimum_size})"
        )

    patched = 0
    hint_end = WORLD_MAP_HINT_OFFSET + len(WORLD_MAP_HINT_BYTES)
    if bytes(rom[WORLD_MAP_HINT_OFFSET:hint_end]) != WORLD_MAP_HINT_BYTES:
        rom[WORLD_MAP_HINT_OFFSET:hint_end] = WORLD_MAP_HINT_BYTES
        patched += 1

    if struct.unpack_from("<I", rom, WORLD_MAP_HINT_POINTER)[0] != (
        WORLD_MAP_HINT_CPU_ADDR
    ):
        struct.pack_into(
            "<I", rom, WORLD_MAP_HINT_POINTER, WORLD_MAP_HINT_CPU_ADDR
        )
        patched += 1

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
        raise SystemExit(f"ROM introuvable : {args.rom}")

    original = args.rom.read_bytes()
    if len(original) <= 0xB2 or original[0xB2] != 0x96:
        raise SystemExit(f"ROM GBA invalide : {args.rom}")

    rom = bytearray(original)
    patched = apply(rom)
    if patched:
        Path(f"{args.rom}.bak").write_bytes(original)
        args.rom.write_bytes(rom)

    print(
        "patch_world_map_action_labels_fr: "
        f"{patched} élément(s) restauré(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
