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
TILES_POINTER_OFFSETS = (0x01ED7C7C, 0x01ED7EC0)
TILEMAP_POINTER_OFFSETS = (0x01ED7C84, 0x01ED7EC8)
GBA_ROM_BASE = 0x08000000


def test_title_screen_registry_describes_live_8bpp_screen() -> None:
    # Act
    sprite = SPRITES["title_screen"]

    # Assert
    assert sprite.blocks == (0x01FD4854,)
    assert sprite.tilemaps == (0x01FD6514,)
    assert sprite.palette == 0x01FD699C
    assert (sprite.tiles_wide, sprite.tiles_tall) == (32, 20)
    assert sprite.bits_per_pixel == 8
    assert sprite.block_pointers == (TILES_POINTER_OFFSETS,)
    assert sprite.tilemap_pointers == (TILEMAP_POINTER_OFFSETS,)


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
    assert grid[152][160] == 164
    assert grid[153][160] == 164
    assert hashlib.sha256(prompt).hexdigest() == (
        "b4603667ffb9d2b91fd64b7e8beae0e83229dd8be2139e947159c742c61f91fc"
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
    relocated_tiles_offsets = {
        int.from_bytes(actual_rom[offset:offset + 4], "little") - GBA_ROM_BASE
        for offset in TILES_POINTER_OFFSETS
    }
    relocated_tilemap_offsets = {
        int.from_bytes(actual_rom[offset:offset + 4], "little") - GBA_ROM_BASE
        for offset in TILEMAP_POINTER_OFFSETS
    }
    assert len(relocated_tiles_offsets) == 1
    assert len(relocated_tilemap_offsets) == 1
    relocated_tiles_offset = relocated_tiles_offsets.pop()
    relocated_tilemap_offset = relocated_tilemap_offsets.pop()
    actual_tiles = lz77_decompress(actual_rom, relocated_tiles_offset)
    actual_tilemap = lz77_decompress(actual_rom, relocated_tilemap_offset)
    expected_width, expected_height, expected_grid = read_indexed_image(ASSET)
    actual_grid, _, _ = extract_mapped_block(
        actual_rom,
        relocated_tiles_offset,
        relocated_tilemap_offset,
        tiles_wide=expected_width // 8,
        tiles_tall=expected_height // 8,
        bits_per_pixel=8,
    )

    # Assert
    assert actual_tiles is not None
    assert actual_tilemap is not None
    assert relocated_tiles_offset == TILES_OFFSET
    assert relocated_tilemap_offset != TILEMAP_OFFSET
    assert len(actual_tiles[0]) == len(source_tiles[0]) + 64
    assert actual_grid == expected_grid
    assert actual_grid[152][160] == 164
    assert actual_grid[153][160] == 164
    assert actual_rom[TILEMAP_OFFSET:PALETTE_OFFSET] == source_rom[
        TILEMAP_OFFSET:PALETTE_OFFSET
    ]
    assert actual_rom[PALETTE_OFFSET : PALETTE_OFFSET + 512] == source_rom[
        PALETTE_OFFSET : PALETTE_OFFSET + 512
    ]

    allowed_changes = set()
    for pointer_offset in TILEMAP_POINTER_OFFSETS:
        allowed_changes.update(range(pointer_offset, pointer_offset + 4))
    allowed_changes.update(
        range(
            TILES_OFFSET,
            TILES_OFFSET + max(source_tiles[1], actual_tiles[1]),
        )
    )
    allowed_changes.update(
        range(relocated_tilemap_offset, relocated_tilemap_offset + actual_tilemap[1])
    )
    changed_offsets = {
        offset
        for offset, (before, after) in enumerate(zip(source_rom, actual_rom))
        if before != after
    }
    assert changed_offsets <= allowed_changes
