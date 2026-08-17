"""Regression tests for the DE HP-label graphics patch (HP/PS → KP).

Sibling of tests/test_patch_hp_labels_fr.py — same three LZ77 label blocks, but
German draws « KP » (Kraftpunkte) instead of the French « PV ». All three labels
(party-menu green label, summary-screen HP-bar sheet, summary-screen grey stat
label) are 4bpp tiles inside LZ77 blocks — never handled by the text pipeline.
The built DE ROM must render « KP » while keeping the English five-row bar body
and both end caps (GitHub issue #84).
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.de.patches.hp_labels import (
    BATTLE_BLOCKS,
    BATTLE_H_TILE_HEX,
    BATTLE_K_FILL,
    BATTLE_P_TILE_HEX,
    GREEN_BLOCK,
    GREEN_KP_FILL,
    GREEN_OLD_VARIANTS,
    GREEN_SLOT_LEN,
    GREY_BLOCK,
    GREY_KP_FILL,
    GREY_OLD_TILES,
    HPEL_H_LABEL_TILES,
    HPEL_K_FILL,
    HPEL_OLD_H_ALT_HEX,
    HPEL_OLD_H_HEX,
    HPEL_REGION,
    PARTY_BLOCK,
    PARTY_KP_FILL,
    PARTY_NCOLS,
    PARTY_OLD_TILES,
    TEXT_HP_LABELS,
    _draw_green_label,
    _draw_grey_label,
    _draw_party_label,
    _expected_new,
    _hpel_is_h,
    _hpel_rows,
    _make_draw_battle_label,
    _patch_hp_element,
    _patch_text_hp_labels,
    _tiles_hex,
)
from languages.fr.patches import hp_labels as fr_hp_labels
from languages.fr.patches.font import lz77_compress, lz77_decompress

BUILT_DE_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-de.gba"
ENGLISH_ROM = Path(__file__).parent.parent / "input" / "roms" / "englishrom.gba"

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


class TestKpArtDefinitions(unittest.TestCase):
    def test_party_fill_stays_inside_label_area(self):
        for r, c in PARTY_KP_FILL:
            self.assertTrue(0 <= r < 6, f"row {r} outside 6-row label")
            # outline needs one free column on each side of the fill
            self.assertTrue(1 <= c < PARTY_NCOLS - 1, f"col {c} would clip outline")

    def test_green_fill_uses_english_four_row_geometry(self):
        self.assertEqual(sorted({r for r, _ in GREEN_KP_FILL}), [1, 2, 3, 4])
        for r, c in GREEN_KP_FILL:
            self.assertTrue(1 <= c <= 12, f"col {c} would clip the bar cap")

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
        self.assertNotEqual(_expected_new(PARTY_OLD_TILES, _draw_party_label),
                            _expected_new(PARTY_OLD_TILES,
                                          fr_hp_labels._draw_party_label))
        self.assertNotEqual(_expected_new(GREY_OLD_TILES, _draw_grey_label),
                            _expected_new(GREY_OLD_TILES,
                                          fr_hp_labels._draw_grey_label))
        es = GREEN_OLD_VARIANTS["ES « PS »"]
        self.assertNotEqual(_expected_new(es, _draw_green_label),
                            _expected_new(es, fr_hp_labels._draw_green_label))

    def test_green_variants_converge_to_same_kp(self):
        # Whether the source block held EN « HP » or ES « PS », the result is
        # the same « KP » sprite (the draw rebuilds the tiles from scratch).
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

    def test_green_sheet_fits_reserved_lz77_slot(self):
        new = _expected_new(_non_english_green_sheet(), _draw_green_label)
        sheet = b"".join(bytes.fromhex(new[tile]) for tile in range(12))
        self.assertLessEqual(len(lz77_compress(sheet)), GREEN_SLOT_LEN)

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

    def test_battle_healthbox_redraws_h_to_k_and_preserves_p(self):
        for off, h_tile, p_tile in BATTLE_BLOCKS:
            old = {h_tile: BATTLE_H_TILE_HEX[off], p_tile: BATTLE_P_TILE_HEX[off]}
            new = _expected_new(old, _make_draw_battle_label(h_tile, p_tile))
            self.assertNotEqual(new[h_tile], old[h_tile], f"0x{off:08X}: H unchanged")
            self.assertEqual(new[p_tile], old[p_tile], f"0x{off:08X}: P changed")
            for row in (0, 1, 2, 7):
                before = bytes.fromhex(old[h_tile])[row * 4 : row * 4 + 4]
                after = bytes.fromhex(new[h_tile])[row * 4 : row * 4 + 4]
                self.assertEqual(before, after, f"0x{off:08X}: border row {row} changed")

    def test_battle_k_fill_stays_inside_first_letter_cell(self):
        for row, col in BATTLE_K_FILL:
            self.assertTrue(3 <= row <= 6 and 2 <= col <= 6)


class TestRawHealthboxElements(unittest.TestCase):
    def test_every_h_copy_becomes_k_and_patch_is_idempotent(self):
        _lo, hi = HPEL_REGION
        rom = bytearray(hi + 32)
        for off, old_hex in HPEL_H_LABEL_TILES.items():
            rom[off : off + 32] = bytes.fromhex(old_hex)

        self.assertEqual(_patch_hp_element(rom), len(HPEL_H_LABEL_TILES))
        after_first = bytes(rom)
        self.assertEqual(_patch_hp_element(rom), 0)
        self.assertEqual(bytes(rom), after_first)

        for off in HPEL_H_LABEL_TILES:
            tile = bytes(rom[off : off + 32])
            self.assertFalse(_hpel_is_h(tile), f"0x{off:08X}: residual H")
            self.assertEqual(_hpel_rows(tile), HPEL_K_FILL)

    def test_alt_palette_keeps_its_pill_and_border(self):
        rom = bytearray(HPEL_REGION[1] + 32)
        off = min(HPEL_H_LABEL_TILES)
        old = bytes.fromhex(HPEL_OLD_H_ALT_HEX)
        rom[off : off + 32] = old

        self.assertEqual(_patch_hp_element(rom), 1)
        new = bytes(rom[off : off + 32])
        for row in (0, 1, 2, 7):
            self.assertEqual(old[row * 4 : row * 4 + 4], new[row * 4 : row * 4 + 4])
        self.assertEqual(_hpel_rows(new), HPEL_K_FILL)

    def test_known_h_variants_are_recognized(self):
        self.assertTrue(_hpel_is_h(bytes.fromhex(HPEL_OLD_H_HEX)))
        self.assertTrue(_hpel_is_h(bytes.fromhex(HPEL_OLD_H_ALT_HEX)))


class TestFixedTextHpLabels(unittest.TestCase):
    def test_every_fixed_hp_cell_becomes_kp_and_patch_is_idempotent(self):
        end = max(TEXT_HP_LABELS) + 8
        rom = bytearray(b"\x5A" * end)
        for offset, (old, _new) in TEXT_HP_LABELS.items():
            rom[offset : offset + len(old)] = old

        self.assertEqual(_patch_text_hp_labels(rom), len(TEXT_HP_LABELS))
        after_first = bytes(rom)
        self.assertEqual(_patch_text_hp_labels(rom), 0)
        self.assertEqual(bytes(rom), after_first)

        for offset, (_old, new) in TEXT_HP_LABELS.items():
            self.assertEqual(bytes(rom[offset : offset + len(new)]), new)

    def test_fixed_text_patch_preserves_adjacent_bytes(self):
        for offset, (old, _new) in TEXT_HP_LABELS.items():
            rom = bytearray(b"\x5A" * (offset + len(old) + 2))
            rom[offset : offset + len(old)] = old
            before = (rom[offset - 1], rom[offset + len(old)])

            self.assertEqual(_patch_text_hp_labels(rom), 1)
            self.assertEqual((rom[offset - 1], rom[offset + len(old)]), before)

    def test_unknown_fixed_text_cell_is_never_overwritten(self):
        end = max(TEXT_HP_LABELS) + 8
        rom = bytearray(b"\x5A" * end)
        before = bytes(rom)

        self.assertEqual(_patch_text_hp_labels(rom), 0)
        self.assertEqual(bytes(rom), before)


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

    def test_summary_bar_sheet_matches_english_body_and_caps(self):
        if not ENGLISH_ROM.exists():
            self.skipTest("englishrom.gba not available")
        english = lz77_decompress(bytearray(ENGLISH_ROM.read_bytes()), GREEN_BLOCK)
        german = lz77_decompress(self.rom, GREEN_BLOCK)
        self.assertIsNotNone(english)
        self.assertIsNotNone(german)
        en_tiles, de_tiles = bytes(english[0]), bytes(german[0])
        for tile in list(range(9)) + [11]:
            self.assertEqual(de_tiles[tile * 32:(tile + 1) * 32],
                             en_tiles[tile * 32:(tile + 1) * 32],
                             f"tile {tile} diverges from the English bar art")
        for row in range(8):
            off = 10 * 32 + row * 4 + 3
            self.assertEqual(de_tiles[off] >> 4, en_tiles[off] >> 4,
                             f"tile 10 row {row} left cap diverges from English")

    def test_summary_grey_label_is_kp(self):
        self._assert_block_is_kp(GREY_BLOCK, GREY_OLD_TILES, _draw_grey_label)

    def test_battle_healthbox_labels_are_kp(self):
        for off, h_tile, p_tile in BATTLE_BLOCKS:
            old = {h_tile: BATTLE_H_TILE_HEX[off], p_tile: BATTLE_P_TILE_HEX[off]}
            self._assert_block_is_kp(
                off, old, _make_draw_battle_label(h_tile, p_tile)
            )

    def test_raw_healthbox_has_no_h_label_copy(self):
        lo, hi = HPEL_REGION
        residual = []
        for off in range(lo, hi - 32, 4):
            if _hpel_is_h(bytes(self.rom[off : off + 32])):
                residual.append(off)
        self.assertEqual(
            residual,
            [],
            "residual « HP » healthbox H tiles at "
            + ", ".join(f"0x{off:08X}" for off in residual),
        )

    def test_fixed_text_labels_are_kp(self):
        for offset, (_old, new) in TEXT_HP_LABELS.items():
            self.assertEqual(
                bytes(self.rom[offset : offset + len(new)]),
                new,
                f"0x{offset:08X} ne contient pas « KP »",
            )

    def test_shared_hp_label_pointer_consumers_still_target_kp(self):
        shared_label = 0x004169C2
        for pointer_site in (0x00125174, 0x008C0FFC, 0x008C980C):
            target = int.from_bytes(
                self.rom[pointer_site : pointer_site + 4], "little"
            ) - 0x08000000
            self.assertEqual(target, shared_label)
            self.assertEqual(
                bytes(self.rom[target : target + 3]),
                TEXT_HP_LABELS[shared_label][1],
            )


if __name__ == "__main__":
    unittest.main()
