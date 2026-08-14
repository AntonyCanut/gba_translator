#!/usr/bin/env python3
"""Injecte les écrans titre et Carte Dresseur allemands dans la ROM DE."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from languages.de.sprites import SPRITES  # noqa: E402
from scripts.insert_sprite import _write_rom_safely  # noqa: E402
from src.graphics.sprite_image import read_indexed_image  # noqa: E402
from src.graphics.sprite_rom import (  # noqa: E402
    insert_mapped_block,
    resolve_live_offset,
)

ASSET_NAMES = (
    "title_screen",
    "trainer_card_front",
    "trainer_card_back",
)
ASSET_DIR = ROOT_DIR / "languages/de/sprites"


def apply_to_rom(rom_path: Path, asset_dir: Path = ASSET_DIR) -> int:
    """Réinjecte les trois écrans allemands dans une ROM de sortie.

    Args:
        rom_path: ROM DE produite par le builder générique.
        asset_dir: Dossier contenant les PNG indexés versionnés.

    Returns:
        Nombre d'écrans réinjectés.
    """
    prepared: list[tuple[str, list[list[int]]]] = []
    for name in ASSET_NAMES:
        sprite = SPRITES[name]
        width, height, grid = read_indexed_image(asset_dir / f"{name}.png")
        expected = (sprite.tiles_wide * 8, sprite.tiles_tall * 8)
        if (width, height) != expected:
            raise ValueError(
                f"{name}: expected {expected[0]}x{expected[1]}, got {width}x{height}"
            )
        prepared.append((name, grid))

    rom = bytearray(rom_path.read_bytes())
    for name, grid in prepared:
        sprite = SPRITES[name]
        block_pointers = sprite.block_pointers[0] if sprite.block_pointers else ()
        tilemap_pointers = (
            sprite.tilemap_pointers[0] if sprite.tilemap_pointers else ()
        )
        tiles_offset = resolve_live_offset(
            rom,
            sprite.blocks[0],
            block_pointers,
        )
        tilemap_offset = resolve_live_offset(
            rom,
            sprite.tilemaps[0],
            tilemap_pointers,
        )
        insert_mapped_block(
            rom,
            tiles_offset,
            tilemap_offset,
            grid,
            sprite.tiles_wide,
            sprite.tiles_tall,
            compressed=sprite.compressed,
            vram_safe=sprite.vram_safe,
            bits_per_pixel=sprite.bits_per_pixel,
            tiles_pointer_offsets=block_pointers,
            tilemap_pointer_offsets=tilemap_pointers,
        )

    _write_rom_safely(rom_path, bytes(rom))
    return len(prepared)


def main() -> int:
    """Point d'entrée CLI appelé par le driver multilingue."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args()
    patched = apply_to_rom(args.rom)
    print(f"screen_graphics_de: {patched} screen(s) patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
