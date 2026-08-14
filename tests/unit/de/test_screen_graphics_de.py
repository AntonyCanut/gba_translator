"""Gardes des assets allemands de l'écran titre et de la Carte Dresseur."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

from languages.de.patches import screen_graphics
from languages.de.tools import build_screen_assets as asset_builder
from languages.de.sprites import SPRITES
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_mapped_block
from src.graphics.sprite_rom import resolve_live_offset

ROOT = Path(__file__).resolve().parents[3]
INPUT_ROM = ROOT / "input/roms/englishrom.gba"
ASSET_DIR = ROOT / "languages/de/sprites"
LABEL_REGIONS = {
    "title_screen": (64, 145, 192, 158),
    "trainer_card_front": (17, 4, 145, 18),
    "trainer_card_back": (17, 4, 130, 18),
}


def test_german_screen_sprite_registry_exists() -> None:
    """Le flux DE doit déclarer son propre registre de sprites éditables."""
    assert importlib.util.find_spec("languages.de.sprites") is not None


def test_german_registry_describes_exact_live_resources() -> None:
    """Les offsets DE doivent rester ceux des ressources anglaises vivantes."""
    front = SPRITES["trainer_card_front"]
    back = SPRITES["trainer_card_back"]
    title = SPRITES["title_screen"]

    assert front.blocks == (0x01FDA2BC,)
    assert front.tilemaps == (0x01FDA820,)
    assert front.block_pointers == ((0x01ED8AA4,),)
    assert front.tilemap_pointers == ((0x01ED8AA8,),)
    assert back.blocks == (0x01FDAA4C,)
    assert back.tilemaps == (0x01FDB2AC,)
    assert back.tilemap_pointers == ((0x01ED8AB8,),)
    assert title.blocks == (0x01FD4854,)
    assert title.tilemaps == (0x01FD6514,)
    assert title.block_pointers == ((0x01ED7C7C, 0x01ED7EC0),)
    assert title.tilemap_pointers == ((0x01ED7C84, 0x01ED7EC8),)
    assert title.palette == 0x01FD699C
    assert title.bits_per_pixel == 8
    assert {
        (sprite.tiles_wide, sprite.tiles_tall)
        for sprite in SPRITES.values()
    } == {(32, 20)}


def test_german_screen_asset_generator_exists() -> None:
    """Les sources doivent être régénérables sans retouche manuelle opaque."""
    assert (ROOT / "languages/de/tools/build_screen_assets.py").is_file()


def test_german_screen_labels_are_explicit_and_language_only() -> None:
    """Les seuls contenus dessinés doivent être les trois libellés allemands."""
    assert getattr(asset_builder, "LABELS", None) == {
        "title_screen": "START DRÜCKEN",
        "trainer_card_front": "TRAINERPASS",
        "trainer_card_back": "LIGA-ORDEN",
    }


def _source_grid(name: str) -> list[list[int]]:
    sprite = SPRITES[name]
    rom = INPUT_ROM.read_bytes()
    grid, _, _ = extract_mapped_block(
        rom,
        sprite.blocks[0],
        sprite.tilemaps[0],
        sprite.tiles_wide,
        sprite.tiles_tall,
        bits_per_pixel=sprite.bits_per_pixel,
    )
    return grid


def test_german_assets_are_reproducible_and_only_change_label_regions(
    tmp_path: Path,
) -> None:
    """Une régénération doit reproduire les sources sans altérer le décor."""
    build_assets = getattr(asset_builder, "build_assets", None)
    assert callable(build_assets)

    produced = build_assets(INPUT_ROM, tmp_path)

    assert {path.name for path in produced} == {
        f"{name}.{suffix}"
        for name in LABEL_REGIONS
        for suffix in ("png", "bmp")
    }
    for name, (x0, y0, x1, y1) in LABEL_REGIONS.items():
        png = tmp_path / f"{name}.png"
        bmp = tmp_path / f"{name}.bmp"
        expected_png = ASSET_DIR / png.name
        expected_bmp = ASSET_DIR / bmp.name
        assert png.read_bytes() == expected_png.read_bytes()
        assert bmp.read_bytes() == expected_bmp.read_bytes()

        width, height, actual = read_indexed_image(png)
        bmp_width, bmp_height, bmp_grid = read_indexed_image(bmp)
        source = _source_grid(name)
        assert (width, height) == (bmp_width, bmp_height) == (256, 160)
        assert actual == bmp_grid
        assert any(
            actual[y][x] != source[y][x]
            for y in range(y0, y1)
            for x in range(x0, x1)
        )
        assert all(
            actual[y][x] == source[y][x]
            for y in range(height)
            for x in range(width)
            if not (x0 <= x < x1 and y0 <= y < y1)
        )


def test_german_screen_graphics_patch_exists() -> None:
    """Le build générique doit disposer d'un patch DE dédié aux trois écrans."""
    assert (ROOT / "languages/de/patches/screen_graphics.py").is_file()


def test_german_screen_graphics_run_after_lz77_repairs() -> None:
    """Les réparations LZ77 ne doivent jamais écraser les libellés DE."""
    descriptor = (ROOT / "languages/de/lang.yaml").read_text(encoding="utf-8")
    repair = descriptor.index("  - repair_lz77")
    localized = descriptor.index("  - repair_localized_lz77")
    graphics = descriptor.index("  - screen_graphics")

    assert repair < graphics
    assert localized < graphics


def test_german_screen_graphics_patch_owns_only_de_assets() -> None:
    """Le patch ne doit référencer ni fichiers FR/IT ni noms de jeu traduits."""
    assert getattr(screen_graphics, "ASSET_NAMES", None) == tuple(LABEL_REGIONS)
    assert callable(getattr(screen_graphics, "apply_to_rom", None))
    source = (ROOT / "languages/de/patches/screen_graphics.py").read_text(
        encoding="utf-8"
    )
    assert "languages/fr" not in source
    assert "languages/it" not in source


def _live_grid(rom: bytes, name: str) -> list[list[int]]:
    sprite = SPRITES[name]
    tiles_offset = resolve_live_offset(
        rom,
        sprite.blocks[0],
        sprite.block_pointers[0] if sprite.block_pointers else (),
    )
    tilemap_offset = resolve_live_offset(
        rom,
        sprite.tilemaps[0],
        sprite.tilemap_pointers[0] if sprite.tilemap_pointers else (),
    )
    grid, _, _ = extract_mapped_block(
        rom,
        tiles_offset,
        tilemap_offset,
        sprite.tiles_wide,
        sprite.tiles_tall,
        bits_per_pixel=sprite.bits_per_pixel,
    )
    return grid


@pytest.mark.rom
def test_german_screen_graphics_patch_writes_all_three_live_screens(
    tmp_path: Path,
) -> None:
    """Chaque pointeur vivant de la ROM patchée doit rendre l'asset DE exact."""
    rom_path = tmp_path / "german-screen-graphics.gba"
    shutil.copy2(INPUT_ROM, rom_path)
    original = rom_path.read_bytes()

    patched = screen_graphics.apply_to_rom(rom_path)

    actual_rom = rom_path.read_bytes()
    assert patched == 3
    assert Path(f"{rom_path}.bak").read_bytes() == original
    for name in LABEL_REGIONS:
        sprite = SPRITES[name]
        assert resolve_live_offset(
            actual_rom,
            sprite.blocks[0],
            sprite.block_pointers[0] if sprite.block_pointers else (),
        ) == sprite.blocks[0]
        assert resolve_live_offset(
            actual_rom,
            sprite.tilemaps[0],
            sprite.tilemap_pointers[0] if sprite.tilemap_pointers else (),
        ) == sprite.tilemaps[0]
        _, _, expected = read_indexed_image(ASSET_DIR / f"{name}.png")
        assert _live_grid(actual_rom, name) == expected
