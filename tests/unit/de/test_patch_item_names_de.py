"""Regression guard for languages/de/patches/item_names.py (mirrors the FR suite)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import patch_item_names_de as mod  # noqa: E402

ALL_NAMES = mod.ALL_NAMES
BERRY_NAMES = mod.BERRY_NAMES
ITEM_NAMES = mod.ITEM_NAMES
ITEM_STRIDE = mod.ITEM_STRIDE
ITEM_TABLE_BASE = mod.ITEM_TABLE_BASE
NAME_FIELD = mod.NAME_FIELD
apply_item_name_fixes = mod.apply_item_name_fixes
decode_name = mod.decode_name
encode = mod.encode


def _make_item_rom(cells):
    max_index = max(i for i, _ in cells)
    data = bytearray(ITEM_TABLE_BASE + (max_index + 1) * ITEM_STRIDE)
    for index, name in cells:
        offset = ITEM_TABLE_BASE + index * ITEM_STRIDE
        raw = encode(name)
        data[offset : offset + len(raw)] = raw
        data[offset + len(raw)] = 0xFF
        data[offset + NAME_FIELD : offset + NAME_FIELD + 2] = b"\xAB\x01"
    return data


class TestBerryNameData(unittest.TestCase):
    def test_exactly_67_berries(self):
        self.assertEqual(len(BERRY_NAMES), 67)

    def test_every_german_name_fits_cell(self):
        for en, de in BERRY_NAMES.items():
            self.assertLessEqual(len(encode(de)) + 1, NAME_FIELD, en)

    def test_every_german_name_is_encodable(self):
        for en, de in BERRY_NAMES.items():
            encode(de)

    def test_german_names_differ_from_english(self):
        for en, de in BERRY_NAMES.items():
            self.assertNotEqual(en, de, en)

    def test_all_german_names_end_with_beere(self):
        for de in BERRY_NAMES.values():
            self.assertTrue(de.endswith("beere"), de)

    def test_known_canonical_mappings(self):
        self.assertEqual(BERRY_NAMES["Oran Berry"], "Sinelbeere")
        self.assertEqual(BERRY_NAMES["Sitrus Berry"], "Tsitrubeere")
        self.assertEqual(BERRY_NAMES["Cheri Berry"], "Amrenabeere")


class TestItemNameData(unittest.TestCase):
    def test_every_german_name_fits_cell(self):
        for en, de in ALL_NAMES.items():
            self.assertLessEqual(len(encode(de)) + 1, NAME_FIELD, en)

    def test_every_german_name_is_encodable(self):
        for en, de in ALL_NAMES.items():
            encode(de)

    def test_berries_and_items_are_disjoint(self):
        overlap = set(BERRY_NAMES) & set(ITEM_NAMES)
        self.assertEqual(overlap, set(), overlap)
        self.assertEqual(len(ALL_NAMES), len(BERRY_NAMES) + len(ITEM_NAMES))

    def test_known_canonical_mappings(self):
        self.assertEqual(ITEM_NAMES["Sun Stone"], "Sonnenstein")
        self.assertEqual(ITEM_NAMES["Heart Scale"], "Herzschuppe")
        self.assertEqual(ITEM_NAMES["Bug Gem"], "Käferjuwel")
        self.assertEqual(ITEM_NAMES["HM01"], "VM01")

    def test_documented_exclusions_are_absent(self):
        # These official German names exceed the 13-glyph cell and must not
        # be present as byte-exact entries (see module docstring).
        for en in ("Room Service", "Bottle Cap", "Purp Nectar"):
            self.assertNotIn(en, ITEM_NAMES, en)

    def test_key_set_matches_fr_minus_documented_exclusions(self):
        import importlib.util

        fr_path = ROOT / "scripts" / "patch_item_names_fr.py"
        spec = importlib.util.spec_from_file_location("patch_item_names_fr", fr_path)
        fr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fr)

        missing = set(fr.ITEM_NAMES) - set(ITEM_NAMES)
        extra = set(ITEM_NAMES) - set(fr.ITEM_NAMES)
        self.assertEqual(missing, {"Room Service", "Bottle Cap", "Purp Nectar"})
        self.assertEqual(extra, set())
        self.assertEqual(set(fr.BERRY_NAMES), set(BERRY_NAMES))


class TestApplyItemNameFixes(unittest.TestCase):
    def test_patches_matching_cells(self):
        data = _make_item_rom([(0, "Aspear Berry"), (1, "Oran Berry")])
        patched = apply_item_name_fixes(data, BERRY_NAMES)
        self.assertEqual(patched, 2)
        self.assertEqual(decode_name(data, ITEM_TABLE_BASE), "Wilbirbeere")
        self.assertEqual(decode_name(data, ITEM_TABLE_BASE + ITEM_STRIDE), "Sinelbeere")

    def test_preserves_item_data_after_name_field(self):
        data = _make_item_rom([(0, "Aspear Berry"), (1, "Sitrus Berry")])
        apply_item_name_fixes(data, BERRY_NAMES)
        for index in (0, 1):
            off = ITEM_TABLE_BASE + index * ITEM_STRIDE + NAME_FIELD
            self.assertEqual(bytes(data[off : off + 2]), b"\xAB\x01")

    def test_idempotent(self):
        data = _make_item_rom([(0, "Aspear Berry")])
        self.assertEqual(apply_item_name_fixes(data, BERRY_NAMES), 1)
        self.assertEqual(apply_item_name_fixes(data, BERRY_NAMES), 0)

    def test_ignores_unknown_names(self):
        data = _make_item_rom([(0, "Potion"), (1, "Master Ball")])
        self.assertEqual(apply_item_name_fixes(data, BERRY_NAMES), 0)
        self.assertEqual(decode_name(data, ITEM_TABLE_BASE), "Potion")

    def test_patches_full_all_names_set(self):
        cells = [(i, en) for i, en in enumerate(ALL_NAMES)]
        data = _make_item_rom(cells)
        self.assertEqual(apply_item_name_fixes(data, ALL_NAMES), len(ALL_NAMES))
        for i, en in enumerate(ALL_NAMES):
            off = ITEM_TABLE_BASE + i * ITEM_STRIDE
            self.assertEqual(decode_name(data, off), ALL_NAMES[en], en)
            data_off = off + NAME_FIELD
            self.assertEqual(bytes(data[data_off : data_off + 2]), b"\xAB\x01", en)


if __name__ == "__main__":
    unittest.main()
