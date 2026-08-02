"""Régressions du patch graphique des badges de statut FR."""

import hashlib
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.font import lz77_decompress
from languages.fr.patches.status_badges import (
    BADGE_BLOCKS,
    _TILE_BYTES,
    _TILES_PER_BADGE,
    apply_patches,
)
from languages.fr.sprites import SPRITES
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_block

ROOT = Path(__file__).parent.parent
BUILT_FR_ROM = ROOT / "output/roms/GenedRom-fr.gba"
SPRITE_DIR = ROOT / "languages/fr/sprites"
EDITABLE_BMP = SPRITE_DIR / "status_badges.bmp"
EDITABLE_PNG = SPRITE_DIR / "status_badges.png"
USER_BADGE_PIXEL_SHA256 = (
    "9ab29c8b025c697e84b864c64ed4f082f290b049bd7a047b1d2e146076ae8d41"
)


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


class TestBadgeAsset(unittest.TestCase):
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
    """Toutes les copies ROM doivent conserver leur propre indice de bordure."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        cls.rom = bytearray(BUILT_FR_ROM.read_bytes())

    def test_content_tiles_use_each_blocks_own_border_colour(self):
        for block in BADGE_BLOCKS:
            result = lz77_decompress(self.rom, block)
            self.assertIsNotNone(result)
            tiles = result[0]
            for slot in range(7):
                base = slot * _TILES_PER_BADGE * _TILE_BYTES
                right_cap = base + 3 * _TILE_BYTES
                border = tiles[right_cap] & 0xF
                for content_idx in (1, 2):
                    content = base + content_idx * _TILE_BYTES
                    top = tiles[content : content + 4]
                    bottom = tiles[content + 28 : content + 32]
                    expected = bytes([border | (border << 4)]) * 4
                    self.assertEqual(
                        top,
                        expected,
                        f"0x{block:08X} slot {slot} top border",
                    )
                    self.assertEqual(
                        bottom,
                        expected,
                        f"0x{block:08X} slot {slot} bottom border",
                    )


@pytest.mark.rom
def test_user_bmp_is_applied_identically_to_every_ui_block(tmp_path: Path):
    """Le patch doit reproduire le dessin fourni dans combat et menus Pokémon."""
    if not BUILT_FR_ROM.exists():
        pytest.skip("GenedRom-fr.gba not built")
    rom_path = tmp_path / "status-badges.gba"
    rom_path.write_bytes(BUILT_FR_ROM.read_bytes())

    patched = apply_patches(rom_path)

    assert patched == len(BADGE_BLOCKS)
    rom = rom_path.read_bytes()
    for block in BADGE_BLOCKS:
        grid, _, _ = extract_block(rom, block, tiles_wide=4, tiles_tall=8)
        assert _normalized_badge_pixel_hash(grid) == USER_BADGE_PIXEL_SHA256


if __name__ == "__main__":
    unittest.main()
