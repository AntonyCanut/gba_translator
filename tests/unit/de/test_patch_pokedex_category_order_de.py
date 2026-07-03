"""Regression guard for languages/de/patches/pokedex_category_order.py.

The instruction swap is byte-identical to French (same ASM, same fixed
"Pokémon" suffix — the brand name is unchanged across localisations); the
render-order behaviour under unicorn is already exercised end-to-end by
tests/test_patch_pokedex_category_order_fr.py against the same bytes, so this
file only covers the byte-level apply/idempotency contract.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import patch_pokedex_category_order_de as mod  # noqa: E402

PATCHES = mod.PATCHES
apply_patches = mod.apply_patches


def _synthetic(form_index: int = 0) -> bytearray:
    size = max(off + len(new) for off, _olds, new in PATCHES) + 4
    data = bytearray(size)
    for offset, olds, _new in PATCHES:
        form = olds[min(form_index, len(olds) - 1)]
        data[offset: offset + len(form)] = form
    return data


class TestRealPatches(unittest.TestCase):
    def test_all_forms_same_length_as_new(self):
        for offset, olds, new in PATCHES:
            for old in olds:
                self.assertEqual(len(old), len(new), f"length mismatch at 0x{offset:X}")

    def test_applies_on_synthetic_rom_both_suffix_forms(self):
        for form_index in (0, 1):
            data = _synthetic(form_index)
            self.assertEqual(apply_patches(data), len(PATCHES))

    def test_idempotent_on_synthetic_rom(self):
        data = _synthetic(0)
        apply_patches(data)
        self.assertEqual(apply_patches(data), 0)

    def test_suffix_gets_trailing_not_leading_space(self):
        new = next(n for off, _olds, n in PATCHES if off == 0x415F8F)
        self.assertEqual(new[-1], 0xFF)
        self.assertEqual(new[-2], 0x00)
        self.assertNotEqual(new[0], 0x00)


if __name__ == "__main__":
    unittest.main()
