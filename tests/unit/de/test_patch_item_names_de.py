"""Regression guard for languages/de/patches/item_names.py (mirrors the FR suite)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from src.core.text_codec import GERMAN_UMLAUT_CHARS, TextDecoder, TextEncoder

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from languages.de.patches import item_names as mod  # noqa: E402

ALL_NAMES = mod.ALL_NAMES
BERRY_NAMES = mod.BERRY_NAMES
ITEM_NAMES = mod.ITEM_NAMES
ITEM_DESC_OVERRIDES = mod.ITEM_DESC_OVERRIDES
ITEM_STRIDE = mod.ITEM_STRIDE
ITEM_TABLE_BASE = mod.ITEM_TABLE_BASE
NAME_FIELD = mod.NAME_FIELD
apply_item_desc_fixes = mod.apply_item_desc_fixes
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
        self.assertEqual(ITEM_NAMES["HP Up"], "KP-Plus")

    def test_documented_exclusions_are_absent(self):
        # These official German names exceed the 13-glyph cell and must not
        # be present as byte-exact entries (see module docstring).
        for en in ("Room Service", "Bottle Cap", "Purp Nectar"):
            self.assertNotIn(en, ITEM_NAMES, en)

    def test_key_set_matches_fr_minus_documented_exclusions(self):
        import importlib.util

        fr_path = ROOT / "languages" / "fr" / "patches" / "item_names.py"
        spec = importlib.util.spec_from_file_location("patch_item_names_fr", fr_path)
        fr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fr)

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
        # This abbreviated source value is injected only by the FR pipeline;
        # the DE source cell still contains "Super Repel".
        fr_only_source_keys = {"Sup. Repouss"}
        missing = set(fr.ITEM_NAMES) - set(ITEM_NAMES)
        extra = set(ITEM_NAMES) - set(fr.ITEM_NAMES)
        self.assertEqual(
            missing,
            {"Room Service", "Bottle Cap", "Purp Nectar"} | fr_only_source_keys,
        )
        # FR receives this medicine name through its legacy translation data;
        # DE must patch the fixed gItems cell explicitly.
        self.assertEqual(extra, standard_ball_keys | {"HP Up"})
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

    def test_patches_hp_up_to_official_kp_plus(self):
        data = _make_item_rom([(0, "HP Up")])

        self.assertEqual(apply_item_name_fixes(data, ALL_NAMES), 1)
        self.assertEqual(decode_name(data, ITEM_TABLE_BASE), "KP-Plus")


class TestItemDescOverrides(unittest.TestCase):
    """Master Ball description (issue #40): the item's NAME cell already reads
    "Meisterball", but its description pointer targets an untranslated,
    class-2 base-ROM cell (absent from translation_ready.json and the
    Spanish extraction), same rationale as fixed_table_names.py.
    """

    def _make_desc_rom(self, offset: int, text: str, slack: int = 0) -> bytearray:
        raw = TextEncoder.encode_pokemon(text, skip_aliases=GERMAN_UMLAUT_CHARS)
        data = bytearray(offset + len(raw) + slack)
        data[offset : offset + len(raw)] = raw
        return data

    def test_master_ball_override_registered(self):
        self.assertIn(0x3D4ECC, ITEM_DESC_OVERRIDES)

    def test_every_override_is_encodable_with_german_umlauts_preserved(self):
        for offset, text in ITEM_DESC_OVERRIDES.items():
            encoded = TextEncoder.encode_pokemon(text, skip_aliases=GERMAN_UMLAUT_CHARS)
            decoded = TextDecoder.decode(encoded, "pokemon")
            self.assertEqual(decoded, text, hex(offset))

    def test_patches_matching_offset(self):
        original = (
            "The best Ball with the ultimate\n"
            "performance. It will catch any wild\n"
            "Pokémon without fail."
        )
        data = self._make_desc_rom(0x3D4ECC, original)
        patched = apply_item_desc_fixes(data)
        self.assertEqual(patched, 1)
        expected = TextEncoder.encode_pokemon(
            ITEM_DESC_OVERRIDES[0x3D4ECC], skip_aliases=GERMAN_UMLAUT_CHARS
        )
        self.assertEqual(bytes(data[0x3D4ECC : 0x3D4ECC + len(expected)]), expected)

    def test_replacement_fits_without_expanding_slot(self):
        # The override must never be longer than the original English slot it
        # replaces, so it always applies without relocation.
        original = (
            "The best Ball with the ultimate\n"
            "performance. It will catch any wild\n"
            "Pokémon without fail."
        )
        data = self._make_desc_rom(0x3D4ECC, original)
        original_len = len(TextEncoder.encode_pokemon(original))
        new_len = len(
            TextEncoder.encode_pokemon(
                ITEM_DESC_OVERRIDES[0x3D4ECC], skip_aliases=GERMAN_UMLAUT_CHARS
            )
        )
        self.assertLessEqual(new_len, original_len)
        apply_item_desc_fixes(data)  # must not raise / not skip

    def test_idempotent(self):
        original = (
            "The best Ball with the ultimate\n"
            "performance. It will catch any wild\n"
            "Pokémon without fail."
        )
        data = self._make_desc_rom(0x3D4ECC, original)
        apply_item_desc_fixes(data)
        # Re-applying against already-patched bytes must still find room and
        # rewrite the identical bytes (no exception, no growth).
        self.assertEqual(apply_item_desc_fixes(data), 1)

    def test_skips_when_slot_too_small(self):
        data = self._make_desc_rom(0x3D4ECC, "Short.")
        self.assertEqual(apply_item_desc_fixes(data), 0)


if __name__ == "__main__":
    unittest.main()
