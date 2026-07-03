"""Regression guard for languages/de/patches/givecs_gift_item.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.de.patches.givecs_gift_item import (
    ITEM_ENTRY_OFF,
    ITEM_STRIDE,
    NAME_PREFIX_LEN,
    apply_to_rom,
)


def _make_en(size: int = 0x900000) -> bytearray:
    en = bytearray(b"\xff" * size)
    en[ITEM_ENTRY_OFF:ITEM_ENTRY_OFF + ITEM_STRIDE] = bytes(range(ITEM_STRIDE))
    return en


class TestGivecsGiftItemDe(unittest.TestCase):
    def test_restores_tail_leaves_name_prefix(self):
        en = _make_en()
        rom = bytearray(en)
        # Diverge the tail (simulated overflow) but keep the localized prefix.
        rom[ITEM_ENTRY_OFF + NAME_PREFIX_LEN + 5] = 0xAA
        prefix_before = bytes(rom[ITEM_ENTRY_OFF:ITEM_ENTRY_OFF + NAME_PREFIX_LEN])

        n = apply_to_rom(rom, bytes(en))
        self.assertEqual(n, 1)
        self.assertEqual(
            rom[ITEM_ENTRY_OFF + NAME_PREFIX_LEN:ITEM_ENTRY_OFF + ITEM_STRIDE],
            en[ITEM_ENTRY_OFF + NAME_PREFIX_LEN:ITEM_ENTRY_OFF + ITEM_STRIDE],
        )
        self.assertEqual(
            rom[ITEM_ENTRY_OFF:ITEM_ENTRY_OFF + NAME_PREFIX_LEN], prefix_before,
            "name prefix must be left untouched",
        )

    def test_idempotent(self):
        en = _make_en()
        rom = bytearray(en)
        rom[ITEM_ENTRY_OFF + NAME_PREFIX_LEN + 5] = 0xAA
        apply_to_rom(rom, bytes(en))
        self.assertEqual(apply_to_rom(rom, bytes(en)), 0)

    def test_dry_run_does_not_write(self):
        en = _make_en()
        rom = bytearray(en)
        rom[ITEM_ENTRY_OFF + NAME_PREFIX_LEN + 5] = 0xAA
        original = bytes(rom)
        n = apply_to_rom(rom, bytes(en), dry_run=True)
        self.assertEqual(n, 1)
        self.assertEqual(bytes(rom), original)


if __name__ == "__main__":
    unittest.main()
