"""Gardes des graphismes éditables de la carte de Dresseur."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from languages.fr.sprites import SPRITES, SpriteDef
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_mapped_block

ROOT = Path(__file__).resolve().parents[2]
BACK_ASSET = ROOT / "languages" / "fr" / "sprites" / "trainer_card_back.png"
BUILT_ROM = ROOT / "output" / "roms" / "GenedRom-fr.gba"
BADGES_DE_LIGUE_ROWS = (
    "999994449999449999944499994499999449999444499999449999944449944449944999944994499499999",
    "994499499449949944994994499499444499444444499449949944444449944449949944994994499499444",
    "994499499449949944994994499499444499444444499449949944444449944449949944994994499499444",
    "994499499449949944994994444499444499444444499449949944444449944449949944444994499499444",
    "999994499999949944994994444499999449994444499449949999944449944449949944444994499499999",
    "994499499449949944994994999499444444499444499449949944444449944449949949994994499499444",
    "994499499449949944994994499499444444499444499449949944444449944449949944994994499499444",
    "994499499449949944994994499499444444499444499449949944444449944449949944994994499499444",
    "999994499449949999944499994499999499994444499999449999944449999949944999944499994499999",
)


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


def test_trainer_card_back_uses_contributed_french_heading() -> None:
    """Le verso versionné doit conserver exactement le dessin fourni."""
    _, _, grid = read_indexed_image(BACK_ASSET)

    actual = tuple(
        "".join(f"{pixel:X}" for pixel in row[21:108])
        for row in grid[7:16]
    )

    assert actual == BADGES_DE_LIGUE_ROWS


def test_french_build_inserts_trainer_card_back() -> None:
    """La recette FR doit exécuter la réinjection du verso traduit."""
    result = subprocess.run(
        ["make", "-n", "build-fr"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        "scripts/insert_sprite.py --rom output/roms/GenedRom-fr.gba "
        "--lang fr --sprite trainer_card_back "
        "--image languages/fr/sprites/trainer_card_back.png"
    ) in result.stdout


@pytest.mark.rom
def test_built_french_rom_contains_trainer_card_back_asset() -> None:
    """Le rendu mappé de la ROM doit être identique à l’asset versionné."""
    sprite = SPRITES["trainer_card_back"]
    _, _, expected = read_indexed_image(BACK_ASSET)

    actual, decompressed_len, _ = extract_mapped_block(
        BUILT_ROM.read_bytes(),
        sprite.blocks[0],
        sprite.tilemaps[0],
        sprite.tiles_wide,
        sprite.tiles_tall,
        compressed=sprite.compressed,
    )

    assert decompressed_len == 6_688
    assert actual == expected
