"""Regression tests for the FR « Lv » → « N. » string patch (summary + party).

The « Lv » level prefix on the Résumé header AND the party list is the FRLG
extra-symbol #5 (bytes ``F9 05``) inside isolated pointed ``gText_Lv`` strings.
``_patch_header`` must rewrite every such pointed ``F9 05 FF`` string — including
the party copy at 0x26051C, which is preceded by ``0x08`` (not ``FF``) and was
skipped by the original ``FF F9 05 FF`` filter (leaving the party list « Lv »).
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.summary_lv_labels import (
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


class TestPatchMemos(unittest.TestCase):
    def test_rewrites_lv_before_dynamic_level(self):
        rom = bytearray(0x100)
        rom[0xB2] = 0x96
        rom[0x40:0x44] = LV_SYMBOL + b"\x00\xf7"  # F9 05 00 F7
        self.assertEqual(_patch_memos(rom), 1)
        self.assertEqual(bytes(rom[0x40:0x42]), ND_TEXT)


@pytest.mark.rom
class TestBuiltFrRomPartyString(unittest.TestCase):
    """The shipped FR ROM must carry « N. » (C8 AD) at the party gText_Lv copy."""

    def test_party_lv_string_is_nd(self):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        rom = BUILT_FR_ROM.read_bytes()
        self.assertEqual(
            rom[0x26051C:0x26051F], ND_TEXT + b"\xff",
            "built FR ROM still shows « Lv » in the party list (0x26051C not patched)",
        )


if __name__ == "__main__":
    unittest.main()
