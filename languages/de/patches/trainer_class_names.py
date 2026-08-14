#!/usr/bin/env python3
"""Injecte strictement les classes de Dresseurs allemandes en cellules fixes."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import GERMAN_UMLAUT_CHARS, TextEncoder

ROOT = Path(__file__).resolve().parents[3]
TABLE_BASE = 0x23E558
CELL_STRIDE = 13
FIRST_CLASS_INDEX = 1
CLASS_COUNT = 107
_LINE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
SHORT_NAMES = {
    13: "Schnösel",
    20: "Käfermaniac",
    23: "Lady",
    33: "Drachenprofi",
    37: "Schirmdame",
    48: "Schattenboss",
    49: "Ex-Schatten",
    82: "Forscher",
    96: "Geschwister",
}


def _load_combined(path: Path) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LINE.match(line)
        if match:
            mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def _target_cells() -> dict[int, bytes]:
    combined = _load_combined(ROOT / "languages/de/combined_de.txt")
    cells: dict[int, bytes] = {}
    for index in range(FIRST_CLASS_INDEX, CLASS_COUNT):
        offset = TABLE_BASE + index * CELL_STRIDE
        text = SHORT_NAMES.get(index, combined.get(offset))
        if text is None:
            continue
        encoded = TextEncoder.encode(
            text, "pokemon", skip_aliases=GERMAN_UMLAUT_CHARS
        )
        if len(encoded) > CELL_STRIDE:
            raise ValueError(f"classe DE trop longue à l'index {index}: {text!r}")
        cells[index] = encoded + b"\x00" * (CELL_STRIDE - len(encoded))
    return cells


TARGET_CELLS = _target_cells()
FIRST_TRANSLATED_INDEX = min(TARGET_CELLS)


def apply(rom: bytearray, source_rom: bytes) -> dict[str, int]:
    """Écrit les 95 cellules connues et refuse toute préimage corrompue."""
    if len(rom) != len(source_rom):
        raise ValueError("les ROM source et cible doivent avoir la même taille")
    stats = {"written": 0, "unchanged": 0, "preserved": 0}
    for index in range(FIRST_CLASS_INDEX, CLASS_COUNT):
        offset = TABLE_BASE + index * CELL_STRIDE
        target = TARGET_CELLS.get(index)
        if target is None:
            stats["preserved"] += 1
            continue
        source_cell = source_rom[offset : offset + CELL_STRIDE]
        current = bytes(rom[offset : offset + CELL_STRIDE])
        if current == target:
            stats["unchanged"] += 1
            continue
        if current != source_cell:
            raise ValueError(
                f"classe Dresseur {index} inattendue à 0x{offset:X}: {current.hex()}"
            )
        rom[offset : offset + CELL_STRIDE] = target
        stats["written"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    """Applique le patch à une ROM DE construite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=ROOT / "input/roms/englishrom.gba")
    args = parser.parse_args(argv)
    original = args.rom.read_bytes()
    rom = bytearray(original)
    stats = apply(rom, args.source.read_bytes())
    if stats["written"]:
        Path(f"{args.rom}.bak").write_bytes(original)
        args.rom.write_bytes(rom)
    print(f"patch_trainer_class_names_de: {stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
