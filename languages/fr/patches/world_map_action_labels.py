#!/usr/bin/env python3
"""Stabilise les libellés d'action partagés (#111 / #131 / #178).

Le bandeau de déplacement est chargé par le littéral ``0x9FB64``. La source
FR courte existe à ``0x418E77``, mais le build générique peut conserver une
ancienne cellule sans le point final ou laisser le littéral pointer vers une
relocalisation périmée. Le correctif source seul ne survit donc pas à tous les
rebuilds.

Les actions d'annulation ont le même problème : l'injection relocalise leurs
trois pointeurs vers la chaîne générique « Annuler » et laisse les deux cellules
anglaises d'origine intactes. La forme « Annul. » occupe exactement la largeur
de « Cancel » ; elle peut donc être restaurée en place sans allocation.

Ce patch post-build réécrit les trois cellules canoniques, puis restaure leurs
quatre pointeurs. Il est déterministe, idempotent et ne touche ni le
« Annuler » partagé du menu Équipe ni sa relocalisation.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


ROM_BASE = 0x08000000
WORLD_MAP_HINT_POINTER = 0x9FB64
WORLD_MAP_HINT_OFFSET = 0x418E77
WORLD_MAP_HINT_CPU_ADDR = ROM_BASE + WORLD_MAP_HINT_OFFSET

# {DPAD_ANY}Dépl. {SE_SHOP}OK {B_BUTTON}Annul. + terminateur CFRU.
WORLD_MAP_HINT_BYTES = bytes.fromhex(
    "f80cbe1be4e0ad00f800c9c500f801bbe2e2e9e0adff"
)

# {SE_SHOP}Annul. + terminateur CFRU, même largeur que {SE_SHOP}Cancel.
WORLD_MAP_CANCEL_BYTES = bytes.fromhex("f800bbe2e2e9e0adff")
WORLD_MAP_CANCEL_OFFSETS = (0x418E95, 0x418E9E)
WORLD_MAP_CANCEL_POINTER_TARGETS = (
    (0xC06FC, 0x418E95),
    (0xC1B28, 0x418E9E),
    (0xC50C0, 0x418E95),
)


def apply(rom: bytearray) -> int:
    """Restaure les cellules courtes et leurs pointeurs vivants.

    Returns:
        Nombre d'éléments modifiés (cellule et/ou pointeur).
    """
    minimum_size = max(
        WORLD_MAP_HINT_POINTER + 4,
        WORLD_MAP_HINT_OFFSET + len(WORLD_MAP_HINT_BYTES),
        *(
            offset + len(WORLD_MAP_CANCEL_BYTES)
            for offset in WORLD_MAP_CANCEL_OFFSETS
        ),
        *(
            pointer + 4
            for pointer, _target in WORLD_MAP_CANCEL_POINTER_TARGETS
        ),
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

    for offset in WORLD_MAP_CANCEL_OFFSETS:
        end = offset + len(WORLD_MAP_CANCEL_BYTES)
        if bytes(rom[offset:end]) != WORLD_MAP_CANCEL_BYTES:
            rom[offset:end] = WORLD_MAP_CANCEL_BYTES
            patched += 1

    for pointer, target in WORLD_MAP_CANCEL_POINTER_TARGETS:
        target_cpu_addr = ROM_BASE + target
        if struct.unpack_from("<I", rom, pointer)[0] != target_cpu_addr:
            struct.pack_into("<I", rom, pointer, target_cpu_addr)
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
