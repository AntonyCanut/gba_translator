"""Régressions des assets graphiques DE hors combat (F-605)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from languages.de.patches.menu_sprites import PATCHES
from languages.de.sprites import SPRITES
from src.graphics.sprite_image import read_indexed_image, variant_path
from src.graphics.sprite_rom import extract_block, resolve_live_offset
from src.i18n import load_registry

ROOT = Path(__file__).resolve().parents[3]
ASSET_DIR = ROOT / "languages/de/sprites"
SOURCE_ROM = ROOT / "input/roms/englishrom.gba"
BUILT_ROM = ROOT / "output/roms/GenedRom-de.gba"

EXPECTED_ASSETS = {
    "cube_sort_hint": (104, 32),
    "pc_box_labels": (128, 72),
    "pokemon_mart_sign": (16, 8),
    "selection": (40, 104),
    "start_menu_move_hint": (120, 8),
}


def _image_for(name: str, block_index: int) -> Path:
    base = ASSET_DIR / f"{name}.png"
    return variant_path(base, block_index) if name == "pokemon_mart_sign" else base


def test_german_registry_exposes_every_requested_menu_asset() -> None:
    """Une omission du registre doit rendre l'asset impossible à injecter."""
    assert set(SPRITES) == set(EXPECTED_ASSETS)
    assert {patch.sprite for patch in PATCHES} == set(EXPECTED_ASSETS)
    assert len([patch for patch in PATCHES if patch.sprite == "pokemon_mart_sign"]) == 3


@pytest.mark.parametrize(("name", "dimensions"), EXPECTED_ASSETS.items())
def test_german_assets_are_indexed_and_keep_the_declared_geometry(
    name: str,
    dimensions: tuple[int, int],
) -> None:
    """Un export RGB ou redimensionné détruirait les indices de palette GBA."""
    sprite = SPRITES[name]
    indices = range(len(sprite.blocks)) if name == "pokemon_mart_sign" else (0,)

    for block_index in indices:
        width, height, pixels = read_indexed_image(_image_for(name, block_index))

        assert (width, height) == dimensions
        assert (width, height) == (sprite.tiles_wide * 8, sprite.tiles_tall * 8)
        assert max(pixel for row in pixels for pixel in row) < 16


@pytest.mark.parametrize("name", EXPECTED_ASSETS)
def test_german_assets_do_not_keep_french_only_pixel_grid(name: str) -> None:
    """Les labels FR doivent disparaître ; le « SHOP » commun peut rester identique."""
    de_paths = (
        [_image_for(name, index) for index in range(3)]
        if name == "pokemon_mart_sign"
        else [_image_for(name, 0)]
    )
    if name == "pokemon_mart_sign":
        fr_candidates = [
            ROOT / "languages/fr/sprites/pokemon_mart_sign_classic.png",
        ]
    else:
        fr_candidates = [
            ROOT / "languages/fr/sprites" / f"{name}.png",
            ROOT / "languages/fr/sprites" / f"{name}.bmp",
        ]

    for de_path in de_paths:
        _, _, de_pixels = read_indexed_image(de_path)
        assert all(
            not candidate.exists()
            or read_indexed_image(candidate)[2] != de_pixels
            for candidate in fr_candidates
        )


def test_menu_sprites_run_after_both_lz77_repairs() -> None:
    """Déplacer l'étape avant une réparation réintroduirait l'art anglais."""
    patches = load_registry().get("de").patches

    assert patches.index("menu_sprites") > patches.index("repair_lz77")
    assert patches.index("menu_sprites") > patches.index("repair_localized_lz77")


@pytest.mark.rom
def test_menu_sprite_patch_is_byte_idempotent(tmp_path: Path) -> None:
    """Un second passage du patch ne doit plus modifier aucun octet."""
    if not SOURCE_ROM.exists():
        pytest.skip("ROM source absente")
    target = tmp_path / "de-menu-assets.gba"
    shutil.copy2(SOURCE_ROM, target)
    command = [
        sys.executable,
        str(ROOT / "languages/de/patches/menu_sprites.py"),
        "--rom",
        str(target),
    ]

    subprocess.run(command, cwd=ROOT, check=True)
    first = target.read_bytes()
    subprocess.run(command, cwd=ROOT, check=True)

    assert target.read_bytes() == first


@pytest.mark.rom
def test_built_german_rom_contains_every_versioned_menu_asset() -> None:
    """Le build final doit contenir les pixels versionnés, pas l'art anglais réparé."""
    if not BUILT_ROM.exists():
        pytest.skip("ROM DE non construite")
    rom = BUILT_ROM.read_bytes()

    for patch in PATCHES:
        sprite = SPRITES[patch.sprite]
        index = patch.block_index
        offset = resolve_live_offset(
            rom,
            sprite.blocks[index],
            sprite.block_pointers[index] if sprite.block_pointers else (),
        )
        actual, _, _ = extract_block(
            rom,
            offset,
            sprite.tiles_wide,
            sprite.tiles_tall,
            compressed=sprite.compressed,
            bits_per_pixel=sprite.bits_per_pixel,
            start_tile=sprite.start_tiles[index] if sprite.start_tiles else 0,
        )
        _, _, expected = read_indexed_image(patch.image)

        assert actual == expected, patch.sprite
