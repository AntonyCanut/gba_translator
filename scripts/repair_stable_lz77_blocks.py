#!/usr/bin/env python3
"""
Restore LZ77 blocks that should be identical across EN/ES but were corrupted.

Some UI graphics (keyboard, menus) are stored as compressed blocks that should
match between English and Spanish ROMs. If those blocks differ in the French
ROM, we restore them from the English reference to remove visual glitches.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Tuple

import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import is_font_block, lz77_decompress  # noqa: E402


def _iter_lz77_blocks(data: bytes, min_dec: int, max_dec: int) -> Iterable[Tuple[int, int, bytes]]:
    start = 0
    while True:
        idx = data.find(b"\x10", start)
        if idx == -1:
            break
        start = idx + 1
        result = lz77_decompress(data, idx)
        if result is None:
            continue
        decompressed, comp_len = result
        dec_len = len(decompressed)
        if dec_len < min_dec or dec_len > max_dec:
            continue
        if idx + comp_len > len(data):
            continue
        yield idx, comp_len, decompressed


def repair_stable_blocks(
    target: bytearray, english: bytes, spanish: bytes, min_dec: int, max_dec: int
) -> Tuple[int, int]:
    """Restore stable (EN==ES) LZ77 blocks in ``target`` from ``english``.

    Returns ``(stable_blocks, repaired_blocks)``. Font blocks are skipped:
    the font isn't localized (EN/ES share the same bytes), so they always
    look "stable" here — but font.py intentionally rewrites their é/è/à/ç
    glyphs. Restoring them from English would silently undo that accent fix.
    repair_localized_lz77_blocks.py applies the same exclusion for the same
    reason.
    """
    stable_blocks = 0
    repaired_blocks = 0

    for offset, comp_len, en_dec in _iter_lz77_blocks(english, min_dec, max_dec):
        if is_font_block(en_dec):
            continue
        if offset + comp_len > len(spanish) or offset + comp_len > len(target):
            continue
        ref_en = english[offset : offset + comp_len]
        ref_es = spanish[offset : offset + comp_len]
        if ref_en != ref_es:
            continue
        stable_blocks += 1
        if target[offset : offset + comp_len] != ref_en:
            target[offset : offset + comp_len] = ref_en
            repaired_blocks += 1

    return stable_blocks, repaired_blocks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore stable (EN=ES) LZ77 blocks in a target ROM."
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
    parser.add_argument("--min-dec", type=int, default=0x100, help="Min decompressed size")
    parser.add_argument("--max-dec", type=int, default=0x20000, help="Max decompressed size")

    args = parser.parse_args()

    for path in (args.target, args.english, args.spanish):
        if not path.exists():
            raise SystemExit(f"Missing ROM: {path}")

    english = args.english.read_bytes()
    spanish = args.spanish.read_bytes()
    target = bytearray(args.target.read_bytes())

    stable_blocks, repaired_blocks = repair_stable_blocks(
        target, english, spanish, args.min_dec, args.max_dec
    )

    args.target.write_bytes(target)

    print(f"Stable blocks checked: {stable_blocks}")
    print(f"Repaired blocks: {repaired_blocks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
