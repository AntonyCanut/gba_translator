#!/usr/bin/env python3
"""Localise le titre de mission fixe « The Food Thief » en allemand."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import TextEncoder

TITLE_OFFSET = 0x1FA4E10
ENGLISH_BYTES = TextEncoder.encode("The Food Thief", "pokemon")
GERMAN_BYTES = TextEncoder.encode("Der Essensdieb", "pokemon")

if len(ENGLISH_BYTES) != len(GERMAN_BYTES):
    raise AssertionError("le titre DE doit conserver exactement la cellule EN")


def apply(rom: bytearray) -> int:
    """Remplace le titre après validation byte-exacte de sa préimage."""
    current = bytes(rom[TITLE_OFFSET : TITLE_OFFSET + len(ENGLISH_BYTES)])
    if current == GERMAN_BYTES:
        return 0
    if current != ENGLISH_BYTES:
        raise ValueError(f"octets inattendus pour le titre de mission: {current.hex()}")
    rom[TITLE_OFFSET : TITLE_OFFSET + len(GERMAN_BYTES)] = GERMAN_BYTES
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
    print(f"patch_mission_titles_de: {changed} titre(s) traduit(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
