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

Issue #138 second follow-up: misdiagnosed at the time as the dot's own ink
being one pixel narrow; nibble 37/41 (local col 2 — the real « N » letter's
own antialiasing column, immediately left of the dot) was turned white
(value 4) in rows 9-10. That broke the column's continuity with rows 4-8
(always grey there), which is what the next follow-up reported as "the
bottom of the N is wrong".

Issue #138 third follow-up: nibble 37/41 goes back to grey (value 8's left
sub-pixel, restoring the « N »'s antialiasing column and fixing the "bottom
of N" regression), and its previously-transparent right sub-pixel — along
with row 11's same right sub-pixel (nibble 45) — becomes grey too (0x8 →
0xA), closing the one remaining gap beside the dot without touching the
dot's own ink (nibbles 36/40) or its shadow (nibble 44).

Issue #138 fourth follow-up (reporter: "so close! the grey pixels are on the
wrong side"): the third follow-up's right sub-pixel change shaded local col 2
(nibbles 37/41/45), which sits immediately *left* of the dot's own ink (local
col 3) — the wrong side. The glyph is a fixed 8-physical-pixel-wide tile and
the dot's ink already occupies its last two columns, flush against the right
edge, so there is no column *inside this glyph* to the dot's right. This
reverts nibble 37/41/45's right sub-pixel back to transparent (0xA -> 0x8),
removing the confirmed-wrong placement.

Issue #138 fifth follow-up (reporter's own pixel-grid mockup): rather than
touch a neighbouring codepoint, the dot's own ink shifts one physical pixel
left — nibble 36/40's right sub-pixel turns from white to grey (its former
rightmost ink pixel becomes a shadow pixel) while nibble 37/41's right
sub-pixel turns from transparent to white (extending the ink left by one
pixel). Row 11 (the shadow row) gains a matching grey right sub-pixel at
nibble 45, so the shadow wraps the dot's new position on both its right and
its bottom. Nibble 37/41/45's left sub-pixel (the real « N »'s own
antialiasing column) and nibble 44 (the already-full shadow below the dot)
are untouched.
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
    OLD_ND_GLYPH_ANTIALIAS_WRONG_SIDE,
    OLD_ND_GLYPH_HALF_SHADOW,
    OLD_ND_GLYPH_MISWIDENED_DOT,
    OLD_ND_GLYPH_NOSHADOW,
    OLD_ND_GLYPH_ROW12_OVERFLOW,
    OLD_ND_GLYPH_SHADOW_BELOW_ONLY,
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

    def test_period_dot_spans_nibble_36_left_and_nibble_37_right_subpixels(self):
        # Issue #138 fifth follow-up: the dot's white ink is one physical pixel
        # left of where it used to be. Nibble 36/40 (local col 3) now carries
        # white only on its LEFT sub-pixel (value 6 = white+grey, not the old
        # solid 5 = white+white) and nibble 37/41 (local col 2) now carries
        # white on its RIGHT sub-pixel (value 9 = grey+white, not the old 8 =
        # grey+transparent) — together the two white sub-pixels are still
        # exactly 2 pixels wide, just shifted one pixel left.
        for nib in (36, 40):
            byte = nib // 2
            val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
            self.assertEqual(val, 6, f"nibble {nib} should be white+grey (6)")
        for nib in (37, 41):
            byte = nib // 2
            val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
            self.assertEqual(val, 9, f"nibble {nib} should be grey+white (9)")

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

    def test_n_antialiasing_column_left_subpixel_stays_grey_not_widened_white(self):
        # Issue #138 third follow-up: nibble 37/41/45 (local col 2) is the real
        # « N » letter's own antialiasing column, immediately left of the dot
        # (col 3) — not part of the dot. Its LEFT sub-pixel (high 2 bits) must
        # stay grey (not white — the second follow-up's mistake, which broke
        # the column's continuity and was reported as "the bottom of the N is
        # wrong") in every row of the column, including the fifth follow-up's
        # revised rows 9-10 (now 9 = grey+white, not 4 = white+transparent).
        for nib in (37, 41, 45):
            byte = nib // 2
            val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
            left_subpixel = (val >> 2) & 3
            self.assertEqual(left_subpixel, 2, f"nibble {nib}'s left sub-pixel should stay grey")
            miswidened = (OLD_ND_GLYPH_MISWIDENED_DOT[byte] & 0xF) if nib % 2 == 0 else (OLD_ND_GLYPH_MISWIDENED_DOT[byte] >> 4)
            if nib in (37, 41):
                self.assertEqual(miswidened, 4, f"nibble {nib} was wrongly white+transparent (4) before this fix")

    def test_n_antialiasing_column_right_subpixel_now_shaded_to_match_shifted_dot(self):
        # Issue #138 fifth follow-up (reporter's own pixel-grid mockup): with
        # the dot shifted one pixel left, nibble 37/41's right sub-pixel
        # becomes the dot's own new ink (white, not transparent) and nibble
        # 45's right sub-pixel becomes shadow (grey, not transparent) so the
        # shadow row lines up under the dot's new position. This supersedes
        # the fourth follow-up, which kept all three transparent because the
        # dot was still flush against the tile's right edge back then.
        for nib in (37, 41):
            byte = nib // 2
            val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
            self.assertEqual(val & 3, 1, f"nibble {nib}'s right sub-pixel should now be white (dot ink)")
        nib = 45
        byte = nib // 2
        val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
        self.assertEqual(val & 3, 2, "nibble 45's right sub-pixel should now be grey (shadow)")
        wrong_side = (OLD_ND_GLYPH_ANTIALIAS_WRONG_SIDE[byte] & 0xF) if nib % 2 == 0 else (OLD_ND_GLYPH_ANTIALIAS_WRONG_SIDE[byte] >> 4)
        self.assertEqual(wrong_side, 0xA, "nibble 45 was already grey+grey (0xA) in the wrong-side glyph too")

    def test_no_ink_below_row_11(self):
        # Issue #138: nothing beyond nibble row 11 (nibble index >= 48) may
        # carry white(5) or shadow(8/0xA) ink — that row overflows the in-battle
        # level-up box's clipped glyph area and bleeds onto its border strip.
        for nib in range(48, 64):
            byte = nib // 2
            val = (NEW_ND_GLYPH[byte] & 0xF) if nib % 2 == 0 else (NEW_ND_GLYPH[byte] >> 4)
            self.assertNotIn(val, (5, 8, 0xA), f"nibble {nib} (row {nib // 4}) must not carry ink/shadow")

    def test_noshadow_differs_only_by_dot_shadow_and_column_bytes(self):
        # These bytes (18/20/22) now also carry the fifth follow-up's dot
        # shift, on top of the original shadow-completion diff.
        diffs = [i for i in range(GLYPH_SIZE) if NEW_ND_GLYPH[i] != OLD_ND_GLYPH_NOSHADOW[i]]
        self.assertEqual(diffs, [18, 20, 22], "must only touch the dot/shadow/column bytes")

    def test_row12_overflow_glyph_differs_only_by_dot_shadow_and_relocation(self):
        diffs = [i for i in range(GLYPH_SIZE) if NEW_ND_GLYPH[i] != OLD_ND_GLYPH_ROW12_OVERFLOW[i]]
        self.assertEqual(
            sorted(diffs), [18, 20, 22, 24],
            "fix must only touch the dot/shadow/column bytes and move the shadow from byte 24 (row 12)",
        )

    def test_half_shadow_glyph_differs_only_by_dot_shadow_and_column_bytes(self):
        # Issue #138 follow-up: originally this fix only completed the row-11
        # shadow (byte 22); the fifth follow-up's dot shift now also touches
        # bytes 18/20 on top of that.
        diffs = [i for i in range(GLYPH_SIZE) if NEW_ND_GLYPH[i] != OLD_ND_GLYPH_HALF_SHADOW[i]]
        self.assertEqual(diffs, [18, 20, 22], "fix must only touch the dot/shadow/column bytes")

    def test_miswidened_dot_glyph_differs_by_antialiasing_column_and_shadow_bytes(self):
        # Issue #138 second follow-up: originally re-patching this glyph only
        # reverted the antialiasing column's left sub-pixel (bytes 18/20); the
        # fifth follow-up's dot shift now also touches byte 22 (the shadow row).
        diffs = [i for i in range(GLYPH_SIZE) if NEW_ND_GLYPH[i] != OLD_ND_GLYPH_MISWIDENED_DOT[i]]
        self.assertEqual(diffs, [18, 20, 22], "fix must only touch the antialiasing-column and shadow bytes")

    def test_antialias_wrong_side_glyph_differs_only_by_column_bytes(self):
        # Issue #138 fourth follow-up: re-patching the wrongly-shaded glyph
        # must only revert the antialiasing column's bytes (18/20) — byte 22
        # already matches NEW_ND_GLYPH since both glyphs have a full row-11
        # shadow (0xAA).
        diffs = [i for i in range(GLYPH_SIZE) if NEW_ND_GLYPH[i] != OLD_ND_GLYPH_ANTIALIAS_WRONG_SIDE[i]]
        self.assertEqual(diffs, [18, 20], "fix must only touch the antialiasing-column bytes")

    def test_shadow_below_only_glyph_differs_only_by_dot_shift_and_column_bytes(self):
        # Issue #138 fourth follow-up's own fix, now superseded by the fifth:
        # re-patching the flush-right dot (shadow below only, no shadow to its
        # right) must only touch the dot/antialiasing-column/shadow bytes
        # (18/20/22) to shift the dot one pixel left and add the right-side
        # shadow.
        diffs = [i for i in range(GLYPH_SIZE) if NEW_ND_GLYPH[i] != OLD_ND_GLYPH_SHADOW_BELOW_ONLY[i]]
        self.assertEqual(diffs, [18, 20, 22], "fix must only touch the dot/shadow/column bytes")


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

    def test_repatches_miswidened_dot_nd_to_gap_free(self):
        # An already-built ROM carrying the #138 second follow-up's mistake
        # (antialiasing column wrongly turned white) must converge to the
        # corrected glyph without a full rebuild (issue #138 third follow-up).
        rom = _fake_rom(OLD_ND_GLYPH_MISWIDENED_DOT)
        p = Path("/tmp/_lvtest_miswidened.gba")
        p.write_bytes(rom)
        self.assertEqual(apply_patch(p), 1)
        self.assertEqual(p.read_bytes()[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE],
                         NEW_ND_GLYPH)

    def test_repatches_antialias_wrong_side_to_correct_side(self):
        # An already-built ROM carrying the #138 third follow-up's mistake
        # (antialiasing column shaded on the dot's wrong/left side) must
        # converge to the corrected glyph without a full rebuild (issue #138
        # fourth follow-up).
        rom = _fake_rom(OLD_ND_GLYPH_ANTIALIAS_WRONG_SIDE)
        p = Path("/tmp/_lvtest_wrongside.gba")
        p.write_bytes(rom)
        self.assertEqual(apply_patch(p), 1)
        self.assertEqual(p.read_bytes()[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE],
                         NEW_ND_GLYPH)

    def test_repatches_shadow_below_only_to_diagonal_shadow(self):
        # An already-built ROM carrying the #138 fourth follow-up's fix (dot
        # flush against the tile's right edge, shadow below only) must
        # converge to the shifted-dot glyph with a diagonal (right + below)
        # shadow without a full rebuild (issue #138 fifth follow-up).
        rom = _fake_rom(OLD_ND_GLYPH_SHADOW_BELOW_ONLY)
        p = Path("/tmp/_lvtest_shadowbelowonly.gba")
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
