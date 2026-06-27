"""Regression guard for scripts/patch_battle_prefix_fr.py.

Critical property: the three single-byte prefix patches (0xA4C61A, 0xA4C636,
0xA4C64C) must write 0xFF regardless of whether the byte currently present is
the original English byte OR a French-translated byte written by the FR builder.
In CI, prepare_fr_json.py may cause the builder to write a different first byte
at these locations; the patch must zero them unconditionally.
"""

from __future__ import annotations

import unittest

from scripts.patch_battle_prefix_fr import PATCHES, apply_patches


# Helpers
def _rom_with_patches(overrides: dict[int, int] | None = None) -> bytearray:
    """Return a minimal bytearray seeded with the expected 'old' bytes from each
    patch entry, plus optional byte overrides (to simulate FR-builder effects)."""
    size = max(offset + len(old) for offset, old, _ in PATCHES) + 256
    data = bytearray(b"\xff" * size)
    for offset, old, _ in PATCHES:
        data[offset: offset + len(old)] = old
    if overrides:
        for offset, byte in overrides.items():
            data[offset] = byte
    return data


class TestApplyPatchesNormalCase(unittest.TestCase):
    def test_applies_all_patches_from_english_rom(self):
        data = _rom_with_patches()
        applied = apply_patches(data)
        self.assertEqual(applied, len(PATCHES))

    def test_idempotent(self):
        data = _rom_with_patches()
        apply_patches(data)
        self.assertEqual(apply_patches(data), 0)

    def test_prefix_bytes_become_ff(self):
        data = _rom_with_patches()
        apply_patches(data)
        # The three 1-byte prefix patches must zero their first byte.
        for offset, old, new in PATCHES:
            if len(old) == 1 and new == bytes([0xFF]):
                self.assertEqual(data[offset], 0xFF,
                                 f"0x{offset:X} should be 0xFF after patch")


class TestApplyPatchesLenientPrefix(unittest.TestCase):
    """CI scenario: the FR builder may overwrite the English first byte of a
    prefix string with a French character before the patch runs."""

    def test_prefix_zeroed_even_when_fr_builder_modified_byte(self):
        # Simulate the CI failure: 0xA4C64C has 0xCE ('T') instead of 0xC6 ('L').
        prefix_offsets = [
            off for off, old, new in PATCHES if len(old) == 1 and new == bytes([0xFF])
        ]
        self.assertTrue(prefix_offsets, "No single-byte prefix patches found")
        for off in prefix_offsets:
            data = _rom_with_patches(overrides={off: 0xCE})
            # Must NOT raise — must write 0xFF.
            applied = apply_patches(data)
            self.assertGreater(applied, 0)
            self.assertEqual(data[off], 0xFF,
                             f"0x{off:X} must be 0xFF even when FR byte 0xCE was present")

    def test_code_cave_still_strict(self):
        # Multi-byte code-cave patches must still reject wrong bytes.
        for offset, old, new in PATCHES:
            if len(old) > 1:
                data = _rom_with_patches(overrides={offset: 0x00})
                with self.assertRaises(ValueError,
                                       msg=f"multi-byte patch at 0x{offset:X} must be strict"):
                    apply_patches(data)
                break  # one is enough


if __name__ == "__main__":
    unittest.main()
