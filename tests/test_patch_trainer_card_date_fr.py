import pytest

pytestmark = pytest.mark.rom

import struct
import unittest
from pathlib import Path

import pytest

from languages.fr.patches.trainer_card_date import (
    BIRTHDAY_FIRST_COMPONENT_FILE,
    BIRTHDAY_FIRST_COMPONENT_NEW,
    BIRTHDAY_FIRST_COMPONENT_OLD,
    BIRTHDAY_LAST_COMPONENT_FILE,
    BIRTHDAY_LAST_COMPONENT_NEW,
    BIRTHDAY_LAST_COMPONENT_OLD,
    BLOCK_FILE,
    BLOCK_LEN,
    BUILDER_FILE,
    MONTH_PTR_TABLE_FILE,
    apply,
    assemble_builder,
    assemble_redirect,
)

ROM = Path("output/roms/GenedRom-fr.gba")


class TestAssembly(unittest.TestCase):
    def test_redirect_is_block_length(self):
        self.assertEqual(len(assemble_redirect()), BLOCK_LEN)

    def test_builder_word_aligned_and_reasonable(self):
        b = assemble_builder()
        self.assertEqual(len(b) % 4, 0)
        self.assertLess(len(b), 0x60)          # comfortably inside free space
        self.assertEqual(b[:2], b"\x70\xb5")   # push {r4,r5,r6,lr}

    def test_redirect_calls_veneer_and_branches_home(self):
        r = assemble_redirect()
        self.assertEqual(r[:2], b"\x3f\x4f")   # ldr r7,[pc,#0xfc]  (dest)
        self.assertEqual(r[2:4], b"\x05\x98")  # ldr r0,[sp,#0x14]  (month idx)
        self.assertEqual(r[6:10], b"\x00\xf0\x46\xfa")  # bl 0x9ED920C (bx r3)


class TestApplySynthetic(unittest.TestCase):
    def _synthetic(self):
        size = 0x2000000  # full 32 MB address space (month table lives near the top)
        data = bytearray(b"\x00" * size)
        # original inline block signature
        data[BLOCK_FILE:BLOCK_FILE + BLOCK_LEN] = (
            b"\x05\x9b" + b"\xaa" * (BLOCK_LEN - 2)
        )
        # free space for the builder
        data[BUILDER_FILE:BUILDER_FILE + 0x60] = b"\xff" * 0x60
        # original birthday assembly loads (year, month, day)
        data[BIRTHDAY_FIRST_COMPONENT_FILE:
             BIRTHDAY_FIRST_COMPONENT_FILE + 2] = BIRTHDAY_FIRST_COMPONENT_OLD
        data[BIRTHDAY_LAST_COMPONENT_FILE:
             BIRTHDAY_LAST_COMPONENT_FILE + 2] = BIRTHDAY_LAST_COMPONENT_OLD
        # a month pointer table pointing at cells, one with a trailing space
        cell_a = 0x1FE6D00
        cell_b = 0x1FE6D10
        data[cell_a:cell_a + 6] = b"\xc7\xd5\xe6\xe7\x00\xff"   # "Mars " (space)
        data[cell_b:cell_b + 6] = b"\xc4\xd5\xe2\xea\xad\xff"   # "Janv." (dot)
        for k in range(12):
            ptr = cell_a if k % 2 == 0 else cell_b
            data[MONTH_PTR_TABLE_FILE + 4 * k:
                 MONTH_PTR_TABLE_FILE + 4 * k + 4] = struct.pack(
                "<I", 0x08000000 + ptr)
        return data, cell_a, cell_b

    def test_apply_and_idempotent(self):
        data, cell_a, cell_b = self._synthetic()
        n = apply(data)
        self.assertGreater(n, 0)
        # redirect written
        self.assertEqual(bytes(data[BLOCK_FILE:BLOCK_FILE + BLOCK_LEN]),
                         assemble_redirect())
        # builder written
        self.assertEqual(bytes(data[BUILDER_FILE:BUILDER_FILE + len(assemble_builder())]),
                         assemble_builder())
        # trailing space trimmed on "Mars " -> terminator moved back
        self.assertEqual(data[cell_a + 4], 0xFF)
        # dot cell untouched
        self.assertEqual(data[cell_b + 4], 0xAD)
        # birthday components now render day/month/year
        self.assertEqual(
            bytes(data[BIRTHDAY_FIRST_COMPONENT_FILE:
                       BIRTHDAY_FIRST_COMPONENT_FILE + 2]),
            BIRTHDAY_FIRST_COMPONENT_NEW,
        )
        self.assertEqual(
            bytes(data[BIRTHDAY_LAST_COMPONENT_FILE:
                       BIRTHDAY_LAST_COMPONENT_FILE + 2]),
            BIRTHDAY_LAST_COMPONENT_NEW,
        )
        # idempotent
        self.assertEqual(apply(data), 0)

    def test_rejects_wrong_block(self):
        data, *_ = self._synthetic()
        data[BLOCK_FILE:BLOCK_FILE + 2] = b"\xde\xad"
        with self.assertRaises(ValueError):
            apply(data)


@pytest.mark.rom
@unittest.skipUnless(ROM.exists(), "built FR ROM not present")
class TestBuiltRom(unittest.TestCase):
    def test_committed_rom_has_french_date_builder(self):
        data = ROM.read_bytes()
        # Birthday is assembled as day/month/year, not the English Y/M/D.
        self.assertEqual(
            data[BIRTHDAY_FIRST_COMPONENT_FILE:BIRTHDAY_FIRST_COMPONENT_FILE + 2],
            BIRTHDAY_FIRST_COMPONENT_NEW,
        )
        self.assertEqual(
            data[BIRTHDAY_LAST_COMPONENT_FILE:BIRTHDAY_LAST_COMPONENT_FILE + 2],
            BIRTHDAY_LAST_COMPONENT_NEW,
        )
        # the inline block must have been redirected (starts ldr r7,[pc,#0xfc])
        self.assertEqual(data[BLOCK_FILE:BLOCK_FILE + 2], b"\x3f\x4f")
        # builder present in free space
        self.assertEqual(data[BUILDER_FILE:BUILDER_FILE + 2], b"\x70\xb5")
        # SP_STR (" ") + all five pool words present just after the code
        self.assertIn(struct.pack("<I", 0x02021D18),
                      data[BUILDER_FILE:BUILDER_FILE + 0x60])  # dest buffer
        # no month cell keeps a trailing space byte before its terminator
        for k in range(12):
            ptr = struct.unpack("<I", data[MONTH_PTR_TABLE_FILE + 4 * k:
                                           MONTH_PTR_TABLE_FILE + 4 * k + 4])[0]
            off = ptr - 0x08000000
            i = off
            while data[i] != 0xFF:
                i += 1
            self.assertNotEqual(data[i - 1], 0x00,
                                f"month cell {k+1} still has trailing space")


if __name__ == "__main__":
    unittest.main()
