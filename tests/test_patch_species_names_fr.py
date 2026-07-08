"""Unit tests for languages/fr/patches/species_names.py.

Species names live in a fixed-width 11-byte, 1293-entry table at file offset
0x166A997 ("Bulbasaur", National Dex #1) through index 1292 ("Urshifu", the
last Unbound-expanded slot). Unlike the move-name table this table is never
relocated by any build pipeline in this repo, so the offset used to key
combined_<code>.txt entries IS the live table location — no pointer
resolution needed.
"""

import unittest

from languages.fr.patches.species_names import (
    SPECIES_STRIDE,
    SPECIES_TABLE_OFFSET,
    _encode,
    apply_to_rom,
)


def _rom_with_cell(offset: int, name: str, size: int) -> bytearray:
    data = bytearray(b"\xff" * size)
    raw = _encode(name)
    data[offset : offset + len(raw)] = raw
    data[offset + len(raw)] = 0xFF
    return data


class TestApplyToRom(unittest.TestCase):
    def test_patches_english_cell(self):
        index = 0
        offset = SPECIES_TABLE_OFFSET + index * SPECIES_STRIDE
        data = _rom_with_cell(offset, "Bulbasaur", offset + SPECIES_STRIDE)
        translations = {offset: "Bisasam"}

        patched, warnings = apply_to_rom(data, translations, count=index + 1)

        self.assertEqual(patched, 1)
        self.assertEqual(warnings, [])
        raw = _encode("Bisasam")
        self.assertEqual(bytes(data[offset : offset + len(raw)]), raw)
        self.assertEqual(data[offset + len(raw)], 0xFF)

    def test_idempotent(self):
        index = 1
        offset = SPECIES_TABLE_OFFSET + index * SPECIES_STRIDE
        data = _rom_with_cell(offset, "Bisaknosp", offset + SPECIES_STRIDE)
        translations = {offset: "Bisaknosp"}

        apply_to_rom(data, translations, count=index + 1)
        patched, _ = apply_to_rom(data, translations, count=index + 1)
        self.assertEqual(patched, 0)

    def test_skips_index_without_translation(self):
        index = 2
        offset = SPECIES_TABLE_OFFSET + index * SPECIES_STRIDE
        data = _rom_with_cell(offset, "Venusaur", offset + SPECIES_STRIDE)

        patched, warnings = apply_to_rom(data, {}, count=index + 1)

        self.assertEqual(patched, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(
            bytes(data[offset : offset + len(_encode("Venusaur"))]),
            _encode("Venusaur"),
        )

    def test_warns_and_skips_overflowing_name(self):
        index = 3
        offset = SPECIES_TABLE_OFFSET + index * SPECIES_STRIDE
        data = _rom_with_cell(offset, "Charmander", offset + SPECIES_STRIDE)
        # 11 chars + terminator = 12 > 11-byte cell.
        translations = {offset: "Salamander!"}

        patched, warnings = apply_to_rom(data, translations, count=index + 1)

        self.assertEqual(patched, 0)
        self.assertEqual(len(warnings), 1)
        self.assertIn("byte cell", warnings[0])
        self.assertEqual(
            bytes(data[offset : offset + len(_encode("Charmander"))]),
            _encode("Charmander"),
        )

    def test_stops_at_end_of_buffer(self):
        index = 0
        offset = SPECIES_TABLE_OFFSET + index * SPECIES_STRIDE
        data = _rom_with_cell(offset, "Bulbasaur", offset + SPECIES_STRIDE)
        translations = {offset: "Bisasam", offset + SPECIES_STRIDE: "Bisaknosp"}

        # count=2 but the buffer only holds index 0 — index 1 must be skipped,
        # not raise an IndexError.
        patched, warnings = apply_to_rom(data, translations, count=2)

        self.assertEqual(patched, 1)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
