import pytest

pytestmark = pytest.mark.rom

import unittest
from pathlib import Path
import re

import pytest

from languages.fr.patches.money_amount_order import (
    ENGLISH_ORDER,
    FRENCH_ORDER,
    TEMPLATE_OFFSET,
    apply,
    apply_inline_money_orders,
)

ROM = Path("output/roms/GenedRom-fr.gba")
COMBINED = Path("languages/fr/combined_fr.txt")

MONEY_DIALOGUE_OFFSETS = {
    0x1A6196,
    0x1BFA3B,
    0x41678E,
    0x416936,
    0x416959,
    0x7E842C,
    0x7EBF53,
    0x893A1F,
    0xA4E00D,
    0x1F2050C,
    0x1F278E7,
    0x1F2C555,
    0x1F6C7EB,
}


def _combined_entries() -> dict[int, str]:
    entries = {}
    for line in COMBINED.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^0x([0-9A-Fa-f]+): (.*)$", line)
        if match:
            entries[int(match.group(1), 16)] = match.group(2)
    return entries


def _synthetic() -> bytearray:
    return bytearray(b"\xff" * (TEMPLATE_OFFSET + 16))


class TestApplySynthetic(unittest.TestCase):
    def test_apply_swaps_symbol_after_amount(self):
        data = _synthetic()
        data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(ENGLISH_ORDER)] = ENGLISH_ORDER
        n = apply(data)
        self.assertEqual(n, 1)
        self.assertEqual(
            bytes(data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)]),
            FRENCH_ORDER,
        )

    def test_idempotent(self):
        data = _synthetic()
        data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)] = FRENCH_ORDER
        self.assertEqual(apply(data), 0)

    def test_rejects_unexpected_bytes(self):
        data = _synthetic()
        data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + 4] = b"\xde\xad\xbe\xef"
        with self.assertRaises(ValueError):
            apply(data)

    def test_inline_money_orders_keep_their_formatting(self):
        data = _synthetic()
        data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)] = FRENCH_ORDER
        start = 8
        data[start:start + 8] = bytes(
            [0xB7, 0xFC, 0x01, 0x06, 0xFD, 0x03, 0xFC, 0x01]
        )
        data[start + 8] = 0x08
        self.assertEqual(apply_inline_money_orders(data), 1)
        self.assertEqual(
            data[start:start + 9],
            bytes([0xFC, 0x01, 0x06, 0xFD, 0x03, 0xB7, 0xFC, 0x01, 0x08]),
        )
        self.assertEqual(apply_inline_money_orders(data), 0)

    def test_money_dialogues_place_the_symbol_after_the_variable(self):
        entries = _combined_entries()
        self.assertTrue(MONEY_DIALOGUE_OFFSETS.issubset(entries))
        for offset in MONEY_DIALOGUE_OFFSETS:
            with self.subTest(offset=f"0x{offset:X}"):
                self.assertNotRegex(entries[offset], r"¥\{STR_VAR_\d+\}")
                self.assertRegex(entries[offset], r"\{STR_VAR_\d+\}¥")


@pytest.mark.rom
@unittest.skipUnless(ROM.exists(), "built FR ROM not present")
class TestBuiltRom(unittest.TestCase):
    def test_committed_rom_has_amount_before_symbol(self):
        data = ROM.read_bytes()
        self.assertEqual(
            data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)],
            FRENCH_ORDER,
        )
        self.assertEqual(apply_inline_money_orders(bytearray(data)), 0)


if __name__ == "__main__":
    unittest.main()
