"""Régressions du patch graphique des badges de statut FR."""

import hashlib
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.status_badges import (
    BADGE_BLOCKS,
    HEALTHBOX_STATUS_GROUPS as PATCHED_HEALTHBOX_STATUS_GROUPS,
    apply_patches,
)
from languages.fr.sprites import SPRITES
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_block, tiles_to_grid

ROOT = Path(__file__).parent.parent
BUILT_FR_ROM = ROOT / "output/roms/GenedRom-fr.gba"
SPRITE_DIR = ROOT / "languages/fr/sprites"
EDITABLE_BMP = SPRITE_DIR / "status_badges.bmp"
EDITABLE_PNG = SPRITE_DIR / "status_badges.png"
USER_BADGE_PIXEL_SHA256 = (
    "9ab29c8b025c697e84b864c64ed4f082f290b049bd7a047b1d2e146076ae8d41"
)
HEALTHBOX_STATUS_GROUPS = (
    (0x00D11E64, 0xC),  # battler 0
    (0x00D124A4, 0xD),  # battler 1 (adversaire gauche)
    (0x00D12684, 0xE),  # battler 2
    (0x00D12864, 0xF),  # battler 3 (adversaire droit)
)
RAW_TILES_PER_STATUS = 3
TILE_BYTES_4BPP = 32


def _normalized_badge_pixel_hash(grid: list[list[int]]) -> str:
    """Normalise les indices de bordure propres aux copies avant empreinte."""
    normalized = [row.copy() for row in grid]
    for slot in range(7):
        first_row = slot * 8
        border = normalized[first_row][24]
        for y in range(first_row, first_row + 8):
            normalized[y] = [9 if pixel == border else pixel for pixel in normalized[y]]
    pixels = bytes(pixel for row in normalized for pixel in row)
    return hashlib.sha256(pixels).hexdigest()


def _normalized_healthbox_status_grid(
    rom: bytes,
    group_offset: int,
    palette_index: int,
) -> list[list[int]]:
    """Rend les cinq badges bruts comme la fenêtre correspondante du BMP."""
    normalized: list[list[int]] = []
    for slot in range(5):
        offset = group_offset + slot * RAW_TILES_PER_STATUS * TILE_BYTES_4BPP
        grid = tiles_to_grid(
            rom[offset:offset + RAW_TILES_PER_STATUS * TILE_BYTES_4BPP],
            RAW_TILES_PER_STATUS,
            1,
        )
        canonical_fill = 4 + slot * 2
        for row in grid:
            normalized.append([
                9 if pixel == 7
                else 2 if pixel == 1
                else 0 if pixel == 2
                else canonical_fill if pixel == palette_index
                else pixel
                for pixel in row
            ])
    return normalized


class TestBadgeAsset(unittest.TestCase):
    def test_healthbox_groups_cover_every_battler(self):
        self.assertEqual(tuple(PATCHED_HEALTHBOX_STATUS_GROUPS), HEALTHBOX_STATUS_GROUPS)

    def test_sprite_reinsertion_uses_compact_lz77_stream(self):
        self.assertFalse(SPRITES["status_badges"].vram_safe)

    def test_bmp_and_png_match_the_user_supplied_pixels(self):
        bmp_width, bmp_height, bmp_grid = read_indexed_image(EDITABLE_BMP)
        png_width, png_height, png_grid = read_indexed_image(EDITABLE_PNG)

        self.assertEqual((bmp_width, bmp_height), (32, 64))
        self.assertEqual((png_width, png_height), (32, 64))
        self.assertEqual(png_grid, bmp_grid)
        self.assertEqual(_normalized_badge_pixel_hash(bmp_grid), USER_BADGE_PIXEL_SHA256)


@pytest.mark.rom
class TestBuiltFrBadge(unittest.TestCase):
    """Toutes les copies ROM doivent reproduire le BMP fourni."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        cls.rom = BUILT_FR_ROM.read_bytes()

    def test_built_rom_matches_user_pixels_in_every_ui_block(self):
        for block in BADGE_BLOCKS:
            grid, _, _ = extract_block(self.rom, block, tiles_wide=4, tiles_tall=8)
            self.assertEqual(
                _normalized_badge_pixel_hash(grid),
                USER_BADGE_PIXEL_SHA256,
                f"0x{block:08X}",
            )

    def test_battle_healthbox_statuses_match_user_pixels_for_every_battler(self):
        """Les deux adversaires doivent charger POI/PAR/SOM/GEL/BRU, pas BRN."""
        _, _, bmp_grid = read_indexed_image(EDITABLE_BMP)
        expected = [row[7:31] for row in bmp_grid[:40]]

        for group_offset, palette_index in HEALTHBOX_STATUS_GROUPS:
            self.assertEqual(
                _normalized_healthbox_status_grid(
                    self.rom,
                    group_offset,
                    palette_index,
                ),
                expected,
                f"healthbox status group 0x{group_offset:08X}",
            )


@pytest.mark.rom
def test_user_bmp_is_applied_identically_to_every_ui_block(tmp_path: Path):
    """Le patch doit reproduire le dessin fourni dans combat et menus Pokémon."""
    if not BUILT_FR_ROM.exists():
        pytest.skip("GenedRom-fr.gba not built")
    rom_path = tmp_path / "status-badges.gba"
    rom_path.write_bytes(BUILT_FR_ROM.read_bytes())
    before = rom_path.read_bytes()
    caps = {
        (group_offset, slot): before[
            group_offset + (slot * RAW_TILES_PER_STATUS + 2) * TILE_BYTES_4BPP:
            group_offset + (slot * RAW_TILES_PER_STATUS + 3) * TILE_BYTES_4BPP
        ]
        for group_offset, _ in HEALTHBOX_STATUS_GROUPS
        for slot in range(5)
    }

    patched = apply_patches(rom_path)

    assert patched == len(BADGE_BLOCKS) + len(HEALTHBOX_STATUS_GROUPS)
    rom = rom_path.read_bytes()
    for block in BADGE_BLOCKS:
        grid, _, _ = extract_block(rom, block, tiles_wide=4, tiles_tall=8)
        assert _normalized_badge_pixel_hash(grid) == USER_BADGE_PIXEL_SHA256
    _, _, bmp_grid = read_indexed_image(EDITABLE_BMP)
    expected = [row[7:31] for row in bmp_grid[:40]]
    for group_offset, palette_index in HEALTHBOX_STATUS_GROUPS:
        assert _normalized_healthbox_status_grid(
            rom,
            group_offset,
            palette_index,
        ) == expected
        for slot in range(5):
            cap_offset = (
                group_offset
                + (slot * RAW_TILES_PER_STATUS + 2) * TILE_BYTES_4BPP
            )
            assert rom[cap_offset:cap_offset + TILE_BYTES_4BPP] == caps[
                (group_offset, slot)
            ]


if __name__ == "__main__":
    unittest.main()
