#!/usr/bin/env python3
"""Insert a 4bpp indexed .bmp file into a ROM at a named UI sprite's
location(s) (F-108).

By default the same .bmp is written to *every* duplicate block the sprite
registers (see ``languages/<lang>/sprites.py``); pass ``--block-index`` to
target just one. A block that fails to decompress, is too small, or whose
recompressed size would overflow into live (non-padding) ROM data is skipped
with a warning — matching the tolerance rule used by the hand-written
``status_badges.py``/``hp_labels.py`` patches — so one bad block never blocks
the others. Exits non-zero if every requested block was skipped.

Usage::

    python3 scripts/insert_sprite.py --rom output/roms/GenedRom-fr.gba \\
        --lang fr --sprite status_badges --bmp languages/fr/sprites/status_badges.bmp
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.graphics.sprite_bmp import read_indexed_bmp  # noqa: E402
from src.graphics.sprite_rom import insert_block  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--lang", required=True, help="e.g. fr, it, de")
    parser.add_argument("--sprite", required=True, help="sprite name in the language's registry")
    parser.add_argument("--bmp", required=True, type=Path)
    parser.add_argument("--block-index", type=int, default=None,
                         help="patch only this duplicate block (default: patch all of them)")
    args = parser.parse_args()

    registry = importlib.import_module(f"languages.{args.lang}.sprites").SPRITES
    if args.sprite not in registry:
        raise SystemExit(
            f"Unknown sprite {args.sprite!r} for lang {args.lang!r}. "
            f"Known: {', '.join(sorted(registry)) or '(none)'}"
        )
    sprite = registry[args.sprite]
    width = sprite.tiles_wide * 8
    height = sprite.tiles_tall * 8

    bmp_w, bmp_h, grid = read_indexed_bmp(args.bmp)
    if (bmp_w, bmp_h) != (width, height):
        raise SystemExit(f"{args.bmp}: expected {width}x{height}, got {bmp_w}x{bmp_h}")

    if args.block_index is not None:
        if not 0 <= args.block_index < len(sprite.blocks):
            raise SystemExit(f"--block-index must be in [0, {len(sprite.blocks) - 1}]")
        indices = [args.block_index]
    else:
        indices = list(range(len(sprite.blocks)))

    rom = bytearray(args.rom.read_bytes())
    patched = 0
    for i in indices:
        offset = sprite.blocks[i]
        try:
            insert_block(rom, offset, grid, sprite.tiles_wide, sprite.tiles_tall)
        except ValueError as exc:
            print(f"  WARN {args.sprite}[{i}] @ 0x{offset:08X}: {exc} — skip", file=sys.stderr)
            continue
        print(f"{args.sprite}[{i}] @ 0x{offset:08X}: patched from {args.bmp}")
        patched += 1

    if patched:
        args.rom.write_bytes(rom)
    print(f"insert_sprite: {patched}/{len(indices)} block(s) patched")
    return 0 if patched else 1


if __name__ == "__main__":
    raise SystemExit(main())
