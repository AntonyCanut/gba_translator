"""Regression guard for scripts/patch_pokedex_metrics_it.py.

The imperial->metric Thumb code patches are byte-identical to the French/
German versions (tests/test_patch_pokedex_metrics_fr.py already exercises
that algorithm end-to-end under unicorn — no need to duplicate it here since
the bytes are the same). This file only covers what's IT-specific: the
two-letter field labels ("Al"/"Pe" instead of "Ht"/"Wt") and the Italian
"kg" unit, plus the generic apply/idempotency contract on a synthetic ROM.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import patch_pokedex_metrics_it as mod  # noqa: E402

PATCHES = mod.PATCHES
apply_patches = mod.apply_patches


class TestApplyPatches(unittest.TestCase):
    def test_all_patches_same_length(self):
        for offset, old, new in PATCHES:
            self.assertEqual(len(old), len(new), f"length mismatch at 0x{offset:X}")

    def test_no_overlapping_patches(self):
        spans = []
        for offset, old, _ in PATCHES:
            end = offset + len(old)
            for a, b in spans:
                self.assertFalse(
                    a < end and offset < b,
                    f"patch at 0x{offset:X} overlaps with 0x{a:X}-0x{b:X}",
                )
            spans.append((offset, end))

    def test_all_patches_apply_and_are_idempotent_on_synthetic_rom(self):
        size = max(off + len(old) for off, old, _ in PATCHES) + 4
        data = bytearray(size)
        for offset, old, _ in PATCHES:
            data[offset: offset + len(old)] = old
        self.assertEqual(apply_patches(data), len(PATCHES))
        self.assertEqual(apply_patches(data), 0)  # second pass: no-op


class TestStringTablePatches(unittest.TestCase):
    def test_ht_renamed_to_al(self):
        p = next(p for p in PATCHES if p[0] == 0x415F98)
        self.assertEqual(p[1], b"\xc2\xe8\xff")
        self.assertEqual(p[2], b"\xbb\xe0\xff")

    def test_wt_renamed_to_pe(self):
        p = next(p for p in PATCHES if p[0] == 0x415F9B)
        self.assertEqual(p[1], b"\xd1\xe8\xff")
        self.assertEqual(p[2], b"\xca\xd9\xff")

    def test_lbs_replaced_by_kg(self):
        p = next(p for p in PATCHES if p[0] == 0x415FA0)
        self.assertEqual(p[1], b"\xe0\xd6\xe7\xad\xff")
        self.assertEqual(p[2], b"\xdf\xdb\xff\x00\x00")

    def test_weight_divisor_lbs_to_kg(self):
        p = next(p for p in PATCHES if p[0] == 0x105AD4)
        self.assertEqual(int.from_bytes(p[1], "little"), 4536)
        self.assertEqual(int.from_bytes(p[2], "little"), 10000)


if __name__ == "__main__":
    unittest.main()
