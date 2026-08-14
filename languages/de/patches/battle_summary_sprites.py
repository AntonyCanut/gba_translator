#!/usr/bin/env python3
"""Réinjecte les sources raster DE des écrans combat, équipe et résumé."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from languages.de.sprites import SPRITES
from scripts.insert_sprite import _write_rom_safely
from src.graphics.sprite_image import read_indexed_image, variant_path
from src.graphics.sprite_rom import insert_block, resolve_live_offset

ASSET_DIR = ROOT / "languages/de/sprites"
SPRITE_NAMES = (
    "status_badges",
    "type_icons_summary",
    "type_icons_battle",
    "party_kp_label",
    "summary_kp_bar",
    "summary_stat_labels",
    "battle_kp_labels",
    "battle_kp_elements",
    "level_marker",
)


@dataclass(frozen=True)
class SpritePatch:
    """Associe une copie de sprite à son PNG indexé allemand."""

    sprite: str
    image: Path
    block_index: int = 0


def _asset(name: str, index: int) -> Path:
    """Retourne le PNG d'une copie, avec suffixe pour les familles multiples."""
    base = ASSET_DIR / f"{name}.png"
    return variant_path(base, index) if len(SPRITES[name].blocks) > 1 else base


PATCHES = tuple(
    SpritePatch(name, _asset(name, index), index)
    for name in SPRITE_NAMES
    for index in range(len(SPRITES[name].blocks))
)


def apply_to_rom(rom_path: Path, asset_dir: Path = ASSET_DIR) -> int:
    """Valide puis réinjecte toutes les copies graphiques dans la ROM DE.

    Args:
        rom_path: ROM allemande produite par le builder générique.
        asset_dir: Dossier des sources PNG indexées.

    Returns:
        Nombre de fenêtres de tuiles réinjectées.
    """
    prepared: list[tuple[SpritePatch, list[list[int]]]] = []
    for patch in PATCHES:
        sprite = SPRITES[patch.sprite]
        image = asset_dir / patch.image.name
        width, height, grid = read_indexed_image(image)
        expected = (sprite.tiles_wide * 8, sprite.tiles_tall * 8)
        if (width, height) != expected:
            raise ValueError(
                f"{image.name}: attendu {expected[0]}x{expected[1]}, "
                f"obtenu {width}x{height}"
            )
        prepared.append((patch, grid))

    rom = bytearray(rom_path.read_bytes())
    if len(rom) <= 0xB2 or rom[0xB2] != 0x96:
        raise ValueError(f"ROM GBA invalide : {rom_path}")

    for patch, grid in prepared:
        sprite = SPRITES[patch.sprite]
        index = patch.block_index
        pointer_offsets = (
            sprite.block_pointers[index] if sprite.block_pointers else ()
        )
        offset = resolve_live_offset(rom, sprite.blocks[index], pointer_offsets)
        insert_block(
            rom,
            offset,
            grid,
            sprite.tiles_wide,
            sprite.tiles_tall,
            compressed=sprite.compressed,
            vram_safe=sprite.vram_safe,
            bits_per_pixel=sprite.bits_per_pixel,
            start_tile=sprite.start_tiles[index] if sprite.start_tiles else 0,
            max_compressed_size=(
                sprite.max_compressed_sizes[index]
                if sprite.max_compressed_sizes
                else None
            ),
            pointer_offsets=pointer_offsets,
        )

    _write_rom_safely(rom_path, bytes(rom))
    return len(prepared)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI appelé en fin de build DE."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.rom.exists():
        raise SystemExit(f"ROM introuvable : {args.rom}")
    count = apply_to_rom(args.rom)
    print(f"battle_summary_sprites_de: {count} copie(s) injectée(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
