"""Gardes des graphismes éditables de la carte de Dresseur."""

from __future__ import annotations

from pathlib import Path

import pytest

from languages.fr.sprites import SPRITES, SpriteDef
from src.graphics.sprite_image import read_indexed_image

ROOT = Path(__file__).resolve().parents[2]


def test_sprite_registry_rejects_unpaired_tilemaps() -> None:
    with pytest.raises(ValueError, match="one tilemap per block"):
        SpriteDef(
            blocks=(0x10, 0x20),
            tilemaps=(0x30,),
            tiles_wide=1,
            tiles_tall=1,
        )


@pytest.mark.parametrize(
    ("name", "tiles_offset", "tilemap_offset"),
    [
        ("trainer_card_front", 0x01FDA2BC, 0x01FDA820),
        ("trainer_card_back", 0x01FDAA4C, 0x01FDB2AC),
    ],
)
def test_trainer_card_registry_pairs_tiles_and_tilemaps(
    name: str,
    tiles_offset: int,
    tilemap_offset: int,
) -> None:
    sprite = SPRITES[name]

    assert sprite.blocks == (tiles_offset,)
    assert sprite.tilemaps == (tilemap_offset,)
    assert (sprite.tiles_wide, sprite.tiles_tall) == (32, 20)


@pytest.mark.parametrize(
    "name",
    ["trainer_card_front", "trainer_card_back"],
)
def test_trainer_card_editable_asset_is_indexed_full_screen(name: str) -> None:
    asset = ROOT / "languages" / "fr" / "sprites" / f"{name}.png"

    width, height, grid = read_indexed_image(asset)

    assert (width, height) == (256, 160)
    assert all(0 <= pixel <= 15 for row in grid for pixel in row)
