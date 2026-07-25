#!/usr/bin/env python3
"""Re-introduce the GitHub issue #84 defect in a throwaway copy of a ROM.

Two sheets carry an HP bar whose end caps a label redraw can eat:

* the summary-screen sheet (LZ77 block 0x00E9B4B8) used to come straight from
  the Spanish ROM — a 7-row bar body and an empty tile 11, i.e. a bar with no
  end caps at all. That is the defect users reported;
* the party-menu sheet (LZ77 block 0x008001D0) keeps the bar's left cap in
  columns 14-15 of the label area. No shipped build ever ate it, so the damage
  applied here is synthetic: the columns are simply blanked.

``languages/<code>/patches/hp_labels.py`` now protects both. This script undoes
that protection so the end-to-end tests can prove they really detect the
regression instead of passing by construction.

It refuses to touch anything but a copy: pass a ROM you are happy to destroy.

Usage::

    python3 scripts/regress_summary_hp_bar.py --rom /tmp/sandbox/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import lz77_compress, lz77_decompress  # noqa: E402
from languages.fr.patches.hp_labels import (  # noqa: E402
    GREEN_BLOCK,
    GREEN_ES_TILES,
    GREEN_SLOT_LEN,
    PARTY_BLOCK,
    TILE,
)

# Right-hand tiles of the party label area; their last byte per row is grid
# columns 14-15, i.e. the HP bar's left cap.
PARTY_CAP_TILES = (52, 60)

# Blanking the cap costs a few bytes of LZ77 entropy, so the damaged stream can
# be slightly longer than the one currently in the ROM (638-642 bytes depending
# on the build). The sheet's slot is what it takes in the base ROM every build
# starts from, 658 bytes, and this script only ever runs on a throwaway copy.
PARTY_SLOT_LEN = 658


def _regress_summary_sheet(rom: bytearray) -> None:
    result = lz77_decompress(rom, GREEN_BLOCK)
    if result is None:
        raise SystemExit(f"Cannot decompress block 0x{GREEN_BLOCK:08X}")

    tiles = bytearray(result[0])
    for tile, hexdata in GREEN_ES_TILES.items():
        tiles[tile * TILE:(tile + 1) * TILE] = bytes.fromhex(hexdata)

    compressed = lz77_compress(bytes(tiles))
    if len(compressed) > GREEN_SLOT_LEN:
        raise SystemExit(
            f"Spanish sheet needs {len(compressed)} bytes, slot is {GREEN_SLOT_LEN}"
        )

    rom[GREEN_BLOCK:GREEN_BLOCK + len(compressed)] = compressed
    print(f"  0x{GREEN_BLOCK:08X}: sheet reverted to the capless Spanish art")


def _regress_party_cap(rom: bytearray) -> None:
    result = lz77_decompress(rom, PARTY_BLOCK)
    if result is None:
        raise SystemExit(f"Cannot decompress block 0x{PARTY_BLOCK:08X}")

    tiles = bytearray(result[0])
    for tile in PARTY_CAP_TILES:
        for row in range(8):
            tiles[tile * TILE + row * 4 + 3] = 0x66  # background on both columns

    compressed = lz77_compress(bytes(tiles))
    if len(compressed) > PARTY_SLOT_LEN:
        raise SystemExit(
            f"Damaged party sheet needs {len(compressed)} bytes, "
            f"slot is {PARTY_SLOT_LEN}"
        )

    rom[PARTY_BLOCK:PARTY_BLOCK + len(compressed)] = compressed
    print(f"  0x{PARTY_BLOCK:08X}: HP-bar left cap blanked in the label tiles")


def regress(rom_path: Path) -> None:
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")

    print(f"regress_summary_hp_bar: damaging {rom_path}")
    _regress_summary_sheet(rom)
    _regress_party_cap(rom)
    rom_path.write_bytes(rom)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True,
                        help="throwaway ROM copy to damage")
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    regress(args.rom)


if __name__ == "__main__":
    main()
