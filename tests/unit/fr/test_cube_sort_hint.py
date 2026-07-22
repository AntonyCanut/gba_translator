"""Garde du bandeau graphique « START Tri » du Cube (issue #140)."""

from pathlib import Path

from languages.fr.sprites import SPRITES
from src.graphics.sprite_bmp import read_indexed_bmp


ROOT = Path(__file__).resolve().parents[3]
ASSET = ROOT / "languages/fr/sprites/cube_sort_hint.bmp"

# Masque blanc (index de palette 3) attendu dans la zone du libellé.
# Le gris d'ombrage est volontairement ignoré : ce masque suffit à empêcher
# le retour du mot anglais « Sort » tout en figeant la lecture « Tri ».
TRI_WHITE_ROWS = (
    ".#####........#.",
    "...#............",
    "...#....###...#.",
    "...#....#..#..#.",
    "...#....#.....#.",
    "...#....#.....#.",
    "...#....#.....#.",
    "................",
)


def test_cube_sort_hint_registry_targets_live_lz77_block() -> None:
    sprite = SPRITES["cube_sort_hint"]
    assert sprite.blocks == (0x00EF1B68,)
    assert (sprite.tiles_wide, sprite.tiles_tall) == (13, 4)
    assert sprite.compressed


def test_cube_sort_hint_asset_draws_tri() -> None:
    width, height, grid = read_indexed_bmp(ASSET)
    assert (width, height) == (104, 32)

    actual = tuple(
        "".join("#" if pixel == 3 else "." for pixel in row[:16])
        for row in grid[12:20]
    )
    assert actual == TRI_WHITE_ROWS


def test_french_build_inserts_cube_sort_hint() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert (
        "scripts/insert_sprite.py --rom $(FR_BUILD) --lang fr "
        "--sprite cube_sort_hint --bmp languages/fr/sprites/cube_sort_hint.bmp"
    ) in makefile
