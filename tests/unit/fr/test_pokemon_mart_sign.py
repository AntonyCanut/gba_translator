"""Gardes de l’enseigne extérieure « SHOP » des Boutiques Pokémon."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from languages.fr.sprites import SPRITES, SpriteDef
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_block

ROOT = Path(__file__).resolve().parents[3]
ASSET = ROOT / "languages" / "fr" / "sprites" / "pokemon_mart_sign.png"
BUILT_ROM = ROOT / "output" / "roms" / "GenedRom-fr.gba"
EXPECTED_INK = (
    ".###.#.#.###.##.",
    ".#...#.#.#.#.#.#",
    ".###.###.#.#.##.",
    "...#.#.#.#.#.#..",
    ".###.#.#.###.#..",
)


def test_pokemon_mart_sign_registry_targets_live_tileset() -> None:
    sprite = SPRITES["pokemon_mart_sign"]

    assert sprite.blocks == (0x00CF91A0,)
    assert sprite.start_tiles == (413,)
    assert sprite.max_compressed_sizes == (11_604,)
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


def test_pokemon_mart_sign_asset_spells_shop() -> None:
    width, height, grid = read_indexed_image(ASSET)

    assert (width, height) == (16, 8)
    actual_ink = tuple(
        "".join("#" if pixel >= 0xA else "." for pixel in row)
        for row in grid[2:7]
    )
    assert actual_ink == EXPECTED_INK


def test_french_build_inserts_shop_sign_after_graphics_repairs() -> None:
    result = subprocess.run(
        ["make", "-n", "build-fr"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    command = (
        "scripts/insert_sprite.py --rom output/roms/GenedRom-fr.gba "
        "--lang fr --sprite pokemon_mart_sign "
        "--image languages/fr/sprites/pokemon_mart_sign.png"
    )
    assert command in result.stdout
    assert result.stdout.index("repair_localized_lz77_blocks.py") < result.stdout.index(command)


@pytest.mark.rom
def test_built_french_rom_contains_shop_sign() -> None:
    sprite = SPRITES["pokemon_mart_sign"]
    _, _, expected = read_indexed_image(ASSET)

    actual, decompressed_len, compressed_len = extract_block(
        BUILT_ROM.read_bytes(),
        sprite.blocks[0],
        sprite.tiles_wide,
        sprite.tiles_tall,
        compressed=sprite.compressed,
        start_tile=sprite.start_tiles[0],
    )

    assert decompressed_len == 20_480
    assert compressed_len <= 11_604
    assert actual == expected
