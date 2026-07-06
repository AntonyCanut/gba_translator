"""Regression tests for the FR START-menu reorder-hint graphic patch (issue #43).

The hint bar « SELECT Move » is a baked LZ77 graphic (offset 0x0B1BBE0, tiles
12-14 = the word « Move »).  The patch redraws those three tiles to « Dépl. ».
We verify the patch is self-consistent (idempotent, recompresses within the
original slot) and that the shipped FR ROM actually carries the French tiles.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.font import lz77_decompress
from languages.fr.patches.start_menu_move_hint import (
    GFX_OFFSET,
    _FIRST_MOVE_TILE,
    _N_MOVE_TILES,
    _TILE_BYTES,
    _compose_tiles,
    apply_patch,
)

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"
EN_ROM = Path(__file__).parent.parent / "input" / "roms" / "englishrom.gba"


def _move_tiles(rom: bytearray) -> list[bytes]:
    dec, _ = lz77_decompress(rom, GFX_OFFSET)
    tiles = bytearray(dec)
    return [
        bytes(tiles[(_FIRST_MOVE_TILE + i) * _TILE_BYTES:
                    (_FIRST_MOVE_TILE + i + 1) * _TILE_BYTES])
        for i in range(_N_MOVE_TILES)
    ]


class TestComposedTiles(unittest.TestCase):
    def test_compose_returns_three_full_tiles(self):
        tiles = _compose_tiles(b"\x00" * 32)
        self.assertEqual(len(tiles), _N_MOVE_TILES)
        for t in tiles:
            self.assertEqual(len(t), _TILE_BYTES)

    def test_deplacer_differs_from_english_move(self):
        if not EN_ROM.exists():
            self.skipTest("englishrom.gba missing")
        rom = bytearray(EN_ROM.read_bytes())
        en_move = _move_tiles(rom)
        fr_depl = _compose_tiles(b"\x00" * 32)
        # The redraw must change the pixels (Move != Dépl.)
        self.assertNotEqual(en_move, fr_depl)


@pytest.mark.rom
class TestApplyIdempotentAndFits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not EN_ROM.exists():
            pytest.skip("englishrom.gba not available")

    def test_apply_is_idempotent_and_in_place(self):
        rom = bytearray(EN_ROM.read_bytes())
        pointer_before = bytes(rom[0xA0C210:0xA0C214])
        self.assertTrue(apply_patch(rom))
        after_first = _move_tiles(rom)
        # second application must reproduce identical tiles (idempotent)
        self.assertTrue(apply_patch(rom))
        after_second = _move_tiles(rom)
        self.assertEqual(after_first, after_second)
        # recompressed graphic fit in place → pointer unchanged
        self.assertEqual(bytes(rom[0xA0C210:0xA0C214]), pointer_before)
        # tiles now equal the composed « Dépl. » tiles
        self.assertEqual(after_second, _compose_tiles(b"\x00" * 32))


@pytest.mark.rom
class TestBuiltFrRom(unittest.TestCase):
    """The shipped FR ROM must carry the « Dépl. » hint tiles."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        cls.rom = bytearray(BUILT_FR_ROM.read_bytes())

    def test_hint_reads_deplacer(self):
        built = _move_tiles(self.rom)
        self.assertEqual(built, _compose_tiles(b"\x00" * 32))


if __name__ == "__main__":
    unittest.main()
