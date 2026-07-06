"""Regression guard for languages/de/patches/fixed_table_names.py."""

from __future__ import annotations

import unittest

from languages.de.patches.fixed_table_names import NAME_FIXES, apply_name_fixes, encode


def _make_cell_rom(offset: int, name: str, stride: int) -> bytearray:
    data = bytearray(b"\x00" * (offset + stride))
    raw = encode(name)
    data[offset : offset + len(raw)] = raw
    data[offset + len(raw)] = 0xFF
    return data


class TestRealFixesFitTheirCells(unittest.TestCase):
    def test_every_fix_fits_its_stride(self):
        for offset, (old, new, stride) in NAME_FIXES.items():
            self.assertLessEqual(len(encode(new)) + 1, stride, hex(offset))
            self.assertLessEqual(len(encode(old)) + 1, stride, hex(offset))


class TestPortaPCCell(unittest.TestCase):
    """The "Porta-PC" key item name (issue #40) shipped in English from a
    tight, unpadded fixed-width cell unreachable by the translation pipeline
    (absent from translation_ready.json and the Spanish extraction). The next
    cell's data starts immediately after the terminator, so the German
    replacement must be byte-length-equal to the English original.
    """

    OFFSET = 0x87A140

    def test_cell_registered(self):
        self.assertIn(self.OFFSET, NAME_FIXES)
        old, new, stride = NAME_FIXES[self.OFFSET]
        self.assertEqual(old, "Porta-PC")
        self.assertEqual(new, "Mobil-PC")
        self.assertEqual(stride, 9)

    def test_replacement_is_byte_exact(self):
        # Same encoded length => no relocation, no risk of clobbering the
        # adjacent cell's data that starts right after the terminator.
        old, new, _ = NAME_FIXES[self.OFFSET]
        self.assertEqual(len(encode(new)), len(encode(old)))

    def test_cell_patches_in_place_without_touching_next_cell(self):
        old, new, stride = NAME_FIXES[self.OFFSET]
        data = _make_cell_rom(self.OFFSET, old, stride)
        # Sentinel representing the next cell's data, starting immediately
        # after the terminator (no padding for this cell).
        sentinel = b"\xAB\xCD\xEF"
        next_off = self.OFFSET + stride
        data[next_off : next_off + len(sentinel)] = sentinel

        self.assertEqual(apply_name_fixes(data, {self.OFFSET: (old, new, stride)}), 1)

        raw = encode(new)
        self.assertEqual(bytes(data[self.OFFSET : self.OFFSET + len(raw)]), raw)
        self.assertEqual(data[self.OFFSET + len(raw)], 0xFF)
        self.assertEqual(bytes(data[next_off : next_off + len(sentinel)]), sentinel)

    def test_idempotent(self):
        old, new, stride = NAME_FIXES[self.OFFSET]
        data = _make_cell_rom(self.OFFSET, old, stride)
        fixes = {self.OFFSET: (old, new, stride)}
        apply_name_fixes(data, fixes)
        self.assertEqual(apply_name_fixes(data, fixes), 0)

    def test_rejects_unexpected_cell_content(self):
        old, new, stride = NAME_FIXES[self.OFFSET]
        data = _make_cell_rom(self.OFFSET, "Wrong", stride)
        with self.assertRaises(ValueError):
            apply_name_fixes(data, {self.OFFSET: (old, new, stride)})


if __name__ == "__main__":
    unittest.main()
