#!/usr/bin/env python3
"""Stabilise les libellés d'action allemands de la carte du monde."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.core.text_codec import GERMAN_UMLAUT_CHARS, TextEncoder

ROM_BASE = 0x08000000
WORLD_MAP_HINT_POINTER = 0x9FB64
WORLD_MAP_HINT_OFFSET = 0x418E77
WORLD_MAP_HINT_TEXT = "{DPAD_ANY}Bew. {SE_SHOP}OK {B_BUTTON}Zurück"
WORLD_MAP_HINT_BYTES = (
    bytes.fromhex("f80c")
    + TextEncoder.encode("Bew. ", "pokemon")[:-1]
    + bytes.fromhex("f800")
    + TextEncoder.encode("OK ", "pokemon")[:-1]
    + bytes.fromhex("f801")
    + TextEncoder.encode(
        "Zurück", "pokemon", skip_aliases=GERMAN_UMLAUT_CHARS
    )
)

WORLD_MAP_CANCEL_TEXT = "{SE_SHOP}Zurück"
WORLD_MAP_CANCEL_BYTES = bytes.fromhex("f800") + TextEncoder.encode(
    "Zurück", "pokemon", skip_aliases=GERMAN_UMLAUT_CHARS
)
WORLD_MAP_CANCEL_OFFSETS = (0x418E95, 0x418E9E)
WORLD_MAP_CANCEL_POINTER_TARGETS = (
    (0xC06FC, 0x418E95),
    (0xC1B28, 0x418E9E),
    (0xC50C0, 0x418E95),
)


def apply(rom: bytearray) -> int:
    """Réécrit les cellules allemandes et leurs quatre pointeurs connus."""
    minimum_size = max(
        WORLD_MAP_HINT_OFFSET + len(WORLD_MAP_HINT_BYTES),
        *(offset + len(WORLD_MAP_CANCEL_BYTES) for offset in WORLD_MAP_CANCEL_OFFSETS),
        *(pointer + 4 for pointer, _ in WORLD_MAP_CANCEL_POINTER_TARGETS),
    )
    if len(rom) < minimum_size:
        raise ValueError(f"ROM trop courte ({len(rom)} octets, minimum {minimum_size})")

    patched = 0
    cells = (
        (WORLD_MAP_HINT_OFFSET, WORLD_MAP_HINT_BYTES),
        *((offset, WORLD_MAP_CANCEL_BYTES) for offset in WORLD_MAP_CANCEL_OFFSETS),
    )
    for offset, encoded in cells:
        end = offset + len(encoded)
        if bytes(rom[offset:end]) != encoded:
            rom[offset:end] = encoded
            patched += 1

    pointers = (
        (WORLD_MAP_HINT_POINTER, WORLD_MAP_HINT_OFFSET),
        *WORLD_MAP_CANCEL_POINTER_TARGETS,
    )
    for pointer, target in pointers:
        value = ROM_BASE + target
        if struct.unpack_from("<I", rom, pointer)[0] != value:
            struct.pack_into("<I", rom, pointer, value)
            patched += 1
    return patched


def main(argv: list[str] | None = None) -> int:
    """Applique le patch à la ROM DE construite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    original = args.rom.read_bytes()
    rom = bytearray(original)
    patched = apply(rom)
    if patched:
        Path(f"{args.rom}.bak").write_bytes(original)
        args.rom.write_bytes(rom)
    print(f"patch_world_map_action_labels_de: {patched} élément(s) restauré(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
