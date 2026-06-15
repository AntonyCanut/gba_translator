import unittest

from scripts.patch_fixed_table_names import NAME_FIXES, apply_name_fixes, encode


def _make_cell_rom(offset: int, name: str, stride: int) -> bytearray:
    data = bytearray(b"\x00" * (offset + stride))
    raw = encode(name)
    data[offset : offset + len(raw)] = raw
    data[offset + len(raw)] = 0xFF
    return data


class TestApplyNameFixes(unittest.TestCase):
    def test_patches_expected_cell(self):
        fixes = {0x40: ("Aéropique", "Aéropiqué", 13)}
        data = _make_cell_rom(0x40, "Aéropique", 13)
        patched = apply_name_fixes(data, fixes)
        self.assertEqual(patched, 1)
        new = encode("Aéropiqué")
        self.assertEqual(bytes(data[0x40 : 0x40 + len(new)]), new)
        self.assertEqual(data[0x40 + len(new)], 0xFF)
        # remaining cell bytes are zero padding
        self.assertEqual(bytes(data[0x40 + len(new) + 1 : 0x40 + 13]), b"\x00\x00\x00")

    def test_idempotent(self):
        fixes = {0x40: ("Aéropique", "Aéropiqué", 13)}
        data = _make_cell_rom(0x40, "Aéropique", 13)
        apply_name_fixes(data, fixes)
        self.assertEqual(apply_name_fixes(data, fixes), 0)

    def test_rejects_unexpected_cell_content(self):
        fixes = {0x40: ("Aéropique", "Aéropiqué", 13)}
        data = _make_cell_rom(0x40, "Plaquage", 13)
        with self.assertRaises(ValueError):
            apply_name_fixes(data, fixes)

    def test_rejects_name_overflowing_cell(self):
        fixes = {0x40: ("Aéropique", "Aéropiqué", 9)}
        data = _make_cell_rom(0x40, "Aéropique", 13)
        with self.assertRaises(ValueError):
            apply_name_fixes(data, fixes)

    def test_real_fixes_fit_their_cells(self):
        for offset, (old, new, stride) in NAME_FIXES.items():
            self.assertLessEqual(len(encode(new)) + 1, stride, hex(offset))
            self.assertLessEqual(len(encode(old)) + 1, stride, hex(offset))


class TestBerryPouchCells(unittest.TestCase):
    """The Berry Pouch key item shipped in English from centered name cells
    unreachable by the translation pipeline (absent from both
    translation_ready.json and the Spanish extraction). "Pochette Baies"
    (14 glyphs) overflowed the 12-byte name slots and silently fell back to
    English; this regressed twice. "Sac à Baies" is byte-exact with
    "Berry Pouch" (11 glyphs), so it can never overflow.
    """

    CENTERED = (0x3DEED8, 0x87A0B0)

    def test_centered_cells_registered(self):
        for offset in self.CENTERED:
            self.assertIn(offset, NAME_FIXES, hex(offset))
            old, new, _ = NAME_FIXES[offset]
            self.assertEqual(old, " " * 12 + "Berry Pouch", hex(offset))
            self.assertEqual(new, " " * 12 + "Sac à Baies", hex(offset))

    def test_replacement_is_byte_exact(self):
        # Same encoded length => no relocation, no pointer needed, no overflow.
        for offset in self.CENTERED:
            old, new, _ = NAME_FIXES[offset]
            self.assertEqual(len(encode(new)), len(encode(old)), hex(offset))

    def test_centered_cells_patch_in_place(self):
        for offset in self.CENTERED:
            old, new, stride = NAME_FIXES[offset]
            data = _make_cell_rom(offset, old, stride)
            self.assertEqual(apply_name_fixes(data, {offset: (old, new, stride)}), 1)
            raw = encode(new)
            self.assertEqual(bytes(data[offset : offset + len(raw)]), raw)
            self.assertEqual(data[offset + len(raw)], 0xFF)


if __name__ == "__main__":
    unittest.main()
