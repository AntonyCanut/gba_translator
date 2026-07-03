"""Regression guard for scripts/patch_shop_de.py.

Mirrors the two patches: "In Cube:" -> "Bestand:" in place (must be the exact
same byte length as the English original — no relocation possible there),
and "Buy" -> "Kaufen" via a freshly-allocated free-space block (dynamically
found, unlike the French dedicated build which can hardcode a fixed offset —
see the module docstring for why hardcoding would be unsafe for a
generic-build language).
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import patch_shop_de as mod  # noqa: E402


def _build_rom() -> bytearray:
    # Must be large enough to cover the real (fixed) ROM offsets this patch
    # touches; the rest is 0xFF free space for FreeSpaceAllocator to use for
    # the "Buy" -> "Kaufen" relocation.
    size = mod._IN_CUBE_OFFSET + 4096
    rom = bytearray(b"\xff" * size)
    rom[mod._IN_CUBE_OFFSET: mod._IN_CUBE_OFFSET + len(mod._IN_CUBE_EN)] = mod._IN_CUBE_EN
    rom[mod._BUY_PTR_OFFSET: mod._BUY_PTR_OFFSET + 4] = mod._BUY_EN_POINTER
    return rom


class TestShopDe(unittest.TestCase):
    def test_in_cube_and_buy_same_length(self):
        self.assertEqual(len(mod._IN_CUBE_EN), len(mod._IN_CUBE_DE))

    def test_apply_translates_both_strings(self):
        rom = _build_rom()
        applied = mod.apply_patches(rom)
        self.assertEqual(applied, 2)
        self.assertEqual(
            bytes(rom[mod._IN_CUBE_OFFSET: mod._IN_CUBE_OFFSET + len(mod._IN_CUBE_DE)]),
            mod._IN_CUBE_DE,
        )
        new_ptr = struct.unpack_from("<I", rom, mod._BUY_PTR_OFFSET)[0]
        self.assertNotEqual(new_ptr, struct.unpack_from("<I", mod._BUY_EN_POINTER)[0])

    def test_apply_is_idempotent(self):
        rom = _build_rom()
        mod.apply_patches(rom)
        snapshot = bytes(rom)
        applied2 = mod.apply_patches(rom)
        self.assertEqual(applied2, 0)
        self.assertEqual(bytes(rom), snapshot)

    def test_unexpected_bytes_raise(self):
        rom = _build_rom()
        rom[mod._IN_CUBE_OFFSET] = 0x00  # corrupt the expected EN bytes
        with self.assertRaises(ValueError):
            mod.apply_patches(rom)


if __name__ == "__main__":
    unittest.main()
