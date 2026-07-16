"""Regression tests for the FR party-menu « Annuler » → « Sortir » button patch.

The party list's persistent bottom-right button is drawn from the *shared*
``gText_Cancel`` string, so the fix must retarget only the party menu's own code
literal at ROM 0x1211E8 (leaving every other « Annuler » untouched) and point it at a
dedicated « Sortir » string written into the ROM's 0xFF tail padding.
"""

import struct
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.party_cancel_button import (
    ANNULER_BYTES,
    PARTY_CANCEL_PTR,
    SORTIR_BYTES,
    SORTIR_CPU_ADDR,
    SORTIR_STR_OFFSET,
    apply,
)

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"
ROM_SIZE = 0x2000000
ANNULER_AT = 0xE58DB2  # where the shared "Annuler" string lives in the built ROM


def _fake_rom() -> bytearray:
    rom = bytearray(ROM_SIZE)
    rom[0xB2] = 0x96
    # shared "Annuler" string + the party literal pointing at it
    rom[ANNULER_AT:ANNULER_AT + len(ANNULER_BYTES)] = ANNULER_BYTES
    struct.pack_into("<I", rom, PARTY_CANCEL_PTR, 0x08000000 + ANNULER_AT)
    # free 0xFF tail padding for the "Sortir" string
    rom[SORTIR_STR_OFFSET:SORTIR_STR_OFFSET + 16] = b"\xff" * 16
    return rom


class TestByteConstants(unittest.TestCase):
    def test_strings_terminated(self):
        self.assertEqual(ANNULER_BYTES[-1], 0xFF)
        self.assertEqual(SORTIR_BYTES[-1], 0xFF)

    def test_sortir_shorter_than_annuler(self):
        # "Sortir" (6) fits wherever "Annuler" (7) did.
        self.assertLess(len(SORTIR_BYTES), len(ANNULER_BYTES))


class TestApply(unittest.TestCase):
    def test_repoints_literal_and_writes_sortir(self):
        rom = _fake_rom()
        self.assertEqual(apply(rom), 1)
        ptr = struct.unpack_from("<I", rom, PARTY_CANCEL_PTR)[0]
        self.assertEqual(ptr, SORTIR_CPU_ADDR)
        self.assertEqual(
            bytes(rom[SORTIR_STR_OFFSET:SORTIR_STR_OFFSET + len(SORTIR_BYTES)]),
            SORTIR_BYTES,
        )

    def test_shared_annuler_string_untouched(self):
        rom = _fake_rom()
        apply(rom)
        self.assertEqual(
            bytes(rom[ANNULER_AT:ANNULER_AT + len(ANNULER_BYTES)]), ANNULER_BYTES
        )

    def test_idempotent(self):
        rom = _fake_rom()
        self.assertEqual(apply(rom), 1)
        self.assertEqual(apply(rom), 0)  # already « Sortir » — no-op

    def test_skips_unexpected_target(self):
        rom = _fake_rom()
        # literal points at something that is not "Annuler" -> skip, leave untouched
        struct.pack_into("<I", rom, PARTY_CANCEL_PTR, 0x08123456)
        self.assertEqual(apply(rom), 0)
        self.assertEqual(struct.unpack_from("<I", rom, PARTY_CANCEL_PTR)[0], 0x08123456)

    def test_skips_when_tail_not_free(self):
        rom = _fake_rom()
        rom[SORTIR_STR_OFFSET] = 0x42  # tail slot already used -> refuse to clobber
        self.assertEqual(apply(rom), 0)
        # literal must remain pointing at the shared "Annuler"
        self.assertEqual(
            struct.unpack_from("<I", rom, PARTY_CANCEL_PTR)[0], 0x08000000 + ANNULER_AT
        )


@pytest.mark.skipif(not BUILT_FR_ROM.exists(), reason="built FR ROM not present")
class TestBuiltRom(unittest.TestCase):
    def test_party_button_points_at_sortir(self):
        rom = BUILT_FR_ROM.read_bytes()
        ptr = struct.unpack_from("<I", rom, PARTY_CANCEL_PTR)[0]
        self.assertTrue(0x08000000 <= ptr < 0x0A000000, f"bad ptr 0x{ptr:08X}")
        off = ptr - 0x08000000
        self.assertEqual(
            rom[off:off + len(SORTIR_BYTES)], SORTIR_BYTES,
            "party menu bottom button must render « Sortir »",
        )


if __name__ == "__main__":
    unittest.main()
