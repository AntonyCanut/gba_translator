"""Regression tests for languages/it/patches/trainer_card_date.py.

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

from languages.it.patches import trainer_card_date as mod  # noqa: E402

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

    def test_idempotent_second_run_changes_nothing(self):
        mod.apply(self.data)
        changed_again = mod.apply(self.data)
        self.assertEqual(changed_again, 0)

    def test_composes_with_time_format_and_save_template(self):
        # time_format writes the weekday/AM-PM/ASM patches and the "Mai"
        # word + date-template edits; none of them use trailing spaces on
        # month cells (all 4-char "Xxx." forms), so the trim step here is a
        # harmless no-op — this just proves running both scripts together
        # doesn't raise or corrupt either one's output.
        from languages.it.patches import time_format as time_mod

        time_mod.apply_patches(self.data)
        time_mod.patch_save_template(self.data)
        n = mod.apply(self.data)
        self.assertGreater(n, 0)
        self.assertEqual(
            bytes(self.data[mod.BLOCK_FILE : mod.BLOCK_FILE + mod.BLOCK_LEN]),
            mod.assemble_redirect(),
        )


if __name__ == "__main__":
    unittest.main()
