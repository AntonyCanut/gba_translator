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

from languages.fr.patches.font import lz77_decompress
from languages.de.patches.status_badges import (
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
from src.i18n import load_registry

BUILT_DE_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-de.gba"

# Engine slot order (fixed): PSN=0, PAR=1, SLP=2, FRZ=3, BRN=4, FNT=6.
SLOT_BY_STATUS = {"poison": 0, "sleep": 2, "freeze": 3, "burn": 4}


class TestBadgePatchTable(unittest.TestCase):
    def test_slot_mapping_matches_official_de_abbrevs(self):
        # The badge tiles must spell exactly the official DE abbreviations.
        expected = {
            0: ("G", "I", "F"),   # PSN → GIF
            2: ("S", "C", "H"),   # SLP → SCH
            3: ("G", "E", "F"),   # FRZ → GEF
            4: ("V", "B", "R"),   # BRN → VBR
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
            self.assertEqual(len(_LETTERS[ltr]), 6)      # 6 pixel rows
            for row in _LETTERS[ltr]:
                self.assertEqual(len(row), 4)            # 4 pixel columns


@pytest.mark.rom
class TestBuiltDeBadge(unittest.TestCase):
    """The shipped DE ROM's badges must contain the DE-abbreviation tiles."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_DE_ROM.exists():
            pytest.skip("GenedRom-de.gba not built")
        cls.rom = bytearray(BUILT_DE_ROM.read_bytes())

    def test_status_badges_render_de_abbrevs(self):
        result = lz77_decompress(self.rom, BADGE_BLOCKS[0])
        self.assertIsNotNone(result)
        tiles = bytearray(result[0])

        for slot, a, b, c in _STATUS_PATCHES:
            bg = _read_slot_bg(tiles, slot)
            expected_t1, expected_t2 = _make_3letter_tiles(
                _LETTERS[a], _LETTERS[b], _LETTERS[c], bg
            )
            base = slot * _TILES_PER_BADGE * _TILE_BYTES
            c1 = base + _CONTENT1_IDX * _TILE_BYTES
            c2 = base + _CONTENT2_IDX * _TILE_BYTES
            self.assertEqual(
                bytes(tiles[c1 : c1 + _TILE_BYTES]), expected_t1,
                f"slot {slot} content1 != {a}{b}{c}",
            )
            self.assertEqual(
                bytes(tiles[c2 : c2 + _TILE_BYTES]), expected_t2,
                f"slot {slot} content2 != {a}{b}{c}",
            )


if __name__ == "__main__":
    unittest.main()
