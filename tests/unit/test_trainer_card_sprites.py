"""Gardes des graphismes éditables de la carte de Dresseur."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from languages.fr.sprites import SPRITES, SpriteDef
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_mapped_block

ROOT = Path(__file__).resolve().parents[2]
FRONT_ASSET = ROOT / "languages" / "fr" / "sprites" / "trainer_card_front.png"
FRONT_REFERENCE = ROOT / "languages" / "fr" / "sprites" / "trainer_card_front.bmp"
BACK_ASSET = ROOT / "languages" / "fr" / "sprites" / "trainer_card_back.png"
BACK_REFERENCE = ROOT / "languages" / "fr" / "sprites" / "trainer_card_back.bmp"
BUILT_ROM = ROOT / "output" / "roms" / "GenedRom-fr.gba"
FRONT_REFERENCE_SHA256 = "64afede2c86875bbba38fbb0dce0c632b3ee1d8a668a8458e17984603173f47c"
FRONT_GRID_SHA256 = "3b019d70cf28bfbb51a2d83e862e1272cade731e4889be604f06f0ebea9cd8d1"
BACK_REFERENCE_SHA256 = "fdce7fafb925b87c339f58e26d6ca3e713669bf1197d62a1b4930e10842a8eb4"
BACK_GRID_SHA256 = "a429790465cf2bd715136a955d85f7ee52b251c99d5310ee78c95a33c2403435"
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


def test_sprite_registry_rejects_unpaired_block_pointers() -> None:
    with pytest.raises(ValueError, match="pointer sets for every block"):
        SpriteDef(
            blocks=(0x10, 0x20),
            block_pointers=((0x30,),),
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


def test_trainer_card_back_declares_verified_tilemap_pointer() -> None:
    assert SPRITES["trainer_card_back"].tilemap_pointers == ((0x01ED8AB8,),)


def test_trainer_card_front_declares_verified_block_pointers() -> None:
    sprite = SPRITES["trainer_card_front"]

    assert sprite.block_pointers == ((0x01ED8AA4,),)
    assert sprite.tilemap_pointers == ((0x01ED8AA8,),)


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


def test_trainer_card_back_keeps_complete_contributed_render() -> None:
    """Le PNG doit inclure le texte et les ornements déplacés du BMP fourni."""
    assert BACK_REFERENCE.exists(), "le BMP original doit rester versionné"
    assert hashlib.sha256(BACK_REFERENCE.read_bytes()).hexdigest() == (
        BACK_REFERENCE_SHA256
    )

    bmp_width, bmp_height, bmp_grid = read_indexed_image(BACK_REFERENCE)
    png_width, png_height, png_grid = read_indexed_image(BACK_ASSET)
    grid_bytes = bytes(pixel for row in png_grid for pixel in row)

    assert (png_width, png_height) == (bmp_width, bmp_height)
    assert hashlib.sha256(grid_bytes).hexdigest() == BACK_GRID_SHA256
    assert png_grid == bmp_grid


def test_trainer_card_front_keeps_complete_contributed_render() -> None:
    """Le PNG doit reprendre chaque pixel du nouveau BMP recto."""
    assert FRONT_REFERENCE.exists(), "le BMP original doit rester versionné"
    assert hashlib.sha256(FRONT_REFERENCE.read_bytes()).hexdigest() == (
        FRONT_REFERENCE_SHA256
    )

    bmp_width, bmp_height, bmp_grid = read_indexed_image(FRONT_REFERENCE)
    png_width, png_height, png_grid = read_indexed_image(FRONT_ASSET)
    grid_bytes = bytes(pixel for row in png_grid for pixel in row)

    assert (png_width, png_height) == (bmp_width, bmp_height)
    assert hashlib.sha256(grid_bytes).hexdigest() == FRONT_GRID_SHA256
    assert png_grid == bmp_grid


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


def test_french_build_inserts_trainer_card_front() -> None:
    """La recette FR doit exécuter la réinjection du recto traduit."""
    result = subprocess.run(
        ["make", "-n", "build-fr"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        "scripts/insert_sprite.py --rom output/roms/GenedRom-fr.gba "
        "--lang fr --sprite trainer_card_front "
        "--image languages/fr/sprites/trainer_card_front.png"
    ) in result.stdout


@pytest.mark.rom
def test_built_french_rom_contains_trainer_card_front_asset() -> None:
    """Le rendu recto vivant doit être identique au BMP fourni."""
    sprite = SPRITES["trainer_card_front"]
    rom = BUILT_ROM.read_bytes()
    _, _, expected = read_indexed_image(FRONT_REFERENCE)
    tiles_offset = (
        int.from_bytes(
            rom[sprite.block_pointers[0][0]:sprite.block_pointers[0][0] + 4],
            "little",
        )
        - 0x08000000
    )
    tilemap_offset = (
        int.from_bytes(
            rom[
                sprite.tilemap_pointers[0][0]:sprite.tilemap_pointers[0][0] + 4
            ],
            "little",
        )
        - 0x08000000
    )

    actual, _, _ = extract_mapped_block(
        rom,
        tiles_offset,
        tilemap_offset,
        sprite.tiles_wide,
        sprite.tiles_tall,
        compressed=sprite.compressed,
    )

    assert tiles_offset != sprite.blocks[0]
    assert actual == expected


@pytest.mark.rom
def test_built_french_rom_contains_trainer_card_back_asset() -> None:
    """Le rendu mappé de la ROM doit être identique à l’asset versionné."""
    sprite = SPRITES["trainer_card_back"]
    rom = BUILT_ROM.read_bytes()
    _, _, expected = read_indexed_image(BACK_ASSET)
    tilemap_pointer_offset = sprite.tilemap_pointers[0][0]
    tilemap_offset = (
        int.from_bytes(
            rom[tilemap_pointer_offset:tilemap_pointer_offset + 4],
            "little",
        )
        - 0x08000000
    )

    actual, decompressed_len, compressed_len = extract_mapped_block(
        rom,
        sprite.blocks[0],
        tilemap_offset,
        sprite.tiles_wide,
        sprite.tiles_tall,
        compressed=sprite.compressed,
    )

    assert tilemap_offset != sprite.tilemaps[0]
    assert decompressed_len == 6_752
    assert compressed_len == 2_107
    assert actual == expected
