#!/usr/bin/env python3
"""Extract a named UI sprite from a ROM to a 4bpp indexed .bmp file (F-108).

The sprite's ROM location and tile layout come from that language's registry
(``languages/<lang>/sprites.py``). The resulting .bmp can be opened in any
editor that supports 16-color indexed BMPs and re-inserted with
``insert_sprite.py``.

Usage::

    python3 scripts/extract_sprite.py --rom output/roms/GenedRom-fr.gba \\
        --lang fr --sprite status_badges -o status_badges.bmp

    # A sprite may have several duplicate blocks; pick one explicitly:
    python3 scripts/extract_sprite.py --rom ROM --lang fr \\
        --sprite status_badges --block-index 2 -o secondary.bmp
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.graphics.sprite_bmp import write_indexed_bmp  # noqa: E402
from src.graphics.sprite_rom import extract_block  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--lang", required=True, help="e.g. fr, it, de")
    parser.add_argument("--sprite", required=True, help="sprite name in the language's registry")
    parser.add_argument("--block-index", type=int, default=0,
                         help="which duplicate block to read (default: 0, the first)")
    parser.add_argument("-o", "--out", required=True, type=Path)
    args = parser.parse_args()

    registry = importlib.import_module(f"languages.{args.lang}.sprites").SPRITES
    if args.sprite not in registry:
        raise SystemExit(
            f"Unknown sprite {args.sprite!r} for lang {args.lang!r}. "
            f"Known: {', '.join(sorted(registry)) or '(none)'}"
        )
    sprite = registry[args.sprite]
    if not 0 <= args.block_index < len(sprite.blocks):
        raise SystemExit(f"--block-index must be in [0, {len(sprite.blocks) - 1}]")
    offset = sprite.blocks[args.block_index]

    rom = args.rom.read_bytes()
    grid, dec_len, comp_len = extract_block(rom, offset, sprite.tiles_wide, sprite.tiles_tall)
    width = sprite.tiles_wide * 8
    height = sprite.tiles_tall * 8
    write_indexed_bmp(args.out, width, height, grid)
    print(
        f"{args.sprite}[{args.block_index}] @ 0x{offset:08X}: "
        f"{width}x{height} -> {args.out} "
        f"(decompressed {dec_len}B, compressed {comp_len}B)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
