"""Regression tests for the FR status-badge graphics patch.

Focus: the Sleep badge must render the official French abbreviation « SOM »
(Sommeil), not the older « DOR ». Verified at the pixel level by decompressing
the built ROM's badge block and comparing slot 2's content tiles to the tiles
the patch generates for S-O-M.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.patch_font_fr import lz77_decompress
from scripts.patch_status_badges_fr import (
    BADGE_BLOCKS,
    _LETTERS,
    _STATUS_PATCHES,
    _TILE_BYTES,
    _TILES_PER_BADGE,
    _CONTENT1_IDX,
    _CONTENT2_IDX,
    _make_3letter_tiles,
    _read_slot_bg,
)

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"

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


@pytest.mark.rom
class TestBuiltFrBadge(unittest.TestCase):
    """The shipped FR ROM's sleep badge must contain the S-O-M tiles."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        cls.rom = bytearray(BUILT_FR_ROM.read_bytes())

    def test_sleep_badge_renders_som(self):
        result = lz77_decompress(self.rom, BADGE_BLOCKS[0])
        self.assertIsNotNone(result)
        tiles = bytearray(result[0])

        bg = _read_slot_bg(tiles, SLEEP_SLOT)
        expected_t1, expected_t2 = _make_3letter_tiles(
            _LETTERS["S"], _LETTERS["O"], _LETTERS["M"], bg
        )

        base = SLEEP_SLOT * _TILES_PER_BADGE * _TILE_BYTES
        c1 = base + _CONTENT1_IDX * _TILE_BYTES
        c2 = base + _CONTENT2_IDX * _TILE_BYTES
        self.assertEqual(bytes(tiles[c1 : c1 + _TILE_BYTES]), expected_t1)
        self.assertEqual(bytes(tiles[c2 : c2 + _TILE_BYTES]), expected_t2)


if __name__ == "__main__":
    unittest.main()
