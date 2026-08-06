"""Regression tests for the FR « Lv » → « N. » string patch.

The Résumé header uses literal « N. », while the ``gText_Lv`` copy shared by
the party list and battle healthbox must remain the compact extra-symbol #5
(``F9 05``). Its translated 9 px glyph is the only form that fits the battle
window without clipping the final digit's shadow (issue #175).
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.summary_lv_labels import (
    COMPACT_LV_STRING_OFFSET,
    LV_SYMBOL,
    ND_TEXT,
    _patch_header,
    _patch_memos,
)

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"
GBA_BASE = 0x08000000


def _rom_with_string(str_off: int, body: bytes, preceding: int = 0xFF) -> bytearray:
    """Build a tiny ROM holding *body* at *str_off* with a word-aligned pointer.

    ``preceding`` is the byte placed just before the string (0xFF for a normal
    bounded string, 0x08 to mimic the party copy at 0x26051C).
    """
    rom = bytearray(0x100)
    rom[0xB2] = 0x96
    if str_off > 0:
        rom[str_off - 1] = preceding
    rom[str_off:str_off + len(body)] = body
    # word-aligned live pointer to the string start, placed clear of the body
    ptr_at = 0xF0
    rom[ptr_at:ptr_at + 4] = (GBA_BASE + str_off).to_bytes(4, "little")
    return rom


class TestPatchHeader(unittest.TestCase):
    def test_patches_ff_bounded_copy(self):
        # gText_Lv style: preceded by FF (like 0x416223)
        off = 0x40
        rom = _rom_with_string(off, LV_SYMBOL + b"\xff", preceding=0xFF)
        self.assertEqual(_patch_header(rom), 1)
        self.assertEqual(bytes(rom[off:off + 2]), ND_TEXT)

    def test_patches_non_ff_preceded_copy(self):
        # party copy: preceded by 0x08 (like 0x26051C) — the previously-missed case
        off = 0x40
        rom = _rom_with_string(off, LV_SYMBOL + b"\xff", preceding=0x08)
        self.assertEqual(_patch_header(rom), 1)
        self.assertEqual(bytes(rom[off:off + 2]), ND_TEXT)

    def test_idempotent_on_already_nd(self):
        off = 0x40
        rom = _rom_with_string(off, ND_TEXT + b"\xff", preceding=0x08)
        self.assertEqual(_patch_header(rom), 0)
        self.assertEqual(bytes(rom[off:off + 2]), ND_TEXT)

    def test_skips_unpointed_copy(self):
        # F9 05 FF with NO live pointer (e.g. coincidental code bytes) is left alone
        off = 0x40
        rom = _rom_with_string(off, LV_SYMBOL + b"\xff", preceding=0x08)
        # clobber the pointer so the string is dead
        for i in range(len(rom) - 4):
            if rom[i:i + 4] == (GBA_BASE + off).to_bytes(4, "little"):
                rom[i:i + 4] = b"\x00\x00\x00\x00"
        self.assertEqual(_patch_header(rom), 0)
        self.assertEqual(bytes(rom[off:off + 2]), LV_SYMBOL)

    def test_restores_compact_shared_party_battle_copy(self):
        rom = bytearray(COMPACT_LV_STRING_OFFSET + 3)
        rom[0xB2] = 0x96
        rom[COMPACT_LV_STRING_OFFSET:COMPACT_LV_STRING_OFFSET + 3] = ND_TEXT + b"\xff"

        self.assertEqual(_patch_header(rom), 1)
        self.assertEqual(
            bytes(rom[COMPACT_LV_STRING_OFFSET:COMPACT_LV_STRING_OFFSET + 3]),
            LV_SYMBOL + b"\xff",
        )
        self.assertEqual(_patch_header(rom), 0)

    def test_rejects_unknown_shared_party_battle_copy(self):
        rom = bytearray(COMPACT_LV_STRING_OFFSET + 3)
        rom[0xB2] = 0x96
        rom[COMPACT_LV_STRING_OFFSET:COMPACT_LV_STRING_OFFSET + 3] = b"\x00\x00\xff"

        with self.assertRaisesRegex(ValueError, "unexpected shared gText_Lv"):
            _patch_header(rom)


class TestPatchMemos(unittest.TestCase):
    def test_rewrites_lv_before_dynamic_level_and_moves_space_to_end(self):
        # F9 05 00 F7 01 AD FF = Lv-icon + space + level-ctrl(param 1) + « . » + terminator
        rom = bytearray(0x100)
        rom[0xB2] = 0x96
        rom[0x40:0x47] = LV_SYMBOL + b"\x00\xf7\x01\xad\xff"
        self.assertEqual(_patch_memos(rom), 1)
        # issue #66: no space right after « N. » — it moved past the level
        # number and trailing period, to just before the terminator.
        self.assertEqual(bytes(rom[0x40:0x47]), ND_TEXT + b"\xf7\x01\xad\x00\xff")

    def test_idempotent_on_already_fixed_memo(self):
        rom = bytearray(0x100)
        rom[0xB2] = 0x96
        rom[0x40:0x47] = ND_TEXT + b"\xf7\x01\xad\x00\xff"
        self.assertEqual(_patch_memos(rom), 0)
        self.assertEqual(bytes(rom[0x40:0x47]), ND_TEXT + b"\xf7\x01\xad\x00\xff")

    def test_fixes_legacy_nd_text_with_leading_space(self):
        # a ROM already carrying the old B-508 fix (icon->N. but space untouched)
        rom = bytearray(0x100)
        rom[0xB2] = 0x96
        rom[0x40:0x47] = ND_TEXT + b"\x00\xf7\x01\xad\xff"
        self.assertEqual(_patch_memos(rom), 1)
        self.assertEqual(bytes(rom[0x40:0x47]), ND_TEXT + b"\xf7\x01\xad\x00\xff")


@pytest.mark.rom
class TestBuiltFrRomPartyString(unittest.TestCase):
    """The shipped FR ROM must use the compact translated glyph in battle."""

    def test_party_battle_lv_string_is_compact(self):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        rom = BUILT_FR_ROM.read_bytes()
        self.assertEqual(
            rom[COMPACT_LV_STRING_OFFSET:COMPACT_LV_STRING_OFFSET + 3],
            LV_SYMBOL + b"\xff",
            "built FR ROM does not use the compact party/battle level glyph",
        )


if __name__ == "__main__":
    unittest.main()
