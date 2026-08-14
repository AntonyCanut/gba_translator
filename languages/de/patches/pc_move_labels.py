#!/usr/bin/env python3
"""Corrige l'action courrier PC non pointée « Move To Bag » en allemand."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import TextEncoder

MAIL_OFFSET = 0x4177DD
ENGLISH_CELL = TextEncoder.encode("Move To Bag", "pokemon")
CELL_SIZE = len(ENGLISH_CELL)
_GERMAN = TextEncoder.encode("Zum Beutel", "pokemon")
GERMAN_CELL = _GERMAN + b"\xff" * (CELL_SIZE - len(_GERMAN))


def apply(rom: bytearray) -> int:
    """Réécrit la cellule fixe après contrôle de sa préimage complète."""
    current = bytes(rom[MAIL_OFFSET : MAIL_OFFSET + CELL_SIZE])
    if current == GERMAN_CELL:
        return 0
    if current != ENGLISH_CELL:
        raise ValueError(f"octets inattendus pour Move To Bag: {current.hex()}")
    rom[MAIL_OFFSET : MAIL_OFFSET + CELL_SIZE] = GERMAN_CELL
    return 1


def main(argv: list[str] | None = None) -> int:
    """Applique le patch à une ROM DE construite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    original = args.rom.read_bytes()
    rom = bytearray(original)
    changed = apply(rom)
    if changed:
        Path(f"{args.rom}.bak").write_bytes(original)
        args.rom.write_bytes(rom)
    print(f"patch_pc_move_labels_de: {changed} cellule(s) traduite(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
