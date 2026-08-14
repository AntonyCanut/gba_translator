#!/usr/bin/env python3
"""Restaure les noms propres originaux des labels fixes de carte DE."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGETS = (0xB500A0, 0xB535C8)


def _terminated_entry(rom: bytes, offset: int) -> bytes:
    end = rom.find(b"\xff", offset)
    if end < 0:
        raise ValueError(f"chaîne sans terminateur à 0x{offset:08X}")
    return rom[offset : end + 1]


def apply(rom: bytearray, source_rom: bytes) -> int:
    """Copie les deux noms de lieux depuis la ROM anglaise immuable."""
    if len(rom) != len(source_rom):
        raise ValueError("les ROM source et cible doivent avoir la même taille")
    patched = 0
    for offset in TARGETS:
        encoded = _terminated_entry(source_rom, offset)
        end = offset + len(encoded)
        if bytes(rom[offset:end]) != encoded:
            rom[offset:end] = encoded
            patched += 1
    return patched


def main(argv: list[str] | None = None) -> int:
    """Applique le patch à la ROM DE construite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "input/roms/englishrom.gba",
    )
    args = parser.parse_args(argv)
    original = args.rom.read_bytes()
    rom = bytearray(original)
    patched = apply(rom, args.source.read_bytes())
    if patched:
        Path(f"{args.rom}.bak").write_bytes(original)
        args.rom.write_bytes(rom)
    print(f"patch_worldmap_labels_de: {patched} label(s) restauré(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
