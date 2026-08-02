"""Regression tests for the FR HP-label graphics patch (HP/PS → PV).

Four label graphics show the hit-point abbreviation: the party-menu green
label, the summary-screen HP-bar sheet, the summary-screen grey stat label,
and the in-battle healthbox label (GitHub issue #125). All are 4bpp tiles
inside LZ77 blocks — never handled by the text pipeline. The built FR ROM
must render « PV » in every block — including the four battle healthbox
sheets (0xD1F604 / 0xEEF0AC / 0xEEF380 / 0xEEF688).

The summary-screen sheet also carries the HP bar itself: restoring the
English body and both end caps is what fixes the bar truncated at both ends
reported in GitHub issue #84.
"""

import re
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.font import lz77_compress, lz77_decompress
from languages.fr.patches.hp_labels import (
    BATTLE_BLOCKS,
    BATTLE_H_TILE_HEX,
    BATTLE_P_FILL,
    BATTLE_P_TILE_HEX,
    BATTLE_V_FILL,
    GREEN_BLOCK,
    GREEN_EN_TILES,
    GREEN_NCOLS,
    GREEN_NROWS,
    GREEN_OLD_VARIANTS,
    GREEN_PV_FILL,
    GREEN_SLOT_LEN,
    GREY_BLOCK,
    GREY_OLD_TILES,
    GREY_PV_FILL,
    HPEL_P_FILL,
    HPEL_V_FILL,
    HPEL_LABEL_TILES,
    HPEL_OLD_H_ALT_HEX,
    HPEL_OLD_H_HEX,
    HPEL_OLD_P_HEX,
    HPEL_REGION,
    TILE,
    PARTY_BLOCK,
    PARTY_CURRENT_PV_TILES,
    PARTY_NCOLS,
    PARTY_OLD_TILES,
    PARTY_PV_FILL,
    _hpel_is_h,
    _hpel_is_label,
    _hpel_is_p,
    _hpel_plate,
    _hpel_rows,
    _make_draw_battle_label,
    _patch_hp_element,
    _draw_green_label,
    _draw_grey_label,
    _draw_party_label,
    _expected_new,
    _tiles_hex,
    hpel_convert_pair,
    hpel_convert_tile,
)

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"
ENGLISH_ROM = Path(__file__).parent.parent / "input" / "roms" / "englishrom.gba"


def _tile_from_pixels(rows: list[str]) -> bytes:
    """Build a 4bpp tile from 8 rows of 8 pixel nibbles (leftmost pixel first)."""
    out = bytearray()
    for row in rows:
        for c in range(0, 8, 2):
            out.append(int(row[c], 16) | (int(row[c + 1], 16) << 4))
    return bytes(out)


class TestPvArtDefinitions(unittest.TestCase):
    def test_party_fill_stays_inside_label_area(self):
        for r, c in PARTY_PV_FILL:
            self.assertTrue(0 <= r < 6, f"row {r} outside 6-row label")
            # outline needs one free column on each side of the fill
            self.assertTrue(1 <= c < PARTY_NCOLS - 1, f"col {c} would clip outline")

    def test_green_fill_stays_inside_label_box(self):
        for r, c in GREEN_PV_FILL:
            self.assertTrue(1 <= r <= GREEN_NROWS - 2, f"row {r} would clip outline")
            # cols 14-15 carry the HP-bar left cap, so the outline must stop
            # one column earlier than the box edge
            self.assertTrue(1 <= c <= GREEN_NCOLS - 2, f"col {c} would clip the bar cap")

    def test_grey_fill_stays_inside_oval(self):
        for r, c in GREY_PV_FILL:
            self.assertTrue(3 <= r <= 9, f"row {r} outside letter rows")
            self.assertTrue(3 <= c <= 13, f"col {c} outside oval interior")

    def test_new_art_differs_from_old(self):
        self.assertNotEqual(_expected_new(PARTY_OLD_TILES, _draw_party_label),
                            PARTY_OLD_TILES)
        self.assertNotEqual(_expected_new(GREY_OLD_TILES, _draw_grey_label),
                            GREY_OLD_TILES)
        for variant in GREEN_OLD_VARIANTS.values():
            self.assertNotEqual(_expected_new(variant, _draw_green_label), variant)

    def test_green_variants_converge_to_same_sheet(self):
        # Whether the block held EN « HP », ES « PS » or the pre-#84 French
        # « PV » drawn on the capless Spanish sheet, the result is the same:
        # the draw rebuilds the whole sheet from the English reference.
        results = [
            _expected_new(v, _draw_green_label) for v in GREEN_OLD_VARIANTS.values()
        ]
        for other in results[1:]:
            self.assertEqual(results[0], other)

    def test_green_sheet_keeps_english_bar_and_caps(self):
        # GitHub issue #84: the Spanish sheet copied in by
        # repair_localized_lz77_blocks has a 7-row bar body and an empty
        # tile 11, so the bar looked truncated at both ends. Everything but
        # the label letters must come back byte-exact from the English art.
        new = _expected_new(GREEN_OLD_VARIANTS["ES « PS »"], _draw_green_label)
        for tile in list(range(9)) + [11]:
            self.assertEqual(new[tile], GREEN_EN_TILES[tile],
                             f"tile {tile} is not the English bar art")
        # tile 10 column 7 (rows 2-4) is the bar's left cap, inside the label
        # tile — the redraw must leave those pixels alone.
        old_b = bytes.fromhex(GREEN_EN_TILES[10])
        new_b = bytes.fromhex(new[10])
        for row in range(8):
            self.assertEqual(old_b[row * 4 + 3] >> 4, new_b[row * 4 + 3] >> 4,
                             f"tile 10 row {row} col 7 (left cap) modified")

    def test_green_sheet_fits_its_slot(self):
        new = _expected_new(GREEN_OLD_VARIANTS["EN « HP »"], _draw_green_label)
        sheet = bytearray(len(GREEN_EN_TILES) * 32)
        for tile, hexdata in new.items():
            sheet[tile * 32:(tile + 1) * 32] = bytes.fromhex(hexdata)
        self.assertLessEqual(len(lz77_compress(bytes(sheet))), GREEN_SLOT_LEN)

    def test_clipped_party_variant_migrates_to_same_pv(self):
        self.assertEqual(
            _expected_new(PARTY_CURRENT_PV_TILES, _draw_party_label),
            _expected_new(PARTY_OLD_TILES, _draw_party_label),
        )

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

    def test_battle_fill_stays_inside_letter_boxes(self):
        for r, c in BATTLE_P_FILL:
            self.assertTrue(3 <= r <= 6 and 2 <= c <= 6,
                            f"P fill ({r},{c}) outside H-tile letter box")
        for r, c in BATTLE_V_FILL:
            self.assertTrue(3 <= r <= 6 and 0 <= c <= 4,
                            f"V fill ({r},{c}) outside P-tile letter box")

    def test_battle_new_art_differs_from_old(self):
        for off, h_tile, p_tile in BATTLE_BLOCKS:
            old = {h_tile: BATTLE_H_TILE_HEX[off], p_tile: BATTLE_P_TILE_HEX[off]}
            draw = _make_draw_battle_label(h_tile, p_tile)
            self.assertNotEqual(_expected_new(old, draw), old,
                                f"block 0x{off:08X} art unchanged")

    def test_battle_redraw_preserves_pill_border_rows(self):
        # Rows 0-2 and 7 (pill top/bottom border + transparent margin) must be
        # left byte-exact — only the letter rows 3-6 change.
        for off, h_tile, p_tile in BATTLE_BLOCKS:
            old = {h_tile: BATTLE_H_TILE_HEX[off], p_tile: BATTLE_P_TILE_HEX[off]}
            new = _expected_new(old, _make_draw_battle_label(h_tile, p_tile))
            for tile in (h_tile, p_tile):
                ob = bytes.fromhex(old[tile])
                nb = bytes.fromhex(new[tile])
                for row in (0, 1, 2, 7):
                    self.assertEqual(ob[row * 4:row * 4 + 4],
                                     nb[row * 4:row * 4 + 4],
                                     f"tile {tile} border row {row} modified")

    def test_battle_p_tile_preserves_right_cap(self):
        # The « P » letter tile keeps its right-hand pill cap (col 7) untouched.
        for off, h_tile, p_tile in BATTLE_BLOCKS:
            old = {h_tile: BATTLE_H_TILE_HEX[off], p_tile: BATTLE_P_TILE_HEX[off]}
            new = _expected_new(old, _make_draw_battle_label(h_tile, p_tile))
            ob = bytes.fromhex(old[p_tile])
            nb = bytes.fromhex(new[p_tile])
            for row in range(8):
                self.assertEqual(ob[row * 4 + 3] >> 4, nb[row * 4 + 3] >> 4,
                                 f"P-tile row {row} col 7 cap modified")


class TestOpponentHpElement(unittest.TestCase):
    """The uncompressed healthbox « HP » element tiles (issue #125 reopens).

    The element table holds the label four times; the box is drawn from one
    copy but ``UpdateStatusIconInHealthbox`` re-copies another, so a statused
    Pokémon showed « HP » again until every copy was converted.
    """

    def setUp(self):
        self.old_h = bytes.fromhex(HPEL_OLD_H_HEX)
        self.old_p = bytes.fromhex(HPEL_OLD_P_HEX)
        self.new_h, self.new_p = hpel_convert_pair(self.old_h, self.old_p)

    def test_recognizes_known_hp_pair(self):
        self.assertTrue(_hpel_is_h(self.old_h), "opponent « H » tile not recognised")
        self.assertTrue(_hpel_is_p(self.old_p), "opponent « P » tile not recognised")

    def test_every_known_label_tile_converts(self):
        # All four copies — including the pill-colour-3 sibling and the second
        # « P » — must be recognised and converted, not just the adjacent pair.
        self.assertEqual(len(HPEL_LABEL_TILES), 4)
        for off, old_hex in HPEL_LABEL_TILES.items():
            old = bytes.fromhex(old_hex)
            self.assertTrue(_hpel_is_label(old),
                            f"0x{off:08X} not recognised as a label tile")
            new = hpel_convert_tile(old)
            self.assertIsNotNone(new, f"0x{off:08X} not converted")
            self.assertNotEqual(new, old, f"0x{off:08X} art unchanged")
            self.assertFalse(_hpel_is_h(new), f"0x{off:08X} still reads « H »")
            self.assertIsNone(hpel_convert_tile(new),
                              f"0x{off:08X} would be converted twice")

    def test_alt_palette_h_keeps_its_own_pill_colour(self):
        # The sibling's pill is colour 3, not 7 — the redraw must not paint
        # colour-7 pixels into it.
        old = bytes.fromhex(HPEL_OLD_H_ALT_HEX)
        new = hpel_convert_tile(old)
        self.assertEqual(_hpel_plate(old), 0x3)
        self.assertEqual(_hpel_plate(new), 0x3)
        self.assertEqual(_hpel_rows(new), HPEL_P_FILL,
                         "sibling tile does not draw « P »")
        for row in (0, 1, 2, 7):
            self.assertEqual(old[row * 4:row * 4 + 4], new[row * 4:row * 4 + 4],
                             f"sibling row {row} margin/border modified")

    def test_bar_and_status_art_is_not_mistaken_for_a_label(self):
        # Neighbouring element tiles (HP-bar gradient, status abbreviations)
        # must fail the structural gate so the 4-byte-stride scan can't eat them.
        bar = _tile_from_pixels([
            "00000000", "00000000", "77777777", "11111111",
            "b6666666", "a5555555", "11111111", "77777777",
        ])
        status = _tile_from_pixels([
            "77777777", "7c111ccc", "7c1cc1c1", "7c1cc1c1",
            "7c111ccc", "7c1cccc1", "7c1ccccc", "77777777",
        ])
        for name, tile in (("HP bar", bar), ("status abbrev", status)):
            self.assertIsNone(hpel_convert_tile(tile),
                              f"{name} tile mistaken for an HP label")

    def test_convert_yields_p_then_v(self):
        # H tile → « P » at cols 2-6; P tile → « V » at cols 0-4. Crucially
        # neither converted tile is an « H » any more (so « HP » cannot render),
        # and their letter masks match the intended « P »/« V » art.
        self.assertNotEqual(self.new_h, self.old_h)
        self.assertNotEqual(self.new_p, self.old_p)
        self.assertFalse(_hpel_is_h(self.new_h), "converted first tile still « H »")
        self.assertFalse(_hpel_is_h(self.new_p), "converted second tile reads « H »")
        self.assertEqual(_hpel_rows(self.new_h), HPEL_P_FILL,
                         "first tile does not draw « P »")
        v_rows = {r: {c for c in cols if c <= 4}
                  for r, cols in _hpel_rows(self.new_p).items()}
        self.assertEqual(v_rows, HPEL_V_FILL, "second tile does not draw « V »")

    def test_preserves_margin_and_separator(self):
        # Rows 0-2 and 7 (transparent margin + pill border) stay byte-exact,
        # and the « P »→« V » redraw leaves the col-7 separator stem untouched.
        for old, new in ((self.old_h, self.new_h), (self.old_p, self.new_p)):
            for row in (0, 1, 2, 7):
                self.assertEqual(old[row * 4:row * 4 + 4], new[row * 4:row * 4 + 4],
                                 f"row {row} margin/border modified")
        for row in range(8):  # col 7 = high nibble of byte 3 in each row
            self.assertEqual(self.old_p[row * 4 + 3] >> 4, self.new_p[row * 4 + 3] >> 4,
                             f"V-tile row {row} col 7 separator modified")

    def test_patch_converts_every_copy_and_is_idempotent(self):
        lo, hi = HPEL_REGION
        rom = bytearray(hi + TILE)
        for off, old_hex in HPEL_LABEL_TILES.items():
            rom[off:off + TILE] = bytes.fromhex(old_hex)
        self.assertEqual(_patch_hp_element(rom), len(HPEL_LABEL_TILES),
                         "first pass must convert every label tile")
        after_first = bytes(rom)
        self.assertEqual(_patch_hp_element(rom), 0, "second pass should be a no-op")
        self.assertEqual(bytes(rom), after_first, "second pass changed bytes")
        self.assertEqual(rom[0x00D11BE4:0x00D11BE4 + TILE], self.new_h)
        self.assertEqual(rom[0x00D11C04:0x00D11C04 + TILE], self.new_p)
        for off, old_hex in HPEL_LABEL_TILES.items():
            self.assertEqual(bytes(rom[off:off + TILE]),
                             hpel_convert_tile(bytes.fromhex(old_hex)),
                             f"0x{off:08X} not converted by the patch pass")


@pytest.mark.rom
class TestBuiltFrRomShowsPv(unittest.TestCase):
    """The shipped FR ROM must contain the « PV » tiles in all three blocks."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        cls.rom = bytearray(BUILT_FR_ROM.read_bytes())

    def _assert_block_is_pv(self, block, old_tiles, draw):
        result = lz77_decompress(self.rom, block)
        self.assertIsNotNone(result, f"block 0x{block:08X} not decompressible")
        tiles = bytearray(result[0])
        expected = _expected_new(old_tiles, draw)
        self.assertEqual(_tiles_hex(tiles, old_tiles.keys()), expected,
                         f"block 0x{block:08X} does not render « PV »")

    def test_party_label_is_pv(self):
        self._assert_block_is_pv(PARTY_BLOCK, PARTY_OLD_TILES, _draw_party_label)

    def test_summary_bar_label_is_pv(self):
        self._assert_block_is_pv(GREEN_BLOCK, GREEN_OLD_VARIANTS["ES « PS »"],
                                 _draw_green_label)

    def test_summary_bar_sheet_matches_english_outside_the_label(self):
        # GitHub issue #84 in the shipped ROM: every tile but the two label
        # tiles must be the English bar art, caps included.
        if not ENGLISH_ROM.exists():
            self.skipTest("englishrom.gba not available")
        english = lz77_decompress(bytearray(ENGLISH_ROM.read_bytes()), GREEN_BLOCK)
        french = lz77_decompress(self.rom, GREEN_BLOCK)
        self.assertIsNotNone(english)
        self.assertIsNotNone(french)
        en_tiles, fr_tiles = bytes(english[0]), bytes(french[0])
        self.assertEqual(len(fr_tiles), len(en_tiles))
        for tile in list(range(9)) + [11]:
            self.assertEqual(fr_tiles[tile * 32:(tile + 1) * 32],
                             en_tiles[tile * 32:(tile + 1) * 32],
                             f"tile {tile} diverges from the English bar art")
        for row in range(8):
            off = 10 * 32 + row * 4 + 3
            self.assertEqual(fr_tiles[off] >> 4, en_tiles[off] >> 4,
                             f"tile 10 row {row} left cap diverges from English")

    def test_summary_grey_label_is_pv(self):
        self._assert_block_is_pv(GREY_BLOCK, GREY_OLD_TILES, _draw_grey_label)

    def test_battle_healthbox_labels_are_pv(self):
        for off, h_tile, p_tile in BATTLE_BLOCKS:
            old = {h_tile: BATTLE_H_TILE_HEX[off], p_tile: BATTLE_P_TILE_HEX[off]}
            self._assert_block_is_pv(
                off, old, _make_draw_battle_label(h_tile, p_tile))

    def test_opponent_healthbox_element_is_pv(self):
        # Every uncompressed « HP » label tile must be « PV » in the shipped ROM
        # — the pair the box is drawn from AND the copies the status-icon redraw
        # loads (GitHub issue #125: « HP » came back under poison/burn).
        new_h, new_p = hpel_convert_pair(
            bytes.fromhex(HPEL_OLD_H_HEX), bytes.fromhex(HPEL_OLD_P_HEX))
        self.assertEqual(bytes(self.rom[0x00D11BE4:0x00D11BE4 + TILE]), new_h,
                         "opponent « H »→« P » tile not applied in ROM")
        self.assertEqual(bytes(self.rom[0x00D11C04:0x00D11C04 + TILE]), new_p,
                         "opponent « P »→« V » tile not applied in ROM")
        for off, old_hex in HPEL_LABEL_TILES.items():
            self.assertEqual(bytes(self.rom[off:off + TILE]),
                             hpel_convert_tile(bytes.fromhex(old_hex)),
                             f"healthbox label 0x{off:08X} is not « PV » in the ROM")
        # No unconverted label tile — « H » OR « P » — may survive in the
        # element window, whatever its palette slot or neighbours.
        lo, hi = HPEL_REGION
        for off in range(lo, hi - TILE, 4):
            tile = bytes(self.rom[off:off + TILE])
            self.assertIsNone(hpel_convert_tile(tile),
                              f"residual « HP » healthbox label tile at 0x{off:08X}")

    def test_no_hp_label_tile_survives_anywhere_in_the_rom(self):
        # The definitive guard: sweep the WHOLE ROM by letter shape, not just
        # the element window. Byte-exact searches are what kept missing copies
        # of this label (0xD1F604, then 0xD11BC4/0xD123E4).
        # Every label tile starts with two fully transparent rows followed by a
        # non-zero pill row, so that prefix narrows the sweep cheaply.
        residual = []
        for match in re.finditer(rb"(?=\x00{8}[^\x00])", bytes(self.rom)):
            off = match.start()
            if off % 4:
                continue
            if hpel_convert_tile(bytes(self.rom[off:off + TILE])) is not None:
                residual.append(off)
        self.assertEqual(residual, [],
                         "residual « HP » label tiles at "
                         + ", ".join(f"0x{o:08X}" for o in residual))


if __name__ == "__main__":
    unittest.main()
