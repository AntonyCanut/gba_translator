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
from src.text.charmap_data import CHAR_TO_BYTE


def _enc(text: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in text)

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

    def test_inline_guard_accepts_french_sentence(self):
        # A money pattern inside a real French string is rewritten.
        data = _synthetic()
        text = _enc("Ça fera ") + bytes([0xB7, 0xFD, 0x02]) + _enc(".")
        start = 8
        data[start:start + len(text)] = text
        self.assertEqual(apply_inline_money_orders(data), 1)
        swapped = _enc("Ça fera ") + bytes([0xFD, 0x02, 0xB7]) + _enc(".")
        self.assertEqual(bytes(data[start:start + len(swapped)]), swapped)

    def test_inline_guard_rejects_thumb_code(self):
        # 0xB7/0xFD halves of Thumb BL pairs must NOT be reordered — a blind
        # rewrite here rebooted the game after every wild capture (ticket
        # « Capture reset game »). Real bytes around 0x104C58 in the ROM.
        code = bytes.fromhex(
            "01200021221cfff7b7fd02b010bc01bc00470000f0b54f46"
        )
        data = _synthetic()
        start = 64
        data[start:start + len(code)] = code
        self.assertEqual(apply_inline_money_orders(data), 0)
        self.assertEqual(bytes(data[start:start + len(code)]), code)

    def test_inline_guard_rejects_compressed_data(self):
        # Random-looking compressed graphics containing the byte pattern must
        # be left byte-identical (real bytes around 0x52D32F in the ROM).
        blob = bytes.fromhex(
            "06591122165bc6eab7fd02492e57ed0c9f6494c73c76b816"
        )
        data = _synthetic()
        start = 64
        data[start:start + len(blob)] = blob
        self.assertEqual(apply_inline_money_orders(data), 0)
        self.assertEqual(bytes(data[start:start + len(blob)]), blob)

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
