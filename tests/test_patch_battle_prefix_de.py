"""Regression guard for languages/de/patches/battle_prefix.py.

Unlike the FR version, the German patch is a report-only guard (no code cave,
no byte mutation): German keeps the engine's natural prefix-before-name word
order, so the translations already written by the normal pipeline at
0xA4C61A / 0xA4C636 / 0xA4C64C are sufficient. This just verifies the guard
never mutates the ROM and correctly flags an unterminated cell.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.de.patches.battle_prefix import PREFIX_CELLS, apply_to_rom, check_cell


def _rom_with_valid_cells(size: int = 0xA500000) -> bytearray:
    rom = bytearray(b"\xff" * size)
    for offset, _label in PREFIX_CELLS:
        # A short, properly terminated placeholder string.
        rom[offset:offset + 4] = bytes([0xD9, 0xD9, 0xD9, 0xFF])
    return rom


class TestBattlePrefixGuard(unittest.TestCase):
    def test_never_mutates_rom(self):
        rom = _rom_with_valid_cells()
        original = bytes(rom)
        applied = apply_to_rom(rom)
        self.assertEqual(applied, 0)
        self.assertEqual(bytes(rom), original)

    def test_check_cell_passes_when_terminated(self):
        rom = _rom_with_valid_cells()
        for offset, label in PREFIX_CELLS:
            self.assertTrue(check_cell(rom, offset, label))

    def test_check_cell_fails_when_unterminated(self):
        size = 0xA500000
        rom = bytearray(b"\xd9" * size)  # no 0xFF anywhere nearby
        for offset, label in PREFIX_CELLS:
            self.assertFalse(check_cell(rom, offset, label))


if __name__ == "__main__":
    unittest.main()
