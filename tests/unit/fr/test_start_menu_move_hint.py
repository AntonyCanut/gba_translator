"""Régressions du libellé français de déplacement du menu START (#107)."""

from pathlib import Path

from languages.fr.sprites import SPRITES
from src.graphics.sprite_bmp import read_indexed_bmp
from src.graphics.sprite_rom import extract_block


ROOT = Path(__file__).resolve().parents[3]
ASSET = ROOT / "languages/fr/sprites/start_menu_move_hint.bmp"
BUILT_ROM = ROOT / "output/roms/GenedRom-fr.gba"
EXPECTED_LABEL_PIXELS = (
    "1eeef111ef111111ef111111",
    "feffef1eff111111ef111111",
    "fef2ef2eef2eeef2ef222222",
    "fef2efeffefeffefef222222",
    "fef3efeeeefef3efef333333",
    "fef3efeffffef3efefeef333",
    "feeefffeeefeeeffefeef444",
    "4ffff44ffffefff4fffff444",
)


def test_start_menu_move_hint_uses_depl_pixels() -> None:
    """Le dernier groupe de trois tuiles doit dessiner « Dépl. »."""
    width, height, grid = read_indexed_bmp(ASSET)

    label_pixels = tuple("".join(f"{pixel:x}" for pixel in row[96:]) for row in grid)

    assert (width, height) == (120, 8)
    assert label_pixels == EXPECTED_LABEL_PIXELS


def test_start_menu_move_hint_is_inserted_by_french_build() -> None:
    """La recette française doit injecter l’asset corrigé dans la ROM."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    expected_command = (
        "scripts/insert_sprite.py --rom $(FR_BUILD) --lang fr "
        "--sprite start_menu_move_hint "
        "--bmp languages/fr/sprites/start_menu_move_hint.bmp"
    )

    assert expected_command in makefile


def test_built_french_rom_contains_depl_pixels() -> None:
    """La ROM française livrée doit contenir le même dessin que l’asset."""
    sprite = SPRITES["start_menu_move_hint"]
    _, _, expected_grid = read_indexed_bmp(ASSET)

    actual_grid, _, _ = extract_block(
        BUILT_ROM.read_bytes(),
        sprite.blocks[0],
        sprite.tiles_wide,
        sprite.tiles_tall,
    )

    assert actual_grid == expected_grid
