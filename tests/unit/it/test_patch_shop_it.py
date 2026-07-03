"""Regression guard for languages/it/patches/shop.py.

Mirrors tests/unit/de/test_patch_shop_de.py: "In Cube:" -> "In Cubo:" in
place (must be the exact same byte length as the English original — no
relocation possible there), and "Buy" -> "Compra" via a freshly-allocated
free-space block. Unlike the DE port, IT's free space can already be
exhausted by the time this step runs (it applies near the end of
languages/it/lang.yaml), so the "Buy" relocation degrades gracefully to a
warning instead of raising when no free space is available.
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from languages.it.patches import shop as mod  # noqa: E402


def _build_rom(free_space: int = 4096) -> bytearray:
    # Must be large enough to cover the real (fixed) ROM offsets this patch
    # touches; the rest is 0xFF free space for FreeSpaceAllocator to use for
    # the "Buy" -> "Compra" relocation.
    size = mod._IN_CUBE_OFFSET + free_space
    rom = bytearray(b"\xff" * size)
    rom[mod._IN_CUBE_OFFSET: mod._IN_CUBE_OFFSET + len(mod._IN_CUBE_EN)] = mod._IN_CUBE_EN
    rom[mod._BUY_PTR_OFFSET: mod._BUY_PTR_OFFSET + 4] = mod._BUY_EN_POINTER
    return rom


class TestShopIt(unittest.TestCase):
    def test_in_cube_and_buy_same_length(self):
        self.assertEqual(len(mod._IN_CUBE_EN), len(mod._IN_CUBE_IT))

    def test_apply_translates_both_strings(self):
        rom = _build_rom()
        applied = mod.apply_patches(rom)
        self.assertEqual(applied, 2)
        self.assertEqual(
            bytes(rom[mod._IN_CUBE_OFFSET: mod._IN_CUBE_OFFSET + len(mod._IN_CUBE_IT)]),
            mod._IN_CUBE_IT,
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

    def test_buy_relocation_degrades_gracefully_without_free_space(self):
        # No 0xFF run big enough for "Compra" anywhere in the ROM.
        rom = bytearray(b"\x00" * (mod._IN_CUBE_OFFSET + 64))
        rom[mod._IN_CUBE_OFFSET: mod._IN_CUBE_OFFSET + len(mod._IN_CUBE_EN)] = mod._IN_CUBE_EN
        rom[mod._BUY_PTR_OFFSET: mod._BUY_PTR_OFFSET + 4] = mod._BUY_EN_POINTER
        applied = mod.apply_patches(rom)  # must not raise
        self.assertEqual(applied, 1)  # only "In Cube:" -> "In Cubo:" applied
        # "Buy" pointer left untouched (still English).
        self.assertEqual(
            bytes(rom[mod._BUY_PTR_OFFSET: mod._BUY_PTR_OFFSET + 4]),
            mod._BUY_EN_POINTER,
        )


if __name__ == "__main__":
    unittest.main()
