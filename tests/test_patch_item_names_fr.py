import unittest

from scripts.patch_item_names_fr import (
    BERRY_NAMES,
    ITEM_STRIDE,
    ITEM_TABLE_BASE,
    NAME_FIELD,
    apply_item_name_fixes,
    decode_name,
    encode,
)


def _make_item_rom(cells):
    """Build a synthetic item table.

    ``cells`` is a list of (index, english_name) placed at
    ITEM_TABLE_BASE + index*ITEM_STRIDE. A 2-byte item-ID sentinel is written at
    +14 (the start of the item data) so tests can assert it survives the patch.
    """
    max_index = max(i for i, _ in cells)
    data = bytearray(ITEM_TABLE_BASE + (max_index + 1) * ITEM_STRIDE)
    for index, name in cells:
        offset = ITEM_TABLE_BASE + index * ITEM_STRIDE
        raw = encode(name)
        data[offset : offset + len(raw)] = raw
        data[offset + len(raw)] = 0xFF
        # Sentinel item data (e.g. item ID) right after the name field.
        data[offset + NAME_FIELD : offset + NAME_FIELD + 2] = b"\xAB\x01"
    return data


class TestBerryNameData(unittest.TestCase):
    def test_every_french_name_fits_cell(self):
        for en, fr in BERRY_NAMES.items():
            self.assertLessEqual(len(encode(fr)) + 1, NAME_FIELD, en)

    def test_every_french_name_is_encodable(self):
        # Accented glyphs (Pêcha, Énigma, Résin, Kébia, Sédra, Chérim, Éka…)
        # must all live in the CFRU charmap.
        for en, fr in BERRY_NAMES.items():
            encode(fr)  # raises ValueError if any char is unmapped

    def test_french_names_differ_from_english(self):
        for en, fr in BERRY_NAMES.items():
            self.assertNotEqual(en, fr, en)

    def test_all_french_names_start_with_baie(self):
        for fr in BERRY_NAMES.values():
            self.assertTrue(fr.startswith("Baie "), fr)

    def test_known_canonical_mappings(self):
        # Spot-check a few verified canonical names.
        self.assertEqual(BERRY_NAMES["Oran Berry"], "Baie Oran")
        self.assertEqual(BERRY_NAMES["Aspear Berry"], "Baie Willia")
        self.assertEqual(BERRY_NAMES["Cheri Berry"], "Baie Ceriz")
        self.assertEqual(BERRY_NAMES["Sitrus Berry"], "Baie Sitrus")
        self.assertEqual(BERRY_NAMES["Custap Berry"], "Baie Chérim")


class TestApplyItemNameFixes(unittest.TestCase):
    def test_patches_matching_cells(self):
        data = _make_item_rom([(0, "Aspear Berry"), (1, "Oran Berry")])
        patched = apply_item_name_fixes(data, BERRY_NAMES)
        self.assertEqual(patched, 2)
        self.assertEqual(decode_name(data, ITEM_TABLE_BASE), "Baie Willia")
        self.assertEqual(decode_name(data, ITEM_TABLE_BASE + ITEM_STRIDE), "Baie Oran")

    def test_terminator_after_french_name(self):
        data = _make_item_rom([(0, "Oran Berry")])
        apply_item_name_fixes(data, BERRY_NAMES)
        raw = encode("Baie Oran")
        self.assertEqual(data[ITEM_TABLE_BASE + len(raw)], 0xFF)

    def test_preserves_item_data_after_name_field(self):
        # The 2-byte item-ID sentinel at +14 must survive (a French name is
        # never longer than the 14-byte name field).
        data = _make_item_rom([(0, "Aspear Berry"), (1, "Sitrus Berry")])
        apply_item_name_fixes(data, BERRY_NAMES)
        for index in (0, 1):
            off = ITEM_TABLE_BASE + index * ITEM_STRIDE + NAME_FIELD
            self.assertEqual(bytes(data[off : off + 2]), b"\xAB\x01")

    def test_no_stale_glyphs_when_french_shorter(self):
        # "Oran Berry" (10) -> "Baie Oran" (9): the freed byte must be cleared,
        # not left as a stale glyph before the next field.
        data = _make_item_rom([(0, "Oran Berry")])
        apply_item_name_fixes(data, BERRY_NAMES)
        raw = encode("Baie Oran")
        # byte after FF (still inside the name field) must be zero padding
        self.assertEqual(data[ITEM_TABLE_BASE + len(raw) + 1], 0x00)

    def test_idempotent(self):
        data = _make_item_rom([(0, "Aspear Berry")])
        self.assertEqual(apply_item_name_fixes(data, BERRY_NAMES), 1)
        self.assertEqual(apply_item_name_fixes(data, BERRY_NAMES), 0)

    def test_ignores_unknown_names(self):
        # A correctly-French / non-berry item must never be touched.
        data = _make_item_rom([(0, "Potion"), (1, "Master Ball")])
        self.assertEqual(apply_item_name_fixes(data, BERRY_NAMES), 0)
        self.assertEqual(decode_name(data, ITEM_TABLE_BASE), "Potion")

    def test_patches_full_set(self):
        cells = [(i, en) for i, en in enumerate(BERRY_NAMES)]
        data = _make_item_rom(cells)
        self.assertEqual(apply_item_name_fixes(data, BERRY_NAMES), len(BERRY_NAMES))


if __name__ == "__main__":
    unittest.main()
