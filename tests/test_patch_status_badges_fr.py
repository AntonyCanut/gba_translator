"""Regression tests for the FR status-badge graphics patch.

The four LZ77 copies feed the battle and party/summary screens.  Every copy is
checked at pixel level so one UI cannot silently retain English or misaligned
letters while another looks correct.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.font import lz77_decompress
from languages.fr.patches.status_badges import (
    BADGE_BLOCKS,
    _LETTERS,
    _STATUS_PATCHES,
    _TILE_BYTES,
    _TILES_PER_BADGE,
    _CONTENT1_IDX,
    _CONTENT2_IDX,
    _FNT_SLOT,
    _make_3letter_tiles,
    _make_ko_tiles,
    _read_slot_bg,
    _read_slot_border,
)
from languages.fr.sprites import SPRITES
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_block

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"
EDITABLE_PNG = (
    Path(__file__).parent.parent
    / "languages"
    / "fr"
    / "sprites"
    / "status_badges.png"
)

SLEEP_SLOT = 2


class TestBadgePatchTable(unittest.TestCase):
    def test_sleep_slot_is_som(self):
        sleep = next(p for p in _STATUS_PATCHES if p[0] == SLEEP_SLOT)
        self.assertEqual(sleep, (SLEEP_SLOT, "S", "O", "M"))

    def test_no_dor_anywhere(self):
        # The old "DOR" rendering must not linger in the patch table.
        for slot, a, b, c in _STATUS_PATCHES:
            self.assertNotEqual((a, b, c), ("D", "O", "R"))

    def test_s_glyph_defined(self):
        self.assertIn("S", _LETTERS)
        self.assertEqual(len(_LETTERS["S"]), 6)          # 6 pixel rows
        for row in _LETTERS["S"]:
            self.assertEqual(len(row), 4)                # 4 pixel columns

    def test_sprite_reinsertion_uses_compact_lz77_stream(self):
        self.assertFalse(SPRITES["status_badges"].vram_safe)


@pytest.mark.rom
class TestBuiltFrBadge(unittest.TestCase):
    """Toutes les copies ROM doivent contenir les mêmes libellés FR fiables."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        cls.rom = bytearray(BUILT_FR_ROM.read_bytes())

    def test_all_french_badges_render_in_every_ui_block(self):
        for block in BADGE_BLOCKS:
            with self.subTest(block=f"0x{block:08X}"):
                result = lz77_decompress(self.rom, block)
                self.assertIsNotNone(result)
                tiles = bytearray(result[0])

                for slot, a, b, c in _STATUS_PATCHES:
                    bg = _read_slot_bg(tiles, slot)
                    border = _read_slot_border(tiles, slot)
                    expected = _make_3letter_tiles(
                        _LETTERS[a], _LETTERS[b], _LETTERS[c], bg, border
                    )
                    base = slot * _TILES_PER_BADGE * _TILE_BYTES
                    c1 = base + _CONTENT1_IDX * _TILE_BYTES
                    c2 = base + _CONTENT2_IDX * _TILE_BYTES
                    actual = (
                        bytes(tiles[c1 : c1 + _TILE_BYTES]),
                        bytes(tiles[c2 : c2 + _TILE_BYTES]),
                    )
                    self.assertEqual(actual, expected, f"slot {slot}: {a}{b}{c}")

                ko_expected = _make_ko_tiles(_read_slot_border(tiles, _FNT_SLOT))
                ko_base = _FNT_SLOT * _TILES_PER_BADGE * _TILE_BYTES
                ko_c1 = ko_base + _CONTENT1_IDX * _TILE_BYTES
                ko_c2 = ko_base + _CONTENT2_IDX * _TILE_BYTES
                self.assertEqual(
                    (
                        bytes(tiles[ko_c1 : ko_c1 + _TILE_BYTES]),
                        bytes(tiles[ko_c2 : ko_c2 + _TILE_BYTES]),
                    ),
                    ko_expected,
                )

    def test_content_tiles_use_each_blocks_own_border_colour(self):
        """Évite les pixels de couture dus à un indice 9 forcé sur les blocs 1."""
        patched_slots = [slot for slot, *_ in _STATUS_PATCHES] + [_FNT_SLOT]
        for block in BADGE_BLOCKS:
            result = lz77_decompress(self.rom, block)
            self.assertIsNotNone(result)
            tiles = result[0]
            for slot in patched_slots:
                base = slot * _TILES_PER_BADGE * _TILE_BYTES
                right_cap = base + 3 * _TILE_BYTES
                border = tiles[right_cap] & 0xF
                for content_idx in (_CONTENT1_IDX, _CONTENT2_IDX):
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

    def test_editable_png_matches_primary_rom_block(self):
        self.assertTrue(EDITABLE_PNG.exists())
        png_width, png_height, png_grid = read_indexed_image(EDITABLE_PNG)
        rom_grid, _, _ = extract_block(
            bytes(self.rom),
            BADGE_BLOCKS[0],
            tiles_wide=4,
            tiles_tall=8,
        )
        self.assertEqual((png_width, png_height), (32, 64))
        self.assertEqual(png_grid, rom_grid)


if __name__ == "__main__":
    unittest.main()
