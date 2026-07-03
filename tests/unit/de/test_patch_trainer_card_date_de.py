"""Regression tests for languages/de/patches/trainer_card_date.py.

The builder/redirect assembly is pure Thumb-encoding logic (checked via the
length/structure assertions already baked into the module); these tests
exercise `apply()` end-to-end against a fresh copy of englishrom.gba, which
has both the free-space builder slot and the original inline block in their
pristine (patchable) state.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import patch_time_format_de as time_mod  # noqa: E402
import patch_trainer_card_date_de as mod  # noqa: E402

ENGLISH_ROM = ROOT / "input" / "roms" / "englishrom.gba"


@pytest.mark.skipif(not ENGLISH_ROM.exists(), reason="englishrom.gba not available")
class TestAssembly(unittest.TestCase):
    def test_builder_length_matches_assertions(self):
        builder = mod.assemble_builder()
        self.assertEqual(len(builder) % 4, 0)
        self.assertGreater(len(builder), 0)

    def test_redirect_block_is_exactly_original_block_length(self):
        redirect = mod.assemble_redirect()
        self.assertEqual(len(redirect), mod.BLOCK_LEN)


@pytest.mark.skipif(not ENGLISH_ROM.exists(), reason="englishrom.gba not available")
class TestApply(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(ENGLISH_ROM.read_bytes())

    def test_applies_cleanly_against_pristine_english_rom(self):
        changed = mod.apply(self.data)
        self.assertGreater(changed, 0)
        self.assertEqual(
            bytes(self.data[mod.BLOCK_FILE : mod.BLOCK_FILE + mod.BLOCK_LEN]),
            mod.assemble_redirect(),
        )

    def test_idempotent_second_run_changes_nothing_but_trims(self):
        mod.apply(self.data)
        changed_again = mod.apply(self.data)
        self.assertEqual(changed_again, 0)

    def test_composes_with_time_format_month_patches(self):
        # time_format_de writes several months with a trailing space (März,
        # Mai, Juli, Okt., Dez.); the trainer-card builder must trim exactly
        # those so "<day> <month> <year>" doesn't render a double space.
        time_mod.apply_patches(self.data)
        time_mod.patch_months(self.data)
        n = mod.apply(self.data)
        self.assertGreater(n, 0)

        import struct

        for month in (3, 5, 7, 10, 12):
            ptr_off = mod.MONTH_PTR_TABLE_FILE + 4 * (month - 1)
            ptr = struct.unpack("<I", self.data[ptr_off : ptr_off + 4])[0]
            off = ptr - 0x08000000
            end = off
            while self.data[end] != 0xFF:
                end += 1
            self.assertNotEqual(
                self.data[end - 1], 0x00,
                f"month {month} still has an untrimmed trailing space",
            )


if __name__ == "__main__":
    unittest.main()
