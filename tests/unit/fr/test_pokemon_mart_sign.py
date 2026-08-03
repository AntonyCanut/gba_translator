"""Gardes de l’enseigne extérieure « SHOP » des Boutiques Pokémon."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from languages.fr.sprites import SPRITES, SpriteDef
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_block

ROOT = Path(__file__).resolve().parents[3]
ASSET_DIR = ROOT / "languages" / "fr" / "sprites"
ASSET = ASSET_DIR / "pokemon_mart_sign.png"
USER_BMP = ASSET_DIR / "pokemon_mart_sign.bmp"
CLASSIC_ASSET = ASSET_DIR / "pokemon_mart_sign_classic.png"
BUILT_ROM = ROOT / "output" / "roms" / "GenedRom-fr.gba"
USER_BMP_SHA256 = (
    "93407be53e035fbebfa3659dfd9f8e96d3b594ece86c63830c2e76df4db76482"
)
EXPECTED_USER_GRID = (
    "0000000000000000",
    "3222222222222223",
    "2EE2E2E2EEE2EEE2",
    "2C22C2C2C2C2C2C2",
    "2CC2CCC2C2C2CCC2",
    "22C2C2C2C2C2C222",
    "2EE2E2E2EEE2E222",
    "3222222222222223",
)
EXPECTED_CLASSIC_GRID = (
    "3333333333333333",
    "1111111111111111",
    "1BB2B2B2BBB2BBB2",
    "1C22C2C2C2C2C2C2",
    "1DD2DDD2D2D2DDD2",
    "12E2E2E2E2E2E222",
    "1EE2E2E2EEE2E222",
    "1222222222222222",
)


def _hex_grid(path: Path) -> tuple[str, ...]:
    width, height, grid = read_indexed_image(path)

    assert (width, height) == (16, 8)
    return tuple("".join(f"{pixel:X}" for pixel in row) for row in grid)


def test_pokemon_mart_sign_registry_targets_live_tileset() -> None:
    sprite = SPRITES["pokemon_mart_sign"]

    assert sprite.blocks == (0x007559B8, 0x00B89D5C, 0x00CF91A0)
    assert sprite.start_tiles == (225, 225, 413)
    assert sprite.max_compressed_sizes == (10_452, 10_531, 11_604)
    assert sprite.palette == 0x00EA1BC8
    assert (sprite.tiles_wide, sprite.tiles_tall) == (2, 1)


def test_sprite_registry_pairs_each_block_with_its_slot_capacity() -> None:
    with pytest.raises(ValueError, match="one compressed size per block"):
        SpriteDef(
            blocks=(0x100, 0x200),
            tiles_wide=1,
            tiles_tall=1,
            max_compressed_sizes=(32,),
        )


def test_user_supplied_pokemon_mart_sign_bmp_is_versioned_exactly() -> None:
    assert hashlib.sha256(USER_BMP.read_bytes()).hexdigest() == USER_BMP_SHA256
    assert _hex_grid(USER_BMP) == EXPECTED_USER_GRID


def test_editable_png_matches_user_supplied_bmp_indices() -> None:
    assert _hex_grid(ASSET) == EXPECTED_USER_GRID


def test_classic_tileset_asset_preserves_its_native_frame_and_gradient() -> None:
    assert _hex_grid(CLASSIC_ASSET) == EXPECTED_CLASSIC_GRID


def test_french_build_inserts_shop_sign_after_graphics_repairs() -> None:
    result = subprocess.run(
        ["make", "-n", "build-fr"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    classic_command = (
        "scripts/insert_sprite.py --rom output/roms/GenedRom-fr.gba "
        "--lang fr --sprite pokemon_mart_sign "
        "--image languages/fr/sprites/pokemon_mart_sign_classic.png"
    )
    supplied_command = (
        "scripts/insert_sprite.py --rom output/roms/GenedRom-fr.gba "
        "--lang fr --sprite pokemon_mart_sign --block-index 2 "
        "--image languages/fr/sprites/pokemon_mart_sign.bmp"
    )
    assert result.stdout.count(classic_command) == 2
    assert f"{classic_command} --block-index 0" in result.stdout
    assert f"{classic_command} --block-index 1" in result.stdout
    assert supplied_command in result.stdout
    assert result.stdout.index("repair_localized_lz77_blocks.py") < result.stdout.index(
        classic_command
    )


@pytest.mark.rom
def test_built_french_rom_contains_shop_sign_in_every_tileset_copy() -> None:
    sprite = SPRITES["pokemon_mart_sign"]
    rom = BUILT_ROM.read_bytes()
    expected_assets = (CLASSIC_ASSET, CLASSIC_ASSET, USER_BMP)

    for index, expected_asset in enumerate(expected_assets):
        _, _, expected = read_indexed_image(expected_asset)
        actual, decompressed_len, compressed_len = extract_block(
            rom,
            sprite.blocks[index],
            sprite.tiles_wide,
            sprite.tiles_tall,
            compressed=sprite.compressed,
            start_tile=sprite.start_tiles[index],
        )

        assert decompressed_len == 20_480
        assert compressed_len <= sprite.max_compressed_sizes[index]
        assert actual == expected
