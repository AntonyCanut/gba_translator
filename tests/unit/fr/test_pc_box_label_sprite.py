"""Régressions de l'asset éditable des libellés de boîtes PC (#163)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from languages.fr.sprites import SPRITES
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_block


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROM = ROOT / "input" / "roms" / "englishrom.gba"
ASSET = ROOT / "languages" / "fr" / "sprites" / "pc_box_labels.png"


def test_pc_box_labels_registry_targets_the_live_tilesheet() -> None:
    """Une mauvaise adresse, palette ou grille rendrait le PNG non éditable."""
    sprite = SPRITES["pc_box_labels"]

    assert sprite.blocks == (0x00E9C438,)
    assert sprite.block_pointers == ((0x0008F034,),)
    assert sprite.palette == 0x003CE5DC
    assert (sprite.tiles_wide, sprite.tiles_tall) == (16, 9)


def test_pc_box_labels_asset_is_a_128_by_72_indexed_image() -> None:
    """Un PNG true-colour ou recadré ne pourrait pas être réinjecté tel quel."""
    width, height, _ = read_indexed_image(ASSET)

    assert (width, height) == (128, 72)


def test_pc_box_labels_asset_preserves_english_rom_palette_indices() -> None:
    """Des indices modifiés sans intention changeraient le dessin extrait."""
    sprite = SPRITES["pc_box_labels"]
    _, _, asset_grid = read_indexed_image(ASSET)
    source_grid, _, _ = extract_block(
        SOURCE_ROM.read_bytes(),
        sprite.blocks[0],
        sprite.tiles_wide,
        sprite.tiles_tall,
    )

    assert asset_grid == source_grid


def test_french_build_does_not_insert_untranslated_pc_box_labels() -> None:
    """L'asset anglais éditable ne doit pas entrer dans la ROM française."""
    result = subprocess.run(
        ["make", "-n", "build-fr"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "pc_box_labels" not in result.stdout
