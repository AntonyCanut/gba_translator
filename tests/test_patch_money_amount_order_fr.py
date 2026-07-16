import unittest
from pathlib import Path

import pytest

from languages.fr.patches.money_amount_order import (
    ENGLISH_ORDER,
    FRENCH_ORDER,
    TEMPLATE_OFFSET,
    apply,
)

ROM = Path("output/roms/GenedRom-fr.gba")


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


@pytest.mark.rom
@unittest.skipUnless(ROM.exists(), "built FR ROM not present")
class TestBuiltRom(unittest.TestCase):
    def test_committed_rom_has_amount_before_symbol(self):
        data = ROM.read_bytes()
        self.assertEqual(
            data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)],
            FRENCH_ORDER,
        )


if __name__ == "__main__":
    unittest.main()
