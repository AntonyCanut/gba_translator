"""Regression tests for the DE HP-label graphics patch (HP/PS → KP).

Sibling of tests/test_patch_hp_labels_fr.py — same three LZ77 label blocks, but
German draws « KP » (Kraftpunkte) instead of the French « PV ». All three labels
(party-menu green label, summary-screen green bar-label sprite, summary-screen
grey stat label) are 4bpp tiles inside LZ77 blocks — never handled by the text
pipeline. The built DE ROM must render « KP » in all three.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.font import lz77_decompress
from languages.de.patches.hp_labels import (
    GREEN_BLOCK,
    GREEN_KP_FILL,
    GREEN_OLD_VARIANTS,
    GREY_BLOCK,
    GREY_KP_FILL,
    GREY_OLD_TILES,
    PARTY_BLOCK,
    PARTY_KP_FILL,
    PARTY_NCOLS,
    PARTY_OLD_TILES,
    _draw_green_label,
    _draw_grey_label,
    _draw_party_label,
    _expected_new,
    _tiles_hex,
)

BUILT_DE_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-de.gba"


class TestKpArtDefinitions(unittest.TestCase):
    def test_party_fill_stays_inside_label_area(self):
        for r, c in PARTY_KP_FILL:
            self.assertTrue(0 <= r < 6, f"row {r} outside 6-row label")
            # outline needs one free column on each side of the fill
            self.assertTrue(1 <= c < PARTY_NCOLS - 1, f"col {c} would clip outline")

    def test_green_fill_stays_inside_sprite(self):
        for r, c in GREEN_KP_FILL:
            self.assertTrue(1 <= r <= 5, f"row {r} outside 5-row letters")
            self.assertTrue(1 <= c <= 14, f"col {c} would clip outline")

    def test_grey_fill_stays_inside_oval(self):
        for r, c in GREY_KP_FILL:
            self.assertTrue(3 <= r <= 9, f"row {r} outside letter rows")
            self.assertTrue(3 <= c <= 13, f"col {c} outside oval interior")

    def test_new_art_differs_from_old(self):
        self.assertNotEqual(_expected_new(PARTY_OLD_TILES, _draw_party_label),
                            PARTY_OLD_TILES)
        self.assertNotEqual(_expected_new(GREY_OLD_TILES, _draw_grey_label),
                            GREY_OLD_TILES)
        for variant in GREEN_OLD_VARIANTS.values():
            self.assertNotEqual(_expected_new(variant, _draw_green_label), variant)

    def test_de_kp_differs_from_fr_pv(self):
        # The DE label must be distinct from the FR « PV » drawn from the same
        # source tiles — otherwise the port drew the wrong letters.
        from languages.fr.patches.hp_labels import (
            _draw_party_label as fr_party,
            _draw_green_label as fr_green,
            _draw_grey_label as fr_grey,
        )
        self.assertNotEqual(_expected_new(PARTY_OLD_TILES, _draw_party_label),
                            _expected_new(PARTY_OLD_TILES, fr_party))
        self.assertNotEqual(_expected_new(GREY_OLD_TILES, _draw_grey_label),
                            _expected_new(GREY_OLD_TILES, fr_grey))
        es = GREEN_OLD_VARIANTS["ES « PS »"]
        self.assertNotEqual(_expected_new(es, _draw_green_label),
                            _expected_new(es, fr_green))

    def test_green_variants_converge_to_same_kp(self):
        # Whether the source block held EN « HP » or ES « PS », the result is
        # the same « KP » sprite (the draw rebuilds the tiles from scratch).
        results = [
            _expected_new(v, _draw_green_label) for v in GREEN_OLD_VARIANTS.values()
        ]
        self.assertEqual(results[0], results[1])

    def test_party_label_preserves_bar_cap_columns(self):
        # Grid columns 14-15 (last byte of each row in the right-hand tiles
        # 52/60) hold the HP-bar left cap; the redraw must not touch them.
        new = _expected_new(PARTY_OLD_TILES, _draw_party_label)
        for tile in (52, 60):
            old_b = bytes.fromhex(PARTY_OLD_TILES[tile])
            new_b = bytes.fromhex(new[tile])
            for row in range(8):
                self.assertEqual(old_b[row * 4 + 3], new_b[row * 4 + 3],
                                 f"tile {tile} row {row} cols 14-15 modified")

    def test_grey_label_preserves_oval_border(self):
        new = _expected_new(GREY_OLD_TILES, _draw_grey_label)
        for tile in GREY_OLD_TILES:
            old_b = bytes.fromhex(GREY_OLD_TILES[tile])
            new_b = bytes.fromhex(new[tile])
            for i, (ob, nb) in enumerate(zip(old_b, new_b)):
                for nib_old, nib_new in (((ob & 0xF), (nb & 0xF)),
                                         ((ob >> 4), (nb >> 4))):
                    if nib_old in (0x9, 0xA):  # grid line / dark bg
                        self.assertEqual(nib_old, nib_new,
                                         f"tile {tile} byte {i} border modified")


@pytest.mark.rom
class TestBuiltDeRomShowsKp(unittest.TestCase):
    """The shipped DE ROM must contain the « KP » tiles in all three blocks."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_DE_ROM.exists():
            pytest.skip("GenedRom-de.gba not built")
        cls.rom = bytearray(BUILT_DE_ROM.read_bytes())

    def _assert_block_is_kp(self, block, old_tiles, draw):
        result = lz77_decompress(self.rom, block)
        self.assertIsNotNone(result, f"block 0x{block:08X} not decompressible")
        tiles = bytearray(result[0])
        expected = _expected_new(old_tiles, draw)
        self.assertEqual(_tiles_hex(tiles, old_tiles.keys()), expected,
                         f"block 0x{block:08X} does not render « KP »")

    def test_party_label_is_kp(self):
        self._assert_block_is_kp(PARTY_BLOCK, PARTY_OLD_TILES, _draw_party_label)

    def test_summary_bar_label_is_kp(self):
        self._assert_block_is_kp(GREEN_BLOCK, GREEN_OLD_VARIANTS["ES « PS »"],
                                 _draw_green_label)

    def test_summary_grey_label_is_kp(self):
        self._assert_block_is_kp(GREY_BLOCK, GREY_OLD_TILES, _draw_grey_label)


if __name__ == "__main__":
    unittest.main()
