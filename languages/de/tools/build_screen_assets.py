#!/usr/bin/env python3
"""Reconstruit les écrans graphiques allemands depuis la ROM anglaise.

Le décor, les palettes et les indices viennent directement des ressources ROM
vivantes. Seuls les rectangles des libellés sont redessinés, ce qui garde les
tuiles partagées et les zones animées identiques à la source.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from languages.de.patches.type_icons import _FONT as GAME_FONT  # noqa: E402
from languages.de.sprites import SPRITES  # noqa: E402
from src.graphics.sprite_image import DEFAULT_PALETTE, write_indexed_image  # noqa: E402
from src.graphics.sprite_rom import (  # noqa: E402
    extract_mapped_block,
    read_gba_palette,
    resolve_live_offset,
)

LABELS = {
    "title_screen": "START DRÜCKEN",
    "trainer_card_front": "TRAINERPASS",
    "trainer_card_back": "LIGA-ORDEN",
}

# Demi-ouvert : x0, y0, x1, y1. Ces boîtes couvrent le dessin anglais sans
# atteindre le symbole de Carte Dresseur ni les contours de l'écran titre.
LABEL_REGIONS = {
    "title_screen": (64, 145, 192, 158),
    "trainer_card_front": (17, 4, 145, 18),
    "trainer_card_back": (17, 4, 130, 18),
}

_FONT = {
    **GAME_FONT,
    " ": ["000"] * 7,
    "-": ["000", "000", "000", "111", "000", "000", "000"],
    "Ü": ["1001", "0000", "1001", "1001", "1001", "1001", "0110"],
}


def _text_width(text: str) -> int:
    """Retourne la largeur en pixels d'un libellé avec espacement d'un pixel."""
    return sum(len(_FONT[char][0]) for char in text) + len(text) - 1


def _draw_label(
    grid: list[list[int]],
    name: str,
    text: str,
) -> None:
    """Efface le libellé anglais et dessine son équivalent allemand.

    Args:
        grid: Grille d'indices de palette 256 × 160 extraite de la ROM.
        name: Nom du sprite enregistré.
        text: Libellé allemand à centrer dans la zone dédiée.
    """
    x0, y0, x1, y1 = LABEL_REGIONS[name]
    if name == "title_screen":
        # Le texte animé partage son rectangle avec le contour de Hoopa : seuls
        # ses deux indices sont effacés, jamais les pixels du dessin voisin.
        for y in range(y0, y1):
            for x in range(x0, x1):
                if grid[y][x] in {163, 164}:
                    grid[y][x] = 31
        # Un seul indice garde ce libellé sous le budget LZ77 du bloc original.
        # Le build DE ne conserve plus de plage libre assez grande pour une
        # relocalisation tardive, contrairement à la ROM anglaise source.
        fill, shadow = 163, None
    else:
        for y in range(y0, y1):
            grid[y][x0:x1] = [4] * (x1 - x0)
        fill, shadow = 9, 8

    width = _text_width(text)
    height = len(next(iter(_FONT.values())))
    x = x0 + (x1 - x0 - width) // 2
    y = y0 + (y1 - y0 - height - 1) // 2
    if x < x0 or y < y0:
        raise ValueError(f"{name}: label {text!r} does not fit its region")

    cursor = x
    for char in text:
        glyph = _FONT[char]
        for gy, row in enumerate(glyph):
            for gx, pixel in enumerate(row):
                if pixel == "1":
                    if shadow is not None:
                        grid[y + gy + 1][cursor + gx + 1] = shadow
                    grid[y + gy][cursor + gx] = fill
        cursor += len(glyph[0]) + 1


def _extract_source(
    rom: bytes,
    name: str,
) -> tuple[list[list[int]], list[tuple[int, int, int, int]]]:
    """Extrait la grille mappée et sa palette depuis les pointeurs vivants.

    Args:
        rom: Octets complets de la ROM anglaise.
        name: Nom du sprite dans le registre DE.

    Returns:
        La grille d'indices et la palette RGBA à réutiliser.
    """
    sprite = SPRITES[name]
    tiles_offset = resolve_live_offset(
        rom,
        sprite.blocks[0],
        sprite.block_pointers[0] if sprite.block_pointers else (),
    )
    tilemap_offset = resolve_live_offset(
        rom,
        sprite.tilemaps[0],
        sprite.tilemap_pointers[0] if sprite.tilemap_pointers else (),
    )
    grid, _, _ = extract_mapped_block(
        rom,
        tiles_offset,
        tilemap_offset,
        sprite.tiles_wide,
        sprite.tiles_tall,
        bits_per_pixel=sprite.bits_per_pixel,
    )
    palette = (
        read_gba_palette(rom, sprite.palette, colours=1 << sprite.bits_per_pixel)
        if sprite.palette is not None
        else DEFAULT_PALETTE
    )
    return grid, palette


def build_assets(source_rom: Path, output_dir: Path) -> tuple[Path, ...]:
    """Génère les PNG et BMP DE à partir des ressources exactes de la ROM.

    Args:
        source_rom: ROM anglaise BPRE01 en lecture seule.
        output_dir: Dossier de sortie des six images indexées.

    Returns:
        Les chemins des trois PNG et des trois BMP créés.
    """
    rom = source_rom.read_bytes()
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, text in LABELS.items():
        grid, palette = _extract_source(rom, name)
        _draw_label(grid, name, text)
        for suffix in ("png", "bmp"):
            path = output_dir / f"{name}.{suffix}"
            write_indexed_image(path, 256, 160, grid, palette)
            written.append(path)
    return tuple(written)


def main() -> int:
    """Point d'entrée CLI du générateur reproductible."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        type=Path,
        default=ROOT_DIR / "input/roms/englishrom.gba",
        help="ROM anglaise source",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "languages/de/sprites",
    )
    args = parser.parse_args()
    for path in build_assets(args.rom, args.output_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
