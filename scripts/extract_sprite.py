#!/usr/bin/env python3
"""Extract a named UI sprite from a ROM to an indexed .png/.bmp file.

The sprite's ROM location and tile layout come from that language's registry
(``languages/<lang>/sprites.py``). The resulting image can be opened in any
editor that preserves indexed palettes and re-inserted with ``insert_sprite.py``.
PNG is recommended; BMP remains supported for backward compatibility.

Usage::

    python3 scripts/extract_sprite.py --rom output/roms/GenedRom-fr.gba \\
        --lang fr --sprite status_badges -o status_badges.png

    # A sprite may have several duplicate blocks; pick one explicitly:
    python3 scripts/extract_sprite.py --rom ROM --lang fr \\
        --sprite status_badges --block-index 2 -o secondary.bmp

    # Or export every palette-specific copy as status_badges-0.png, ...:
    python3 scripts/extract_sprite.py --rom ROM --lang fr \\
        --sprite status_badges --all-blocks -o status_badges.png

    # Rebuild a mapped 256x160 Trainer Card screen:
    python3 scripts/extract_sprite.py --rom input/roms/englishrom.gba \\
        --lang fr --sprite trainer_card_front -o trainer_card_front.png
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.graphics.sprite_image import (  # noqa: E402
    DEFAULT_PALETTE,
    variant_path,
    write_indexed_image,
)
from src.graphics.sprite_rom import (  # noqa: E402
    extract_block,
    extract_mapped_block,
    read_gba_palette,
    resolve_live_offset,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--lang", required=True, help="e.g. fr, it, de")
    parser.add_argument("--sprite", required=True, help="sprite name in the language's registry")
    blocks = parser.add_mutually_exclusive_group()
    blocks.add_argument("--block-index", type=int, default=None,
                        help="which duplicate block to read (default: 0, the first)")
    blocks.add_argument("--all-blocks", action="store_true",
                        help="export every block as <output-stem>-<index>.<ext>")
    parser.add_argument("-o", "--out", required=True, type=Path)
    args = parser.parse_args()

    registry = importlib.import_module(f"languages.{args.lang}.sprites").SPRITES
    if args.sprite not in registry:
        raise SystemExit(
            f"Unknown sprite {args.sprite!r} for lang {args.lang!r}. "
            f"Known: {', '.join(sorted(registry)) or '(none)'}"
        )
    sprite = registry[args.sprite]
    if args.block_index is not None and not 0 <= args.block_index < len(sprite.blocks):
        raise SystemExit(f"--block-index must be in [0, {len(sprite.blocks) - 1}]")
    indices = (
        list(range(len(sprite.blocks)))
        if args.all_blocks
        else [args.block_index if args.block_index is not None else 0]
    )

    rom = args.rom.read_bytes()
    width = sprite.tiles_wide * 8
    height = sprite.tiles_tall * 8
    if sprite.palette is not None:
        palette = read_gba_palette(
            rom,
            sprite.palette,
            colours=1 << sprite.bits_per_pixel,
        )
    elif sprite.bits_per_pixel == 4:
        palette = DEFAULT_PALETTE
    else:
        raise SystemExit(
            f"{args.sprite!r}: an 8bpp sprite requires a 256-colour palette"
        )
    for index in indices:
        offset = resolve_live_offset(
            rom,
            sprite.blocks[index],
            sprite.block_pointers[index] if sprite.block_pointers else (),
        )
        if sprite.tilemaps:
            tilemap_offset = resolve_live_offset(
                rom,
                sprite.tilemaps[index],
                (
                    sprite.tilemap_pointers[index]
                    if sprite.tilemap_pointers
                    else ()
                ),
            )
            grid, dec_len, comp_len = extract_mapped_block(
                rom,
                offset,
                tilemap_offset,
                sprite.tiles_wide,
                sprite.tiles_tall,
                compressed=sprite.compressed,
                bits_per_pixel=sprite.bits_per_pixel,
            )
        else:
            start_tile = (
                sprite.start_tiles[index]
                if sprite.start_tiles
                else 0
            )
            grid, dec_len, comp_len = extract_block(
                rom, offset, sprite.tiles_wide, sprite.tiles_tall,
                compressed=sprite.compressed,
                bits_per_pixel=sprite.bits_per_pixel,
                start_tile=start_tile,
            )
        out = variant_path(args.out, index) if args.all_blocks else args.out
        try:
            write_indexed_image(out, width, height, grid, palette)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        print(
            f"{args.sprite}[{index}] @ 0x{offset:08X}: "
            f"{width}x{height} -> {out} "
            f"(decompressed {dec_len}B, compressed {comp_len}B)"
            + (
                f", tilemap 0x{tilemap_offset:08X}"
                if sprite.tilemaps
                else ""
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
