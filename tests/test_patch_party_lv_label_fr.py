"""Regression tests for the FR party-menu « Lv » → « N. » glyph patch.

The party list level prefix (« Lv10 ») is a single ligature glyph (codepoint
0x05 of the non-compressed FRLG party font) at ROM offset 0x1ECFA0 — not a
pointed string and not an LZ77 label. The patch replaces it with « N. ». The
built FR ROM must contain the « N. » glyph bytes.

Issue #138: the dot's drop-shadow must stay within nibble rows 4-11 (the same
vertical extent the plain « N » already uses) so it renders correctly in BOTH
the party list and the in-battle level-up notification box — a row-12 shadow
(the #104 fix) overflows that box's clipped glyph area.

Issue #138 follow-up: each nibble packs two independent 2-bit palette picks (one
per pixel of its 2-pixel-wide cell). The shadow nibble must use value 0xA (grey
for both pixels), not 0x8 (grey for the left pixel only, transparent for the
right one) — the latter rendered as a half-strength/incomplete shadow.

Issue #138 second follow-up: with the shadow completed, the dot's own white ink
was still one pixel narrower than that shadow (and than the glyph's own
antialiasing column beside it) — nibble 37/41 must have its dot-facing sub-pixel
white (value 4: white+transparent), not grey (value 8: grey+transparent).
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
    OLD_ND_GLYPH_HALF_SHADOW,
    OLD_ND_GLYPH_NARROW_DOT,
    OLD_ND_GLYPH_NOSHADOW,
    OLD_ND_GLYPH_ROW12_OVERFLOW,
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
        # right column, at nibbles 36/40 (local col 3, rows 9-10).
        for nib in (36, 40):
            byte = nib // 2
            val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
            self.assertEqual(val, 5, f"nibble {nib} should be white(5) for the period")
            old_val = (OLD_LV_GLYPH[byte] & 0xF) if nib % 2 == 0 else (OLD_LV_GLYPH[byte] >> 4)
            self.assertNotEqual(old_val, 5, f"nibble {nib} was already ink in « Lv »")

    def test_period_dot_has_full_drop_shadow(self):
        # Issue #138 follow-up: the period dot must cast a FULL grey drop-shadow
        # (value 0xA = both sub-pixels grey) immediately below it — nibble 44
        # (local col 3, row 11) — not value 0x8 (left sub-pixel grey, right
        # sub-pixel transparent), which rendered as an incomplete half-shadow.
        nib = 44
        byte = nib // 2
        val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
        self.assertEqual(val, 0xA, "period dot must have a full grey drop-shadow (value 0xA)")
        old = (OLD_ND_GLYPH_NOSHADOW[byte] & 0xF) if nib % 2 == 0 else (OLD_ND_GLYPH_NOSHADOW[byte] >> 4)
        self.assertEqual(old, 5, "shadow-less « N. » had white ink (not shadow) there")
        half = (OLD_ND_GLYPH_HALF_SHADOW[byte] & 0xF) if nib % 2 == 0 else (OLD_ND_GLYPH_HALF_SHADOW[byte] >> 4)
        self.assertEqual(half, 8, "the #138 fix had only a half shadow (value 8) there")

    def test_period_dot_widened_to_match_shadow(self):
        # Issue #138 second follow-up: the dot's own white ink must be as wide
        # as its shadow — nibble 37/41's dot-facing sub-pixel (the high nibble
        # of byte 18/20) must be white (value 4: white+transparent), not grey
        # (value 8: grey+transparent, which read as part of the shadow instead
        # of the dot and left the dot looking one pixel narrower).
        for nib in (37, 41):
            byte = nib // 2
            val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
            self.assertEqual(val, 4, f"nibble {nib} should be white+transparent (4) to widen the dot")
            narrow = (OLD_ND_GLYPH_NARROW_DOT[byte] & 0xF) if nib % 2 == 0 else (OLD_ND_GLYPH_NARROW_DOT[byte] >> 4)
            self.assertEqual(narrow, 8, f"nibble {nib} was grey+transparent (8) before this fix")

    def test_no_ink_below_row_11(self):
        # Issue #138: nothing beyond nibble row 11 (nibble index >= 48) may
        # carry white(5) or shadow(8/0xA) ink — that row overflows the in-battle
        # level-up box's clipped glyph area and bleeds onto its border strip.
        for nib in range(48, 64):
            byte = nib // 2
            val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
            self.assertNotIn(val, (5, 8, 0xA), f"nibble {nib} (row {nib // 4}) must not carry ink/shadow")

    def test_noshadow_differs_only_by_shadow_pixel_and_dot_width(self):
        diffs = [i for i in range(GLYPH_SIZE) if NEW_ND_GLYPH[i] != OLD_ND_GLYPH_NOSHADOW[i]]
        self.assertEqual(
            diffs, [18, 20, 22],
            "must only touch the dot-widening bytes (18/20) and the shadow byte (22)",
        )

    def test_row12_overflow_glyph_differs_only_by_shadow_relocation_and_dot_width(self):
        diffs = [i for i in range(GLYPH_SIZE) if NEW_ND_GLYPH[i] != OLD_ND_GLYPH_ROW12_OVERFLOW[i]]
        self.assertEqual(
            sorted(diffs), [18, 20, 22, 24],
            "fix must only widen the dot (18/20) and move the shadow from byte 24 (row 12) to byte 22 (row 11)",
        )

    def test_half_shadow_glyph_differs_only_by_shadow_completeness_and_dot_width(self):
        # Issue #138 follow-up + second follow-up: this fix must only complete
        # the row-11 shadow (0x8 -> 0xA in byte 22) and widen the dot (18/20),
        # not touch anything else already fixed by #138.
        diffs = [i for i in range(GLYPH_SIZE) if NEW_ND_GLYPH[i] != OLD_ND_GLYPH_HALF_SHADOW[i]]
        self.assertEqual(diffs, [18, 20, 22], "fix must only touch the dot-width and shadow bytes")

    def test_narrow_dot_glyph_differs_only_by_dot_width(self):
        # Issue #138 second follow-up: this fix must only widen the dot
        # (bytes 18/20), the shadow (byte 22) was already correct.
        diffs = [i for i in range(GLYPH_SIZE) if NEW_ND_GLYPH[i] != OLD_ND_GLYPH_NARROW_DOT[i]]
        self.assertEqual(diffs, [18, 20], "fix must only touch the bytes holding the dot's width")


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

    def test_repatches_shadowless_nd_to_shadowed(self):
        # An already-built ROM carrying the old shadow-less « N. » must converge
        # to the shadowed glyph without a full rebuild (issue #104).
        rom = _fake_rom(OLD_ND_GLYPH_NOSHADOW)
        p = Path("/tmp/_lvtest_noshadow.gba")
        p.write_bytes(rom)
        self.assertEqual(apply_patch(p), 1)
        self.assertEqual(p.read_bytes()[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE],
                         NEW_ND_GLYPH)

    def test_repatches_row12_overflow_nd_to_inbounds(self):
        # An already-built ROM carrying #104's row-12-overflow « N. » must
        # converge to the in-bounds glyph without a full rebuild (issue #138).
        rom = _fake_rom(OLD_ND_GLYPH_ROW12_OVERFLOW)
        p = Path("/tmp/_lvtest_row12overflow.gba")
        p.write_bytes(rom)
        self.assertEqual(apply_patch(p), 1)
        self.assertEqual(p.read_bytes()[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE],
                         NEW_ND_GLYPH)

    def test_repatches_half_shadow_nd_to_full_shadow(self):
        # An already-built ROM carrying #138's half-shadow « N. » must converge
        # to the full-shadow glyph without a full rebuild (issue #138 follow-up).
        rom = _fake_rom(OLD_ND_GLYPH_HALF_SHADOW)
        p = Path("/tmp/_lvtest_halfshadow.gba")
        p.write_bytes(rom)
        self.assertEqual(apply_patch(p), 1)
        self.assertEqual(p.read_bytes()[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE],
                         NEW_ND_GLYPH)

    def test_repatches_narrow_dot_nd_to_wide_dot(self):
        # An already-built ROM carrying the full-shadow-but-narrow-dot « N. »
        # must converge to the wide-dot glyph without a full rebuild (issue
        # #138 second follow-up).
        rom = _fake_rom(OLD_ND_GLYPH_NARROW_DOT)
        p = Path("/tmp/_lvtest_narrowdot.gba")
        p.write_bytes(rom)
        self.assertEqual(apply_patch(p), 1)
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
