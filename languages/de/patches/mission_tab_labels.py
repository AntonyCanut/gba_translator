#!/usr/bin/env python3
"""Supprime le suffixe runtime « Missionen » des onglets Missions DE."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import TextDecoder

ROM_BASE = 0x08000000
SUFFIX_PTR_OFFSET = 0x1EBE988
ALLOWED_SUFFIXES = {" Missions", "Missionen", " Missionen"}


def _read_text(rom: bytes, offset: int) -> tuple[str, int]:
    end = rom.find(b"\xff", offset, offset + 32)
    if end < 0:
        raise ValueError("Suffix Missions sans terminateur")
    raw = rom[offset : end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True), end


def apply(rom: bytearray) -> int:
    """Vide le suffixe suivi par le pointeur vivant, avec garde de contenu."""
    pointer = struct.unpack_from("<I", rom, SUFFIX_PTR_OFFSET)[0]
    target = pointer - ROM_BASE
    if not (0 <= target < len(rom)):
        raise ValueError(f"pointeur de suffixe hors ROM: 0x{pointer:08X}")
    if rom[target] == 0xFF:
        return 0
    text, end = _read_text(rom, target)
    if text not in ALLOWED_SUFFIXES:
        raise ValueError(f"Suffix Missions inattendu: {text!r}")
    rom[target : end + 1] = b"\xff" * (end + 1 - target)
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
    print(f"patch_mission_tab_labels_de: {changed} suffixe(s) supprimé(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
