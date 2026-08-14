#!/usr/bin/env python3
"""Localise les six statistiques pointées du Pokédex en allemand."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import TextEncoder

GBA_BASE = ROM_BASE = 0x08000000
PTR_TABLE_OFFSETS = (0x8C972C, 0x964A3C)
PTR_STRIDE = 4
STAT_ORDER = ("hp", "atk", "def", "spe", "spa", "spd")
ENGLISH_LABELS = {
    "hp": "HP", "atk": "Atk", "def": "Def",
    "spe": "Spe", "spa": "SpA", "spd": "SpD",
}
DE_LABELS = GERMAN_LABELS = {
    "hp": "KP", "atk": "Ang", "def": "Ver",
    "spe": "Init", "spa": "SpA", "spd": "SpV",
}
_TAIL = bytes((0xFD, 0x02, 0xFF))


def _entry(label: str) -> bytes:
    encoded = TextEncoder.encode(label, "pokemon")[:-1]
    if len(encoded) > 4:
        raise ValueError(f"abréviation trop longue: {label!r}")
    return encoded + b"\x00" * (4 - len(encoded)) + _TAIL


EN_ENTRIES = {key: _entry(value) for key, value in ENGLISH_LABELS.items()}
DE_ENTRIES = {key: _entry(value) for key, value in DE_LABELS.items()}


def apply_to_rom(rom: bytearray, dry_run: bool = False) -> int:
    """Patch atomiquement chaque table présente, avec préimages strictes."""
    candidate = bytearray(rom)
    changed = 0
    for table in PTR_TABLE_OFFSETS:
        table_end = table + len(STAT_ORDER) * PTR_STRIDE
        if table_end > len(candidate):
            continue
        for index, key in enumerate(STAT_ORDER):
            pointer = struct.unpack_from(
                "<I", candidate, table + index * PTR_STRIDE
            )[0]
            target = pointer - ROM_BASE
            if not (0 <= target <= len(candidate) - 7):
                raise ValueError(f"pointeur statistique hors ROM: 0x{pointer:08X}")
            current = bytes(candidate[target : target + 7])
            if current == DE_ENTRIES[key]:
                continue
            if current != EN_ENTRIES[key]:
                raise ValueError(
                    f"octets inattendus pour {key} à 0x{target:X}: {current.hex()}"
                )
            candidate[target : target + 7] = DE_ENTRIES[key]
            changed += 1
    if changed and not dry_run:
        rom[:] = candidate
    return changed


def apply(rom: bytearray) -> int:
    """API stricte utilisée par les gardes F-602."""
    return apply_to_rom(rom)


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    """Traduit les libellés dans ``rom_path`` et retourne le total modifié."""
    original = rom_path.read_bytes()
    rom = bytearray(original)
    changed = apply_to_rom(rom, dry_run=dry_run)
    if changed and not dry_run:
        Path(f"{rom_path}.bak").write_bytes(original)
        rom_path.write_bytes(rom)
    return changed


def main(argv: list[str] | None = None) -> int:
    """Applique le patch à une ROM DE construite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    changed = apply_patches(args.rom, dry_run=args.dry_run)
    suffix = " (simulation)" if args.dry_run else ""
    print(f"patch_pokedex_stat_labels_de: {changed} entrée(s) traduite(s){suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
