import struct
import unittest
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.pokedex_stat_labels import (
    GBA_BASE,
    PTR_TABLE_OFFSETS,
    PTR_STRIDE,
    STAT_ORDER,
    _EN_LABELS,
    _FR_LABELS,
    _EN_ENTRIES,
    _FR_ENTRIES,
    apply_to_rom,
)

EN_ROM = Path(__file__).parent.parent / "input" / "roms" / "englishrom.gba"
BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"


def _build_synthetic_rom(table_offset, entries_by_key):
    entry_len = len(next(iter(_EN_ENTRIES.values())))
    str_base = table_offset + len(STAT_ORDER) * PTR_STRIDE
    rom = bytearray(str_base + len(STAT_ORDER) * entry_len + 0x10)
    for i, key in enumerate(STAT_ORDER):
        entry = entries_by_key[key]
        off = str_base + i * entry_len
        rom[off:off + entry_len] = entry
        ptr_off = table_offset + i * PTR_STRIDE
        struct.pack_into("<I", rom, ptr_off, GBA_BASE + off)
    return rom, str_base


def _decode_entry(rom, table_offset, index):
    entry_len = len(next(iter(_EN_ENTRIES.values())))
    ptr = struct.unpack_from("<I", rom, table_offset + index * PTR_STRIDE)[0]
    off = ptr - GBA_BASE
    return bytes(rom[off:off + entry_len])


class TestLabelBudget(unittest.TestCase):
    def test_all_entries_same_length(self):
        lengths = {len(v) for v in _EN_ENTRIES.values()} | {len(v) for v in _FR_ENTRIES.values()}
        self.assertEqual(lengths, {7})

    def test_fr_labels_defined_for_every_stat(self):
        self.assertEqual(set(_FR_LABELS), set(STAT_ORDER))
        self.assertEqual(set(_EN_LABELS), set(STAT_ORDER))


class TestApplyToRom(unittest.TestCase):
    def test_patches_single_table_from_english(self):
        table_offset = PTR_TABLE_OFFSETS[0]
        rom, _ = _build_synthetic_rom(table_offset, _EN_ENTRIES)
        changed = apply_to_rom(rom)
        self.assertEqual(changed, len(STAT_ORDER))
        for i, key in enumerate(STAT_ORDER):
            self.assertEqual(_decode_entry(rom, table_offset, i), _FR_ENTRIES[key])

    def test_idempotent(self):
        table_offset = PTR_TABLE_OFFSETS[0]
        rom, _ = _build_synthetic_rom(table_offset, _FR_ENTRIES)
        self.assertEqual(apply_to_rom(rom), 0)

    def test_dry_run_changes_nothing(self):
        table_offset = PTR_TABLE_OFFSETS[0]
        rom, _ = _build_synthetic_rom(table_offset, _EN_ENTRIES)
        before = bytes(rom)
        changed = apply_to_rom(rom, dry_run=True)
        self.assertEqual(changed, len(STAT_ORDER))
        self.assertEqual(bytes(rom), before)

    def test_var2_placeholder_and_terminator_preserved(self):
        table_offset = PTR_TABLE_OFFSETS[0]
        rom, _ = _build_synthetic_rom(table_offset, _EN_ENTRIES)
        apply_to_rom(rom)
        entry = _decode_entry(rom, table_offset, 0)
        self.assertEqual(entry[-3:], bytes([0xFD, 0x02, 0xFF]))


@pytest.mark.rom
class TestEnglishRomPointers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not EN_ROM.exists():
            pytest.skip("englishrom.gba not found")
        cls.rom = bytearray(EN_ROM.read_bytes())

    def test_english_entries_are_known(self):
        for table_offset in PTR_TABLE_OFFSETS:
            for i, key in enumerate(STAT_ORDER):
                self.assertEqual(
                    _decode_entry(self.rom, table_offset, i), _EN_ENTRIES[key]
                )

    def test_patch_produces_french(self):
        rom = bytearray(self.rom)
        changed = apply_to_rom(rom)
        self.assertEqual(changed, len(STAT_ORDER) * len(PTR_TABLE_OFFSETS))
        for table_offset in PTR_TABLE_OFFSETS:
            for i, key in enumerate(STAT_ORDER):
                self.assertEqual(
                    _decode_entry(rom, table_offset, i), _FR_ENTRIES[key]
                )


@pytest.mark.rom
class TestBuiltFrRom(unittest.TestCase):
    """The shipped FR ROM must already show the French stat abbreviations."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        cls.rom = BUILT_FR_ROM.read_bytes()

    def test_built_rom_shows_french_labels(self):
        for table_offset in PTR_TABLE_OFFSETS:
            for i, key in enumerate(STAT_ORDER):
                self.assertEqual(
                    _decode_entry(self.rom, table_offset, i), _FR_ENTRIES[key]
                )


if __name__ == "__main__":
    unittest.main()
