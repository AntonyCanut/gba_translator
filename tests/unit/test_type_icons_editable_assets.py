"""Gardes des planches d’icônes de types éditables."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from languages.fr.sprites import SPRITES
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_block

ROOT = Path(__file__).resolve().parents[2]
SPRITES_DIR = ROOT / "languages" / "fr" / "sprites"


def test_type_icons_registry_exposes_both_raw_sheets() -> None:
    # Arrange
    expected = {
        "type_icons_summary": ((0x00B1EC64,), 19),
        "type_icons_battle": ((0x00961A00,), 13),
    }

    # Act
    sprites = {name: SPRITES[name] for name in expected}

    # Assert
    for name, (blocks, tiles_tall) in expected.items():
        assert sprites[name].blocks == blocks
        assert (sprites[name].tiles_wide, sprites[name].tiles_tall) == (16, tiles_tall)
        assert sprites[name].compressed is False


def test_type_icon_assets_are_distinct_indexed_sheets() -> None:
    # Arrange
    expected_heights = {
        "type_icons_summary": 152,
        "type_icons_battle": 104,
    }

    # Act
    sheets = {
        name: read_indexed_image(SPRITES_DIR / f"{name}.png")
        for name in expected_heights
    }

    # Assert
    for name, (width, height, grid) in sheets.items():
        assert (width, height) == (128, expected_heights[name])
        assert all(0 <= pixel <= 15 for row in grid for pixel in row)
        assert any(pixel == 14 for row in grid for pixel in row)
        assert any(pixel == 15 for row in grid for pixel in row)
    assert sheets["type_icons_summary"][2][:104] != sheets["type_icons_battle"][2]


@pytest.mark.parametrize("name", ["type_icons_summary", "type_icons_battle"])
def test_type_icon_asset_reinserts_its_sheet(tmp_path: Path, name: str) -> None:
    # Arrange
    sprite = SPRITES[name]
    sheet_bytes = sprite.tiles_wide * sprite.tiles_tall * 32
    rom_path = tmp_path / "type-icons.gba"
    rom_path.write_bytes(bytes(sprite.blocks[0] + sheet_bytes))
    asset = SPRITES_DIR / f"{name}.png"

    # Act
    result = subprocess.run(
        [
            "python3",
            "scripts/insert_sprite.py",
            "--rom",
            str(rom_path),
            "--lang",
            "fr",
            "--sprite",
            name,
            "--image",
            str(asset),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Assert
    assert result.returncode == 0, result.stderr
    rom = rom_path.read_bytes()
    expected = read_indexed_image(asset)[2]
    actual, _, _ = extract_block(
        rom,
        sprite.blocks[0],
        sprite.tiles_wide,
        sprite.tiles_tall,
        compressed=False,
    )
    assert actual == expected
    assert Path(f"{rom_path}.bak").read_bytes() == bytes(len(rom))
