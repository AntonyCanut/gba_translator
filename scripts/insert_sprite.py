#!/usr/bin/env python3
"""Insert a 4bpp indexed .png/.bmp into a named UI sprite's ROM location(s).

Single-block sprites need no selector. For a sprite with palette-specific
copies, pass ``--block-index`` for one image or ``--all-blocks`` to consume
the files ``<image-stem>-0.<ext>``, ``<image-stem>-1.<ext>``, etc. This keeps
one block's palette indices from corrupting another block. A block that fails
to decompress, is too small, or whose recompressed size would overflow into
live (non-padding) ROM data is skipped
with a warning — matching the tolerance rule used by the hand-written
``status_badges.py``/``hp_labels.py`` patches — so one bad block never blocks
the others. Exits non-zero if every requested block was skipped.

Usage::

    python3 scripts/insert_sprite.py --rom output/roms/GenedRom-fr.gba \\
        --lang fr --sprite status_badges --block-index 0 \\
        --image languages/fr/sprites/status_badges.png
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.graphics.sprite_image import read_indexed_image, variant_path  # noqa: E402
from src.graphics.sprite_rom import insert_block  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--lang", required=True, help="e.g. fr, it, de")
    parser.add_argument("--sprite", required=True, help="sprite name in the language's registry")
    parser.add_argument(
        "--image",
        "--bmp",
        dest="image",
        required=True,
        type=Path,
        help="indexed .png or .bmp (the --bmp alias is kept for compatibility)",
    )
    blocks = parser.add_mutually_exclusive_group()
    blocks.add_argument("--block-index", type=int, default=None,
                        help="patch only this duplicate block")
    blocks.add_argument(
        "--all-blocks",
        action="store_true",
        help="patch every block from <image-stem>-<index>.<ext>",
    )
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

    if args.block_index is not None:
        if not 0 <= args.block_index < len(sprite.blocks):
            raise SystemExit(f"--block-index must be in [0, {len(sprite.blocks) - 1}]")
        indices = [args.block_index]
    elif args.all_blocks:
        indices = list(range(len(sprite.blocks)))
    elif len(sprite.blocks) == 1:
        indices = [0]
    else:
        raise SystemExit(
            f"{args.sprite!r} has {len(sprite.blocks)} palette-specific blocks; "
            "use --block-index or --all-blocks"
        )

    rom = bytearray(args.rom.read_bytes())
    patched = 0
    for i in indices:
        offset = sprite.blocks[i]
        image = variant_path(args.image, i) if args.all_blocks else args.image
        try:
            image_w, image_h, grid = read_indexed_image(image)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if (image_w, image_h) != (width, height):
            raise SystemExit(
                f"{image}: expected {width}x{height}, got {image_w}x{image_h}"
            )
        try:
            insert_block(rom, offset, grid, sprite.tiles_wide, sprite.tiles_tall,
                         compressed=sprite.compressed, vram_safe=sprite.vram_safe)
        except ValueError as exc:
            print(f"  WARN {args.sprite}[{i}] @ 0x{offset:08X}: {exc} — skip", file=sys.stderr)
            continue
        print(f"{args.sprite}[{i}] @ 0x{offset:08X}: patched from {image}")
        patched += 1

    if patched:
        args.rom.write_bytes(rom)
    print(f"insert_sprite: {patched}/{len(indices)} block(s) patched")
    return 0 if patched else 1


if __name__ == "__main__":
    raise SystemExit(main())
