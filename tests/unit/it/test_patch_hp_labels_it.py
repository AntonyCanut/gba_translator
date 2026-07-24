"""Regression tests for the IT HP-label graphics patch (HP/PS → PS).

Sibling of tests/test_patch_hp_labels_de.py — same three LZ77 label blocks, but
Italian draws « PS » (Punti Salute). All three labels (party-menu green label,
summary-screen HP-bar sheet, summary-screen grey stat label) are 4bpp tiles
inside LZ77 blocks — never handled by the text pipeline. The built IT ROM must
render « PS » while keeping the English five-row bar body and both end caps
(GitHub issue #84).
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from languages.fr.patches import hp_labels as fr_hp_labels
from languages.fr.patches.font import lz77_decompress
from languages.it.patches.hp_labels import (
    GREEN_BLOCK,
    GREEN_OLD_VARIANTS,
    GREEN_PS_FILL,
    GREY_BLOCK,
    GREY_OLD_TILES,
    GREY_PS_FILL,
    PARTY_BLOCK,
    PARTY_NCOLS,
    PARTY_OLD_TILES,
    PARTY_PS_FILL,
    _draw_green_label,
    _draw_grey_label,
    _draw_party_label,
    _expected_new,
    _tiles_hex,
)

BUILT_IT_ROM = Path(__file__).parent.parent.parent.parent / "output" / "roms" / "GenedRom-it.gba"
ENGLISH_ROM = Path(__file__).parent.parent.parent.parent / "input" / "roms" / "englishrom.gba"

EXPECTED_EN_GREEN_TILES: dict[int, str] = {
    0: "00000000ffffffff333333333333333333333333ffffffff0000000000000000",
    1: "00000000ffffffff323333333133333331333333ffffffff0000000000000000",
    2: "00000000ffffffff223333331133333311333333ffffffff0000000000000000",
    3: "00000000ffffffff223233331131333311313333ffffffff0000000000000000",
    4: "00000000ffffffff222233331111333311113333ffffffff0000000000000000",
    5: "00000000ffffffff222232331111313311113133ffffffff0000000000000000",
    6: "00000000ffffffff222222331111113311111133ffffffff0000000000000000",
    7: "00000000ffffffff222222321111113111111131ffffffff0000000000000000",
    8: "00000000ffffffff222222221111111111111111ffffffff0000000000000000",
    9: "00fff00ff0444ff4f04444f4f04444f4f0444ff400fff00f0000000000000000",
    10: "ffff0f004444f400444ff4f04444f4f044ff0ff0ff0000000000000000000000",
    11: "00000000000000000f0000000f0000000f000000000000000000000000000000",
}


def _non_english_green_sheet() -> dict[int, str]:
    sheet = {tile: "aa" * 32 for tile in range(12)}
    sheet.update(GREEN_OLD_VARIANTS["ES « PS »"])
    return sheet


class TestPsArtDefinitions(unittest.TestCase):
    def test_party_fill_stays_inside_label_area(self):
        for r, c in PARTY_PS_FILL:
            self.assertTrue(0 <= r < 6, f"row {r} outside 6-row label")
            # outline needs one free column on each side of the fill
            self.assertTrue(1 <= c < PARTY_NCOLS - 1, f"col {c} would clip outline")

    def test_green_fill_uses_english_four_row_geometry(self):
        self.assertEqual(sorted({r for r, _ in GREEN_PS_FILL}), [1, 2, 3, 4])
        for r, c in GREEN_PS_FILL:
            self.assertTrue(1 <= c <= 12, f"col {c} would clip the bar cap")

    def test_grey_fill_stays_inside_oval(self):
        for r, c in GREY_PS_FILL:
            self.assertTrue(3 <= r <= 9, f"row {r} outside letter rows")
            self.assertTrue(3 <= c <= 13, f"col {c} outside oval interior")

    def test_new_art_differs_from_old(self):
        self.assertNotEqual(_expected_new(PARTY_OLD_TILES, _draw_party_label),
                            PARTY_OLD_TILES)
        self.assertNotEqual(_expected_new(GREY_OLD_TILES, _draw_grey_label),
                            GREY_OLD_TILES)
        for variant in GREEN_OLD_VARIANTS.values():
            self.assertNotEqual(_expected_new(variant, _draw_green_label), variant)

    def test_it_ps_differs_from_es_ps_source(self):
        # The green block's source is already ES « PS », but the redraw must
        # still change the bytes: IT reuses the FR-verified P glyph with a
        # new S rather than leaving the Spanish sprite untouched, so all
        # three blocks share one consistent font.
        es = GREEN_OLD_VARIANTS["ES « PS »"]
        self.assertNotEqual(_expected_new(es, _draw_green_label), es)

    def test_it_ps_differs_from_fr_pv(self):
        # The IT label must be distinct from the FR « PV » drawn from the
        # same source tiles — otherwise the port drew the wrong letters.
        self.assertNotEqual(_expected_new(PARTY_OLD_TILES, _draw_party_label),
                            _expected_new(PARTY_OLD_TILES,
                                          fr_hp_labels._draw_party_label))
        self.assertNotEqual(_expected_new(GREY_OLD_TILES, _draw_grey_label),
                            _expected_new(GREY_OLD_TILES,
                                          fr_hp_labels._draw_grey_label))
        es = GREEN_OLD_VARIANTS["ES « PS »"]
        self.assertNotEqual(_expected_new(es, _draw_green_label),
                            _expected_new(es, fr_hp_labels._draw_green_label))

    def test_green_variants_converge_to_same_ps(self):
        # Whether the source block held EN « HP » or ES « PS », the result is
        # the same « PS » sprite (the draw rebuilds the tiles from scratch).
        results = [
            _expected_new(v, _draw_green_label) for v in GREEN_OLD_VARIANTS.values()
        ]
        self.assertEqual(results[0], results[1])

    def test_green_sheet_restores_english_body_and_caps(self):
        new = _expected_new(_non_english_green_sheet(), _draw_green_label)
        for tile in list(range(9)) + [11]:
            self.assertEqual(new[tile], EXPECTED_EN_GREEN_TILES[tile],
                             f"tile {tile} is not the English bar art")
        old_b = bytes.fromhex(EXPECTED_EN_GREEN_TILES[10])
        new_b = bytes.fromhex(new[10])
        for row in range(8):
            self.assertEqual(old_b[row * 4 + 3] >> 4, new_b[row * 4 + 3] >> 4,
                             f"tile 10 row {row} left cap modified")

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


class TestPsPatchIsIdempotent(unittest.TestCase):
    """Re-running the patch on already-« PS » tiles must be a no-op."""

    def test_party_already_ps_is_skipped(self):
        already = _expected_new(PARTY_OLD_TILES, _draw_party_label)
        self.assertEqual(_expected_new(already, _draw_party_label), already)

    def test_grey_already_ps_is_skipped(self):
        already = _expected_new(GREY_OLD_TILES, _draw_grey_label)
        self.assertEqual(_expected_new(already, _draw_grey_label), already)

    def test_green_already_ps_is_skipped(self):
        es = GREEN_OLD_VARIANTS["ES « PS »"]
        already = _expected_new(es, _draw_green_label)
        self.assertEqual(_expected_new(already, _draw_green_label), already)


@pytest.mark.rom
class TestBuiltItRomShowsPs(unittest.TestCase):
    """The shipped IT ROM must contain the « PS » tiles in all three blocks."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_IT_ROM.exists():
            pytest.skip("GenedRom-it.gba not built")
        cls.rom = bytearray(BUILT_IT_ROM.read_bytes())

    def _assert_block_is_ps(self, block, old_tiles, draw):
        result = lz77_decompress(self.rom, block)
        self.assertIsNotNone(result, f"block 0x{block:08X} not decompressible")
        tiles = bytearray(result[0])
        expected = _expected_new(old_tiles, draw)
        self.assertEqual(_tiles_hex(tiles, old_tiles.keys()), expected,
                         f"block 0x{block:08X} does not render « PS »")

    def test_party_label_is_ps(self):
        self._assert_block_is_ps(PARTY_BLOCK, PARTY_OLD_TILES, _draw_party_label)

    def test_summary_bar_label_is_ps(self):
        self._assert_block_is_ps(GREEN_BLOCK, GREEN_OLD_VARIANTS["ES « PS »"],
                                 _draw_green_label)

    def test_summary_bar_sheet_matches_english_body_and_caps(self):
        if not ENGLISH_ROM.exists():
            self.skipTest("englishrom.gba not available")
        english = lz77_decompress(bytearray(ENGLISH_ROM.read_bytes()), GREEN_BLOCK)
        italian = lz77_decompress(self.rom, GREEN_BLOCK)
        self.assertIsNotNone(english)
        self.assertIsNotNone(italian)
        en_tiles, it_tiles = bytes(english[0]), bytes(italian[0])
        for tile in list(range(9)) + [11]:
            self.assertEqual(it_tiles[tile * 32:(tile + 1) * 32],
                             en_tiles[tile * 32:(tile + 1) * 32],
                             f"tile {tile} diverges from the English bar art")
        for row in range(8):
            off = 10 * 32 + row * 4 + 3
            self.assertEqual(it_tiles[off] >> 4, en_tiles[off] >> 4,
                             f"tile 10 row {row} left cap diverges from English")

    def test_summary_grey_label_is_ps(self):
        self._assert_block_is_ps(GREY_BLOCK, GREY_OLD_TILES, _draw_grey_label)


if __name__ == "__main__":
    unittest.main()
