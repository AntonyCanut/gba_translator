#!/usr/bin/env python3
"""
Restore localized (EN!=ES) LZ77 blocks from the Spanish ROM into a target ROM.

These blocks are small UI graphics that differ between English and Spanish.
We copy Spanish variants when they live at the same offsets to keep visuals
consistent with the Spanish reference (e.g. keyboard blanks, UI tiles).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import is_font_block, lz77_decompress  # noqa: E402


def _collect_pointer_offsets(rom: bytes) -> set[int]:
    offsets = set()
    rom_len = len(rom)
    for i in range(0, rom_len - 3, 4):
        val = int.from_bytes(rom[i:i + 4], "little")
        if 0x08000000 <= val < 0x0A000000:
            off = val - 0x08000000
            if 0 <= off < rom_len:
                offsets.add(off)
    return offsets


def _iter_lz77_offsets(rom: bytes) -> Iterable[Tuple[int, int]]:
    start = 0
    while True:
        idx = rom.find(b"\x10", start)
        if idx == -1:
            break
        start = idx + 1
        result = lz77_decompress(rom, idx)
        if result is None:
            continue
        _decompressed, comp_len = result
        if idx + comp_len > len(rom):
            continue
        yield idx, comp_len


def _is_padding(data: bytes) -> bool:
    if not data:
        return True
    return all(b in (0x00, 0xFF) for b in data)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy localized (EN!=ES) LZ77 blocks from Spanish ROM to target."
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="Target ROM to patch (e.g. output/roms/GenedRom-fr.gba)",
    )
    parser.add_argument(
        "--english",
        type=Path,
        default=Path("input/roms/englishrom.gba"),
        help="English reference ROM",
    )
    parser.add_argument(
        "--spanish",
        type=Path,
        default=Path("input/roms/spanishrom.gba"),
        help="Spanish reference ROM",
    )
    parser.add_argument(
        "--require-pointer",
        action="store_true",
        help="Only patch blocks that have direct pointers in EN or ES ROMs",
    )

    args = parser.parse_args()

    for path in (args.target, args.english, args.spanish):
        if not path.exists():
            raise SystemExit(f"Missing ROM: {path}")

    english = args.english.read_bytes()
    spanish = args.spanish.read_bytes()
    target = bytearray(args.target.read_bytes())

    pointer_offsets = set()
    if args.require_pointer:
        pointer_offsets = _collect_pointer_offsets(english) | _collect_pointer_offsets(spanish)

    patched = 0
    skipped_overlap = 0

    for offset, _en_comp_len in _iter_lz77_offsets(english):
        en_result = lz77_decompress(english, offset)
        es_result = lz77_decompress(spanish, offset)
        if en_result is None or es_result is None:
            continue
        en_dec, en_comp_len = en_result
        es_dec, es_comp_len = es_result
        if len(en_dec) != len(es_dec):
            continue
        if en_dec == es_dec:
            continue
        if is_font_block(en_dec):
            continue
        if args.require_pointer and offset not in pointer_offsets:
            continue

        if offset + es_comp_len > len(target):
            skipped_overlap += 1
            continue
        if es_comp_len > en_comp_len:
            extra = target[offset + en_comp_len:offset + es_comp_len]
            if not _is_padding(extra):
                skipped_overlap += 1
                continue

        target[offset:offset + es_comp_len] = spanish[offset:offset + es_comp_len]
        patched += 1

    args.target.write_bytes(target)

    print(f"Localized blocks patched: {patched}")
    if skipped_overlap:
        print(f"Skipped (overlap risk): {skipped_overlap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
