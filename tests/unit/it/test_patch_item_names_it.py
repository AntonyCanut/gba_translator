"""Regression guard for languages/it/patches/item_names.py (mirrors the DE suite)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from languages.it.patches import item_names as mod  # noqa: E402

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

    def test_every_italian_name_fits_cell(self):
        for en, it in BERRY_NAMES.items():
            self.assertLessEqual(len(encode(it)) + 1, NAME_FIELD, en)

    def test_every_italian_name_is_encodable(self):
        for en, it in BERRY_NAMES.items():
            encode(it)

    def test_italian_names_differ_from_english(self):
        for en, it in BERRY_NAMES.items():
            self.assertNotEqual(en, it, en)

    def test_all_italian_names_start_with_bacca(self):
        for it in BERRY_NAMES.values():
            self.assertTrue(it.startswith("Bacca"), it)

    def test_known_canonical_mappings(self):
        self.assertEqual(BERRY_NAMES["Sitrus Berry"], "Baccacedro")
        self.assertEqual(BERRY_NAMES["Cheri Berry"], "Baccaliegia")


class TestItemNameData(unittest.TestCase):
    def test_every_italian_name_fits_cell(self):
        for en, it in ALL_NAMES.items():
            self.assertLessEqual(len(encode(it)) + 1, NAME_FIELD, en)

    def test_every_italian_name_is_encodable(self):
        for en, it in ALL_NAMES.items():
            encode(it)

    def test_berries_and_items_are_disjoint(self):
        overlap = set(BERRY_NAMES) & set(ITEM_NAMES)
        self.assertEqual(overlap, set(), overlap)
        self.assertEqual(len(ALL_NAMES), len(BERRY_NAMES) + len(ITEM_NAMES))

    def test_known_canonical_mappings(self):
        self.assertEqual(ITEM_NAMES["Sun Stone"], "Pietrasolare")
        self.assertEqual(ITEM_NAMES["Normal Gem"], "Bijounormale")
        self.assertEqual(ITEM_NAMES["HM01"], "MN01")

    def test_documented_exclusions_are_absent(self):
        # These official Italian names exceed the 13-glyph cell and must not
        # be present as byte-exact entries (see module docstring).
        for en in ("Exp. Share", "Soft Sand", "Room Service", "Bug Gem",
                   "Bug Memory", "Bottle Cap", "Eon Ticket"):
            self.assertNotIn(en, ITEM_NAMES, en)

    def test_key_set_matches_fr_minus_documented_exclusions(self):
        import importlib.util

        fr_path = ROOT / "languages" / "fr" / "patches" / "item_names.py"
        spec = importlib.util.spec_from_file_location("patch_item_names_fr", fr_path)
        fr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fr)

        expected_exclusions = {
            "Exp. Share", "Soft Sand", "Room Service", "Bug Gem",
            "Bug Memory", "Bottle Cap", "Eon Ticket",
        }
        # The standard Poké Ball line is keyed on its FRENCH source string: the
        # Unbound base ROM ships those inline gItems cells pre-localised to
        # French (see the item_names.py docstring). FR needs no entry — the
        # source string already IS the correct French name — so IT/DE
        # legitimately carry these 16 keys that FR does not.
        standard_ball_keys = {
            "Hyper Ball", "Super Ball", "Master Ball", "Poké Ball",
            "Safari Ball", "Filet Ball", "Scuba Ball", "Faiblo Ball",
            "Bis Ball", "Chrono Ball", "Luxe Ball", "Honor Ball",
            "Mémoire Ball", "Sombre Ball", "Soin Ball", "Rapide Ball",
        }
        missing = set(fr.ITEM_NAMES) - set(ITEM_NAMES)
        extra = set(ITEM_NAMES) - set(fr.ITEM_NAMES)
        self.assertEqual(missing, expected_exclusions)
        self.assertEqual(extra, standard_ball_keys)
        self.assertEqual(set(fr.BERRY_NAMES), set(BERRY_NAMES))


class TestApplyItemNameFixes(unittest.TestCase):
    def test_patches_matching_cells(self):
        data = _make_item_rom([(0, "Aspear Berry"), (1, "Oran Berry")])
        patched = apply_item_name_fixes(data, BERRY_NAMES)
        self.assertEqual(patched, 2)
        self.assertEqual(decode_name(data, ITEM_TABLE_BASE), BERRY_NAMES["Aspear Berry"])
        self.assertEqual(
            decode_name(data, ITEM_TABLE_BASE + ITEM_STRIDE), BERRY_NAMES["Oran Berry"]
        )

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
