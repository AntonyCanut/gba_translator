"""Regression tests for the DE status-badge graphics patch.

The German build must render the official DE status abbreviations as badge
tiles: GIF (Gift), SCH (Schlaf), GEF (Gefroren), VBR (Verbrennung) and the
2-letter KO (fainted). These match the text ``status_abbrev`` block in
``languages/de/lang.yaml``. Verified at the pixel level by regenerating the
tiles the patch produces and, when the ROM is built, by decompressing the
built ROM's badge block and comparing slot tiles.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.de.patches.status_badges import (
    _CONTENT1_IDX,
    _CONTENT2_IDX,
    _FNT_SLOT,
    _LETTERS,
    _STATUS_PATCHES,
    _TILE_BYTES,
    _TILES_PER_BADGE,
    BADGE_BLOCKS,
    HEALTHBOX_STATUS_GROUPS,
    _make_3letter_tiles,
    _make_ko_tiles,
    _patched_tiles,
    _read_slot_bg,
)
from languages.fr.patches.font import lz77_decompress
from languages.fr.patches.status_badges import _healthbox_status_payload
from src.graphics.sprite_rom import tiles_to_grid
from src.i18n import load_registry

BUILT_DE_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-de.gba"

# Engine slot order (fixed): PSN=0, PAR=1, SLP=2, FRZ=3, BRN=4, FNT=6.
SLOT_BY_STATUS = {"poison": 0, "sleep": 2, "freeze": 3, "burn": 4}


class TestBadgePatchTable(unittest.TestCase):
    def test_slot_mapping_matches_official_de_abbrevs(self):
        # The badge tiles must spell exactly the official DE abbreviations.
        expected = {
            0: ("G", "I", "F"),  # PSN → GIF
            2: ("S", "C", "H"),  # SLP → SCH
            3: ("G", "E", "F"),  # FRZ → GEF
            4: ("V", "B", "R"),  # BRN → VBR
        }
        got = {slot: (a, b, c) for slot, a, b, c in _STATUS_PATCHES}
        self.assertEqual(got, expected)

    def test_par_slot_left_untouched(self):
        # PAR is identical in German, so slot 1 must not be patched.
        self.assertNotIn(1, {slot for slot, *_ in _STATUS_PATCHES})

    def test_badges_match_registry_status_abbrev(self):
        # Guard: badge letters must stay in sync with lang.yaml status_abbrev.
        abbrev = load_registry().get("de").status_abbrev
        for slot, a, b, c in _STATUS_PATCHES:
            status = next(k for k, v in SLOT_BY_STATUS.items() if v == slot)
            self.assertEqual(a + b + c, abbrev[status].upper())

    def test_all_letters_defined_and_well_formed(self):
        used = {ltr for _, *letters in _STATUS_PATCHES for ltr in letters}
        for ltr in used:
            self.assertIn(ltr, _LETTERS)
            self.assertEqual(len(_LETTERS[ltr]), 6)  # 6 pixel rows
            for row in _LETTERS[ltr]:
                self.assertEqual(len(row), 4)  # 4 pixel columns


@pytest.mark.rom
class TestBuiltDeBadge(unittest.TestCase):
    """The shipped DE ROM's badges must contain the DE-abbreviation tiles."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_DE_ROM.exists():
            pytest.skip("GenedRom-de.gba not built")
        cls.rom = bytearray(BUILT_DE_ROM.read_bytes())

    def test_status_badges_render_de_abbrevs_in_every_block(self):
        for block in BADGE_BLOCKS:
            with self.subTest(block=f"0x{block:X}"):
                result = lz77_decompress(self.rom, block)
                self.assertIsNotNone(result)
                tiles = bytearray(result[0])
                for slot, a, b, c in _STATUS_PATCHES:
                    bg = _read_slot_bg(tiles, slot)
                    expected = _make_3letter_tiles(
                        _LETTERS[a], _LETTERS[b], _LETTERS[c], bg
                    )
                    base = slot * _TILES_PER_BADGE * _TILE_BYTES
                    for index, expected_tile in zip(
                        (_CONTENT1_IDX, _CONTENT2_IDX), expected
                    ):
                        start = base + index * _TILE_BYTES
                        self.assertEqual(
                            bytes(tiles[start : start + _TILE_BYTES]), expected_tile
                        )

    def test_ko_badge_renders_in_every_block(self):
        expected = _make_ko_tiles()
        for block in BADGE_BLOCKS:
            with self.subTest(block=f"0x{block:X}"):
                result = lz77_decompress(self.rom, block)
                self.assertIsNotNone(result)
                tiles = bytearray(result[0])
                base = _FNT_SLOT * _TILES_PER_BADGE * _TILE_BYTES
                for index, expected_tile in zip(
                    (_CONTENT1_IDX, _CONTENT2_IDX), expected
                ):
                    start = base + index * _TILE_BYTES
                    self.assertEqual(
                        bytes(tiles[start : start + _TILE_BYTES]), expected_tile
                    )

    def test_raw_battle_healthbox_groups_render_the_same_de_badges(self):
        result = lz77_decompress(self.rom, BADGE_BLOCKS[0])
        self.assertIsNotNone(result)
        grid = tiles_to_grid(
            bytes(_patched_tiles(result[0])[: 32 * _TILE_BYTES]),
            4,
            8,
        )
        for offset, palette_index in HEALTHBOX_STATUS_GROUPS:
            with self.subTest(offset=f"0x{offset:X}"):
                expected = _healthbox_status_payload(grid, palette_index)
                self.assertEqual(
                    bytes(self.rom[offset : offset + len(expected)]),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
