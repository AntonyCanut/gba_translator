#!/usr/bin/env python3
"""Traduit les six libellés statistiques pointés du Pokédex en allemand.

Chaque entrée conserve la cellule CFRU de sept octets du moteur : quatre
octets de libellé ou de remplissage, ``{STR_VAR_2}``, puis ``0xFF``. Les deux
tables de pointeurs sont traitées afin que les variantes de l'écran affichent
les mêmes abréviations : KP, Ang, Ver, Init, SpA et SpV.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from languages.fr.patches import pokedex_stat_labels as base  # noqa: E402

GBA_BASE = base.GBA_BASE
PTR_TABLE_OFFSETS = base.PTR_TABLE_OFFSETS
PTR_STRIDE = base.PTR_STRIDE
STAT_ORDER = base.STAT_ORDER
EN_ENTRIES = base._EN_ENTRIES

DE_LABELS = {
    "hp": "KP",
    "atk": "Ang",
    "def": "Ver",
    "spe": "Init",
    "spa": "SpA",
    "spd": "SpV",
}
DE_ENTRIES = {key: base._entry_bytes(label) for key, label in DE_LABELS.items()}


def apply_to_rom(rom: bytearray, dry_run: bool = False) -> int:
    """Applique les libellés DE aux cellules atteintes par les pointeurs.

    Args:
        rom: ROM modifiable en mémoire.
        dry_run: Compte les changements sans écrire les octets.

    Returns:
        Nombre de cellules qui nécessitent la traduction.
    """
    changes = 0
    for table_offset in PTR_TABLE_OFFSETS:
        for index, key in enumerate(STAT_ORDER):
            pointer_offset = table_offset + index * PTR_STRIDE
            if pointer_offset + 4 > len(rom):
                continue
            pointer = struct.unpack_from("<I", rom, pointer_offset)[0]
            text_offset = pointer - GBA_BASE
            target = DE_ENTRIES[key]
            if not (0 < text_offset <= len(rom) - len(target)):
                continue
            current = bytes(rom[text_offset:text_offset + len(target)])
            if current == target:
                continue
            if current != EN_ENTRIES[key]:
                print(
                    f"WARN 0x{text_offset:06X} ({key}) : cellule inattendue — saut",
                    file=sys.stderr,
                )
                continue
            if not dry_run:
                rom[text_offset:text_offset + len(target)] = target
            changes += 1
    return changes


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    """Traduit les libellés dans ``rom_path`` et retourne le total modifié."""
    rom = bytearray(rom_path.read_bytes())
    changes = apply_to_rom(rom, dry_run=dry_run)
    if changes and not dry_run:
        rom_path.write_bytes(rom)
    return changes


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée du patch post-build DE."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    changes = apply_patches(args.rom, dry_run=args.dry_run)
    suffix = " (simulation)" if args.dry_run else ""
    print(f"patch_pokedex_stat_labels_de: {changes} cellule(s) traduite(s){suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
