import unittest

from languages.fr.patches.fixed_table_names import (
    NAME_FIXES,
    _TM_CT_TABLES,
    _ct_name,
    _tm_name,
    apply_name_fixes,
    apply_tm_to_ct_patches,
    encode,
)


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


class TestTownMapCells(unittest.TestCase):
    """The Town Map key item shipped in English ("Town Map") from the same
    centered name cells as Berry Pouch: read by the bag at base+12
    (0x3DEE34 / 0x87A00C), absent from translation_ready.json, the Spanish
    extraction and combined_fr.txt, so neither reinsertion nor the inline pass
    ever reaches them. "Carte" (5 glyphs) fits the cell with room to spare.
    """

    CENTERED = (0x3DEE28, 0x87A000)

    def test_centered_cells_registered(self):
        for offset in self.CENTERED:
            self.assertIn(offset, NAME_FIXES, hex(offset))
            old, new, _ = NAME_FIXES[offset]
            self.assertEqual(old, " " * 12 + "Town Map", hex(offset))
            self.assertEqual(new, " " * 12 + "Carte", hex(offset))

    def test_centered_cells_patch_in_place(self):
        # The game reads the name at base+12; after patching, that cell must
        # decode to "Carte" and be 0xFF-terminated.
        for offset in self.CENTERED:
            old, new, stride = NAME_FIXES[offset]
            data = _make_cell_rom(offset, old, stride)
            self.assertEqual(apply_name_fixes(data, {offset: (old, new, stride)}), 1)
            name_cell = offset + 12
            self.assertEqual(bytes(data[name_cell : name_cell + 5]), encode("Carte"))
            self.assertEqual(data[name_cell + 5], 0xFF)


class TestHardStoneCells(unittest.TestCase):
    """Hard Stone hold item shipped in English from centered name cells
    unreachable by the translation pipeline (absent from translation_ready.json
    and the Spanish extraction). Both the FireRed table (0x3DD32C) and the
    CFRU extended table (0x878504) must be patched to "Pierre Dure".
    "Pierre Dure" (11 glyphs) fits stride-26 cells (12 spaces + 11 + FF + 2 pad).
    """

    CENTERED = (0x3DD32C, 0x878504)

    def test_centered_cells_registered(self):
        for offset in self.CENTERED:
            self.assertIn(offset, NAME_FIXES, hex(offset))
            old, new, _ = NAME_FIXES[offset]
            self.assertEqual(old, " " * 12 + "Hard Stone", hex(offset))
            self.assertEqual(new, " " * 12 + "Pierre Dure", hex(offset))

    def test_centered_cells_patch_in_place(self):
        for offset in self.CENTERED:
            old, new, stride = NAME_FIXES[offset]
            data = _make_cell_rom(offset, old, stride)
            self.assertEqual(apply_name_fixes(data, {offset: (old, new, stride)}), 1)
            name_cell = offset + 12
            self.assertEqual(bytes(data[name_cell : name_cell + len(encode("Pierre Dure"))]), encode("Pierre Dure"))
            self.assertEqual(data[name_cell + len(encode("Pierre Dure"))], 0xFF)


class TestWeakArmorCell(unittest.TestCase):
    """Roggenrola/Nodulithe's passive ability "Weak Armor" shipped in English
    from a fixed-width 17-byte cell, no pointer (absent from
    translation_ready.json and the Spanish extraction). Official French name
    is "Armurouillée" (Armure + rouillée).
    """

    OFFSET = 0xA37069

    def test_cell_registered(self):
        self.assertIn(self.OFFSET, NAME_FIXES)
        old, new, stride = NAME_FIXES[self.OFFSET]
        self.assertEqual(old, "Weak Armor")
        self.assertEqual(new, "Armurouillée")
        self.assertEqual(stride, 17)

    def test_cell_patches_in_place(self):
        old, new, stride = NAME_FIXES[self.OFFSET]
        data = _make_cell_rom(self.OFFSET, old, stride)
        self.assertEqual(apply_name_fixes(data, {self.OFFSET: (old, new, stride)}), 1)
        raw = encode(new)
        self.assertEqual(bytes(data[self.OFFSET : self.OFFSET + len(raw)]), raw)
        self.assertEqual(data[self.OFFSET + len(raw)], 0xFF)


class TestDrescoGymLeaderNameCells(unittest.TestCase):
    """Dresco Gym Leader "Mirskle" was renamed to "Sylvain" in every
    dialogue string (combined_fr.txt 0x1F15C64 etc.), but the raw trainer-data
    table read by the VS/battle-launch screen has six separate name cells the
    dialogue translation pipeline never reaches (issue #62).
    """

    OFFSETS = (0x23EBBC, 0x23F60C, 0x23F634, 0x245B24, 0x245B4C, 0x245B74)

    def test_cells_registered(self):
        for offset in self.OFFSETS:
            self.assertIn(offset, NAME_FIXES, hex(offset))
            old, new, stride = NAME_FIXES[offset]
            self.assertEqual(old, "Mirskle", hex(offset))
            self.assertEqual(new, "Sylvain", hex(offset))
            self.assertEqual(stride, 8, hex(offset))

    def test_cells_patch_in_place(self):
        for offset in self.OFFSETS:
            old, new, stride = NAME_FIXES[offset]
            data = _make_cell_rom(offset, old, stride)
            self.assertEqual(apply_name_fixes(data, {offset: (old, new, stride)}), 1)
            raw = encode(new)
            self.assertEqual(bytes(data[offset : offset + len(raw)]), raw)
            self.assertEqual(data[offset + len(raw)], 0xFF)


class TestTmToCtCells(unittest.TestCase):
    """TM item name cells (class 2, absent from the injection pipeline) must be
    renamed to CT in all three item tables: FireRed original (TM01–TM50),
    CFRU part 1 (TM01–TM58), CFRU part 2 (TM59–TM120) = 170 cells total.
    """

    # Spot-check one entry from each table range: (base, num, stride)
    SPOT_CHECKS = [
        (0x3DE1D4, 1, 44),   # FireRed first entry: TM01
        (0x3DE1D4, 26, 44),  # FireRed TM26
        (0x3DE1D4, 50, 44),  # FireRed last entry: TM50
        (0x8793AC, 1, 44),   # CFRU part 1 first
        (0x8793AC, 58, 44),  # CFRU part 1 last
        (0x87A274, 59, 44),  # CFRU part 2 first
        (0x87A274, 120, 44), # CFRU part 2 last
    ]

    # Sentinel placed after the name terminator to represent item struct data
    # (item ID, price, description pointer, etc.) that must survive the patch.
    _SENTINEL_OFFSET = 14   # bytes past cell start (matches Gen3 itemId offset)
    _SENTINEL = b"\xB5\x01"  # 0x01B5 little-endian — a real CFRU item ID

    def _make_table_rom(self) -> bytearray:
        """Synthetic ROM with TM names and sentinel item data after each terminator."""
        max_addr = 0
        for base, nums, stride in _TM_CT_TABLES:
            for i, num in enumerate(nums):
                end = base + i * stride + stride
                if end > max_addr:
                    max_addr = end
        data = bytearray(max_addr)
        for base, nums, stride in _TM_CT_TABLES:
            for i, num in enumerate(nums):
                offset = base + i * stride
                raw = encode(_tm_name(num))
                data[offset : offset + len(raw)] = raw
                data[offset + len(raw)] = 0xFF
                # Place sentinel item data after the terminator.
                sentinel_pos = offset + self._SENTINEL_OFFSET
                data[sentinel_pos : sentinel_pos + 2] = self._SENTINEL
        return data

    def test_all_tables_define_expected_ranges(self):
        expected = [
            (0x3DE1D4, range(1, 51), 44),
            (0x8793AC, range(1, 59), 44),
            (0x87A274, range(59, 121), 44),
        ]
        self.assertEqual(_TM_CT_TABLES, expected)

    def test_total_cell_count_is_170(self):
        total = sum(len(list(nums)) for _, nums, _ in _TM_CT_TABLES)
        self.assertEqual(total, 170)

    def test_patches_all_170_cells(self):
        data = self._make_table_rom()
        patched = apply_tm_to_ct_patches(data)
        self.assertEqual(patched, 170)

    def test_item_data_after_terminator_is_preserved(self):
        """Patch must not zero item-struct bytes (ID, price…) that follow the name."""
        data = self._make_table_rom()
        apply_tm_to_ct_patches(data)
        for base, nums, stride in _TM_CT_TABLES:
            for i, num in enumerate(nums):
                offset = base + i * stride
                sentinel_pos = offset + self._SENTINEL_OFFSET
                actual = bytes(data[sentinel_pos : sentinel_pos + 2])
                self.assertEqual(
                    actual,
                    self._SENTINEL,
                    f"item data destroyed at TM{num} (0x{offset:X})",
                )

    def test_spot_check_cells_are_ct_after_patch(self):
        data = self._make_table_rom()
        apply_tm_to_ct_patches(data)
        for base, num, stride in self.SPOT_CHECKS:
            # Compute the index within the table range that contains `num`.
            for table_base, nums, table_stride in _TM_CT_TABLES:
                if num in nums and table_base == base:
                    i = list(nums).index(num)
                    offset = table_base + i * table_stride
                    expected = encode(_ct_name(num))
                    actual = bytes(data[offset : offset + len(expected)])
                    self.assertEqual(actual, expected, f"TM{num:02d}→CT{num:02d} at 0x{offset:X}")
                    self.assertEqual(data[offset + len(expected)], 0xFF, f"no terminator after CT{num:02d}")

    def test_idempotent(self):
        data = self._make_table_rom()
        apply_tm_to_ct_patches(data)
        self.assertEqual(apply_tm_to_ct_patches(data), 0)

    def test_rejects_unexpected_cell_content(self):
        data = self._make_table_rom()
        # Corrupt TM26 in the FireRed table.
        offset = 0x3DE1D4 + 25 * 44
        raw = encode("TM26")
        data[offset] = 0x00  # break first byte
        data[offset + 1 : offset + len(raw)] = raw[1:]
        data[offset + len(raw)] = 0xFF
        with self.assertRaises(ValueError):
            apply_tm_to_ct_patches(data)

    def test_ct_names_fit_stride_44_cells(self):
        # CT01…CT120 + FF must fit within 44 bytes (names are 4-5 chars).
        for _, nums, stride in _TM_CT_TABLES:
            for num in nums:
                encoded = encode(_ct_name(num))
                self.assertLessEqual(len(encoded) + 1, stride, _ct_name(num))


if __name__ == "__main__":
    unittest.main()
