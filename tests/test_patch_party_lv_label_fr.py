"""Regression tests for the FR party-menu « Lv » → « N. » glyph patch.

The party list level prefix (« Lv10 ») is a single ligature glyph (codepoint
0x05 of the non-compressed FRLG party font) at ROM offset 0x1ECFA0 — not a
pointed string and not an LZ77 label. The patch replaces it with « N. ». The
built FR ROM must contain the « N. » glyph bytes.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.party_lv_label import (
    GLYPH_SIZE,
    LV_GLYPH_OFFSET,
    NEW_ND_GLYPH,
    OLD_LV_GLYPH,
    apply_patch,
)

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"


def _fake_rom(glyph: bytes) -> bytearray:
    rom = bytearray(0x1ECFA0 + GLYPH_SIZE + 16)
    rom[0xB2] = 0x96  # GBA validity byte checked by the patch
    rom[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE] = glyph
    return rom


class TestGlyphDefinitions(unittest.TestCase):
    def test_glyphs_are_32_bytes(self):
        self.assertEqual(len(OLD_LV_GLYPH), GLYPH_SIZE)
        self.assertEqual(len(NEW_ND_GLYPH), GLYPH_SIZE)

    def test_new_differs_from_old(self):
        self.assertNotEqual(NEW_ND_GLYPH, OLD_LV_GLYPH)

    def test_period_dot_added_to_empty_right_column(self):
        # The « N. » glyph is the real « N » with a white dot (value 5) in the
        # right column, at nibbles 36/40/44 (local col 3, rows 9-11).
        for nib in (36, 40, 44):
            byte = nib // 2
            val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
            self.assertEqual(val, 5, f"nibble {nib} should be white(5) for the period")
            old_val = (OLD_LV_GLYPH[byte] & 0xF) if nib % 2 == 0 else (OLD_LV_GLYPH[byte] >> 4)
            self.assertNotEqual(old_val, 5, f"nibble {nib} was already ink in « Lv »")


class TestApplyPatch(unittest.TestCase):
    def test_patches_lv_to_nd(self):
        rom = _fake_rom(OLD_LV_GLYPH)
        p = Path("/tmp/_lvtest.gba")
        p.write_bytes(rom)
        self.assertEqual(apply_patch(p), 1)
        out = p.read_bytes()
        self.assertEqual(out[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE], NEW_ND_GLYPH)

    def test_idempotent(self):
        rom = _fake_rom(NEW_ND_GLYPH)
        p = Path("/tmp/_lvtest2.gba")
        p.write_bytes(rom)
        self.assertEqual(apply_patch(p), 0)
        self.assertEqual(p.read_bytes()[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE],
                         NEW_ND_GLYPH)

    def test_unknown_glyph_is_skipped_not_corrupted(self):
        junk = bytes(range(GLYPH_SIZE))
        rom = _fake_rom(junk)
        p = Path("/tmp/_lvtest3.gba")
        p.write_bytes(rom)
        self.assertEqual(apply_patch(p), 0)
        self.assertEqual(p.read_bytes()[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE], junk)


@pytest.mark.rom
class TestBuiltFrRomShowsNd(unittest.TestCase):
    """The shipped FR ROM must carry the « N. » glyph at 0x1ECFA0."""

    def test_built_rom_has_nd_glyph(self):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        rom = BUILT_FR_ROM.read_bytes()
        self.assertEqual(rom[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE], NEW_ND_GLYPH,
                         "built FR ROM does not render « N. » in the party menu")


if __name__ == "__main__":
    unittest.main()
