"""Régressions des sources raster DE des écrans combat et résumé."""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path

import pytest

from languages.de.patches import (
    hp_labels,
    status_badges,
    summary_stat_labels,
    type_icons,
)
from languages.de.patches.battle_summary_sprites import apply_to_rom
from languages.de.sprites import SPRITES
from src.graphics.sprite_image import read_indexed_image, variant_path
from src.graphics.sprite_rom import extract_block, resolve_live_offset
from src.i18n import load_registry

ROOT = Path(__file__).resolve().parents[3]
ASSET_DIR = ROOT / "languages" / "de" / "sprites"
BUILT_ROM = ROOT / "output" / "roms" / "GenedRom-de.gba"
SOURCE_ROM = ROOT / "input" / "roms" / "englishrom.gba"

EXPECTED_SPRITES = {
    "status_badges": (32, 64, 4),
    "battle_status_badges": (24, 40, 4),
    "type_icons_summary": (128, 152, 1),
    "type_icons_battle": (128, 104, 1),
    "party_kp_label": (64, 80, 1),
    "summary_kp_bar": (96, 8, 1),
    "summary_stat_labels": (128, 256, 1),
    "battle_kp_labels": (16, 8, 4),
    "battle_kp_elements": (8, 8, 2),
    "level_marker": (8, 8, 1),
}


def _asset_path(name: str, suffix: str, index: int) -> Path:
    base = ASSET_DIR / f"{name}{suffix}"
    return variant_path(base, index) if EXPECTED_SPRITES[name][2] > 1 else base


def test_registry_declares_every_battle_and_summary_sprite() -> None:
    assert set(EXPECTED_SPRITES) <= set(SPRITES)
    for name, (width, height, copies) in EXPECTED_SPRITES.items():
        sprite = SPRITES[name]
        assert (sprite.tiles_wide * 8, sprite.tiles_tall * 8) == (width, height)
        assert len(sprite.blocks) == copies


@pytest.mark.parametrize("name", EXPECTED_SPRITES)
def test_png_and_bmp_sources_are_indexed_and_pixel_identical(name: str) -> None:
    width, height, copies = EXPECTED_SPRITES[name]
    for index in range(copies):
        png = read_indexed_image(_asset_path(name, ".png", index))
        bmp = read_indexed_image(_asset_path(name, ".bmp", index))
        assert png == bmp
        assert png[:2] == (width, height)
        assert max(pixel for row in png[2] for pixel in row) < 16


def test_divergent_type_copies_have_distinct_complete_sheets() -> None:
    summary = read_indexed_image(ASSET_DIR / "type_icons_summary.png")
    battle = read_indexed_image(ASSET_DIR / "type_icons_battle.png")
    assert summary[:2] != battle[:2]
    assert summary[2][:104] != battle[2]


def test_summary_word_images_replace_every_language_dependent_english_label() -> None:
    if not SOURCE_ROM.exists():
        pytest.skip("englishrom.gba absente")
    english, _decompressed, _compressed = extract_block(
        SOURCE_ROM.read_bytes(), 0x00E9A460, 16, 32
    )
    german = read_indexed_image(ASSET_DIR / "summary_stat_labels.png")[2]

    def changed(xs: range, ys: range) -> int:
        return sum(
            german[y][x] != english[y][x]
            for y in ys
            for x in xs
        )

    for english_label, y0 in (("No", 56), ("TYPE", 80), ("IDNo", 104)):
        assert changed(range(32), range(y0, y0 + 12)) > 0, english_label
    for shared_label, y0 in (("NAME", 68), ("OT", 92), ("ITEM", 116)):
        assert changed(range(32), range(y0, y0 + 12)) == 0, shared_label
    assert changed(range(96, 128), range(56, 112)) > 0, "POWER / ACCURACY"


def test_patch_covers_every_declared_copy_once() -> None:
    module = importlib.import_module("languages.de.patches.battle_summary_sprites")
    expected = {
        (name, index)
        for name, (_width, _height, copies) in EXPECTED_SPRITES.items()
        for index in range(copies)
    }
    assert {(patch.sprite, patch.block_index) for patch in module.PATCHES} == expected


def test_patch_runs_after_repairs_and_graphic_generators() -> None:
    patches = load_registry().get("de").patches
    final = patches.index("battle_summary_sprites")
    for prerequisite in (
        "repair_lz77",
        "repair_localized_lz77",
        "font",
        "status_badges",
        "type_icons",
        "hp_labels",
        "summary_stat_labels",
    ):
        assert final > patches.index(prerequisite)


def _assert_rom_matches_assets(rom: bytes) -> None:
    for name, (_width, _height, copies) in EXPECTED_SPRITES.items():
        sprite = SPRITES[name]
        for index in range(copies):
            offset = resolve_live_offset(
                rom,
                sprite.blocks[index],
                sprite.block_pointers[index] if sprite.block_pointers else (),
            )
            actual, _decompressed, _compressed = extract_block(
                rom,
                offset,
                sprite.tiles_wide,
                sprite.tiles_tall,
                compressed=sprite.compressed,
                bits_per_pixel=sprite.bits_per_pixel,
                start_tile=sprite.start_tiles[index] if sprite.start_tiles else 0,
            )
            expected = read_indexed_image(_asset_path(name, ".png", index))[2]
            assert actual == expected, f"{name}[{index}]"


@pytest.mark.rom
def test_versioned_assets_match_the_deterministic_generators(tmp_path: Path) -> None:
    if not SOURCE_ROM.exists():
        pytest.skip("englishrom.gba absente")
    generated = tmp_path / "generated-de-graphics.gba"
    shutil.copy2(SOURCE_ROM, generated)

    assert status_badges.apply_patches(generated) == 8
    assert type_icons.apply_patches(generated) == 34
    # 9 graphics/raw healthbox surfaces + 2 fixed CFRU text cells.
    assert hp_labels.apply_patches(generated) == 11
    assert summary_stat_labels.apply_patches(generated) == 11

    _assert_rom_matches_assets(generated.read_bytes())


@pytest.mark.rom
def test_raster_reinjection_is_byte_idempotent(tmp_path: Path) -> None:
    if not SOURCE_ROM.exists():
        pytest.skip("englishrom.gba absente")
    target = tmp_path / "de-assets.gba"
    shutil.copy2(SOURCE_ROM, target)

    assert apply_to_rom(target) == 20
    first = target.read_bytes()
    assert apply_to_rom(target) == 20

    assert target.read_bytes() == first
    _assert_rom_matches_assets(first)


@pytest.mark.rom
def test_built_rom_matches_every_versioned_tile_window() -> None:
    if not BUILT_ROM.exists():
        pytest.skip("GenedRom-de.gba non construite")
    _assert_rom_matches_assets(BUILT_ROM.read_bytes())
