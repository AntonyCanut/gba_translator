"""Gardes du graphisme éditable de l’écran titre (issue #155)."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from languages.fr.patches.font import lz77_decompress
from languages.fr.sprites import SPRITES
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_mapped_block

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "languages" / "fr" / "sprites" / "title_screen.png"
INPUT_ROM = ROOT / "input" / "roms" / "englishrom.gba"
TILES_OFFSET = 0x01FD4854
TILEMAP_OFFSET = 0x01FD6514
PALETTE_OFFSET = 0x01FD699C


def test_title_screen_registry_describes_live_8bpp_screen() -> None:
    # Act
    sprite = SPRITES["title_screen"]

    # Assert
    assert sprite.blocks == (0x01FD4854,)
    assert sprite.tilemaps == (0x01FD6514,)
    assert sprite.palette == 0x01FD699C
    assert (sprite.tiles_wide, sprite.tiles_tall) == (32, 20)
    assert sprite.bits_per_pixel == 8


@pytest.mark.rom
def test_extract_cli_exports_8bpp_title_screen(tmp_path: Path) -> None:
    # Arrange
    output = tmp_path / "title-screen.png"

    # Act
    subprocess.run(
        [
            "python3",
            "scripts/extract_sprite.py",
            "--rom",
            str(INPUT_ROM),
            "--lang",
            "fr",
            "--sprite",
            "title_screen",
            "-o",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    width, height, grid = read_indexed_image(output)

    # Assert
    assert (width, height) == (256, 160)
    assert max(pixel for row in grid for pixel in row) > 15


def test_versioned_title_screen_asset_is_indexed_full_screen() -> None:
    # Act
    width, height, grid = read_indexed_image(ASSET)

    # Assert
    assert (width, height) == (256, 160)
    assert max(pixel for row in grid for pixel in row) > 15


def test_versioned_title_screen_asset_keeps_a_visible_prompt() -> None:
    # Arrange
    _, _, grid = read_indexed_image(ASSET)

    # Act: les couleurs 163/164 dessinent le lettrage du prompt en bas d'écran.
    prompt = [pixel for row in grid[144:153] for pixel in row[64:176]]

    # Assert: protège la zone sans figer le texte anglais pixel par pixel.
    assert {163, 164} <= set(prompt)
    assert sum(pixel in {163, 164} for pixel in prompt) >= 100


def test_versioned_title_screen_asset_contains_pressez_start_artwork() -> None:
    # Arrange
    _, _, grid = read_indexed_image(ASSET)

    # Act: empreinte des seuls pixels retouchés dans le BMP fourni.
    prompt = bytes(
        grid[y][x]
        for y in range(149, 154)
        for x in range(80, 161)
    )

    # Assert
    assert hashlib.sha256(prompt).hexdigest() == (
        "3c291170c102a82a0e0e8985abd3e1c383923e226149cda90ae5d0d46ded3d2a"
    )


def test_build_fr_injects_versioned_title_screen_asset() -> None:
    # Act
    result = subprocess.run(
        ["make", "-n", "build-fr"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    # Assert
    assert (
        "scripts/insert_sprite.py --rom output/roms/GenedRom-fr.gba "
        "--lang fr --sprite title_screen "
        "--image languages/fr/sprites/title_screen.png"
    ) in result.stdout


@pytest.mark.rom
def test_insert_cli_round_trips_8bpp_title_screen(tmp_path: Path) -> None:
    # Arrange
    output_rom = tmp_path / "title-screen-roundtrip.gba"
    shutil.copy2(INPUT_ROM, output_rom)
    source_rom = INPUT_ROM.read_bytes()
    source_tiles = lz77_decompress(source_rom, TILES_OFFSET)
    source_tilemap = lz77_decompress(source_rom, TILEMAP_OFFSET)
    assert source_tiles is not None
    assert source_tilemap is not None

    # Act
    subprocess.run(
        [
            "python3",
            "scripts/insert_sprite.py",
            "--rom",
            str(output_rom),
            "--lang",
            "fr",
            "--sprite",
            "title_screen",
            "--image",
            str(ASSET),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    actual_rom = output_rom.read_bytes()
    actual_tiles = lz77_decompress(actual_rom, TILES_OFFSET)
    actual_tilemap = lz77_decompress(actual_rom, TILEMAP_OFFSET)
    expected_width, expected_height, expected_grid = read_indexed_image(ASSET)
    actual_grid, _, _ = extract_mapped_block(
        actual_rom,
        TILES_OFFSET,
        TILEMAP_OFFSET,
        tiles_wide=expected_width // 8,
        tiles_tall=expected_height // 8,
        bits_per_pixel=8,
    )

    # Assert
    assert actual_tiles is not None
    assert actual_tilemap is not None
    assert len(actual_tiles[0]) == len(source_tiles[0])
    assert actual_grid == expected_grid
    assert actual_rom[PALETTE_OFFSET : PALETTE_OFFSET + 512] == source_rom[
        PALETTE_OFFSET : PALETTE_OFFSET + 512
    ]
    assert actual_rom[:TILES_OFFSET] == source_rom[:TILES_OFFSET]
    tiles_end = TILES_OFFSET + max(source_tiles[1], actual_tiles[1])
    tilemap_end = TILEMAP_OFFSET + max(source_tilemap[1], actual_tilemap[1])
    assert actual_rom[tiles_end:TILEMAP_OFFSET] == source_rom[tiles_end:TILEMAP_OFFSET]
    assert actual_rom[tilemap_end:PALETTE_OFFSET] == source_rom[tilemap_end:PALETTE_OFFSET]
    assert actual_rom[PALETTE_OFFSET:] == source_rom[PALETTE_OFFSET:]
