import struct
import unittest
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.text_codec import POKEMON_TABLE
from languages.fr.patches.status_abbrevs import (
    GBA_BASE,
    PTR_TABLE_OFFSET,
    PTR_STRIDE,
    STATUS_PATCHES,
    apply_to_rom,
    _encode,
    _decode_at,
    _patches_from_registry,
)

EN_ROM = Path(__file__).parent.parent / "input" / "roms" / "englishrom.gba"
BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"

# Expected FR target per table index (PAR at index 2 is intentionally absent).
EXPECTED_FR = {0: "SOM", 1: "POI", 3: "BRU", 4: "GEL"}


def _build_synthetic_rom(strings_by_index):
    """Build a tiny ROM with a pointer table at PTR_TABLE_OFFSET pointing at
    3-char strings. `strings_by_index` maps table index -> str to place."""
    # String area sits just past the pointer table.
    str_base = PTR_TABLE_OFFSET + 8 * PTR_STRIDE  # room for 8 slots
    rom = bytearray(str_base + 0x100)
    for idx, text in strings_by_index.items():
        off = str_base + idx * 8
        enc = _encode(text)
        rom[off : off + len(enc)] = enc
        rom[off + len(enc)] = 0xFF
        ptr_off = PTR_TABLE_OFFSET + idx * PTR_STRIDE
        struct.pack_into("<I", rom, ptr_off, GBA_BASE + off)
    return rom, str_base


def _decode_index(rom, idx):
    ptr = struct.unpack_from("<I", rom, PTR_TABLE_OFFSET + idx * PTR_STRIDE)[0]
    return _decode_at(rom, ptr - GBA_BASE)


class TestStatusPatchTable(unittest.TestCase):
    def test_targets_match_ticket(self):
        targets = {e["index"]: e["fr"] for e in STATUS_PATCHES}
        self.assertEqual(targets, EXPECTED_FR)

    def test_par_index_not_patched(self):
        # index 2 (PAR) must never be in the patch table.
        self.assertNotIn(2, {e["index"] for e in STATUS_PATCHES})

    def test_all_targets_three_chars_and_encodable(self):
        for e in STATUS_PATCHES:
            self.assertEqual(len(e["fr"]), 3, e)
            # Encodes without KeyError and is no longer than the EN original.
            self.assertLessEqual(len(_encode(e["fr"])), len(e["en"]))


class TestApplyToRom(unittest.TestCase):
    def test_patches_from_english(self):
        rom, _ = _build_synthetic_rom(
            {0: "SLP", 1: "PSN", 2: "PAR", 3: "BRN", 4: "FRZ"}
        )
        changed = apply_to_rom(rom)
        self.assertEqual(changed, 4)  # PAR untouched
        for idx, fr in EXPECTED_FR.items():
            self.assertEqual(_decode_index(rom, idx), fr)
        self.assertEqual(_decode_index(rom, 2), "PAR")

    def test_self_heals_prior_dor(self):
        # An older build shipped "DOR" for sleep; re-running must converge to SOM.
        rom, _ = _build_synthetic_rom(
            {0: "DOR", 1: "POI", 2: "PAR", 3: "BRU", 4: "GEL"}
        )
        changed = apply_to_rom(rom)
        self.assertEqual(changed, 1)
        self.assertEqual(_decode_index(rom, 0), "SOM")

    def test_self_heals_prior_emp_and_brl(self):
        # An older build shipped "EMP"/"BRL"; re-running must converge to the
        # F-108 targets "POI"/"BRU" (kept in sync with the status_badges.py
        # graphic patch).
        rom, _ = _build_synthetic_rom(
            {0: "SOM", 1: "EMP", 2: "PAR", 3: "BRL", 4: "GEL"}
        )
        changed = apply_to_rom(rom)
        self.assertEqual(changed, 2)
        self.assertEqual(_decode_index(rom, 1), "POI")
        self.assertEqual(_decode_index(rom, 3), "BRU")

    def test_idempotent(self):
        rom, _ = _build_synthetic_rom(
            {0: "SOM", 1: "POI", 2: "PAR", 3: "BRU", 4: "GEL"}
        )
        self.assertEqual(apply_to_rom(rom), 0)

    def test_dry_run_changes_nothing(self):
        rom, _ = _build_synthetic_rom(
            {0: "SLP", 1: "PSN", 2: "PAR", 3: "BRN", 4: "FRZ"}
        )
        before = bytes(rom)
        changed = apply_to_rom(rom, dry_run=True)
        self.assertEqual(changed, 4)
        self.assertEqual(bytes(rom), before)

    def test_terminator_preserved(self):
        rom, str_base = _build_synthetic_rom({0: "SLP"})
        apply_to_rom(rom)
        off = struct.unpack_from("<I", rom, PTR_TABLE_OFFSET)[0] - GBA_BASE
        self.assertEqual(rom[off + 3], 0xFF)


@pytest.mark.rom
class TestEnglishRomPointers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not EN_ROM.exists():
            pytest.skip("englishrom.gba not found")
        cls.rom = bytearray(EN_ROM.read_bytes())

    def test_english_strings_are_known(self):
        en = {0: "SLP", 1: "PSN", 2: "PAR", 3: "BRN", 4: "FRZ"}
        for idx, expected in en.items():
            self.assertEqual(_decode_index(self.rom, idx), expected)

    def test_patch_produces_french(self):
        rom = bytearray(self.rom)
        apply_to_rom(rom)
        for idx, fr in EXPECTED_FR.items():
            self.assertEqual(_decode_index(rom, idx), fr)
        self.assertEqual(_decode_index(rom, 2), "PAR")


@pytest.mark.rom
class TestBuiltFrRom(unittest.TestCase):
    """The shipped FR ROM must already show the official FR abbreviations."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        cls.rom = BUILT_FR_ROM.read_bytes()

    def test_built_rom_shows_french_abbrevs(self):
        for idx, fr in EXPECTED_FR.items():
            self.assertEqual(_decode_index(self.rom, idx), fr)
        self.assertEqual(_decode_index(self.rom, 2), "PAR")


class TestPatchesFromRegistry(unittest.TestCase):
    """Unit-test _patches_from_registry() with synthetic abbrev dicts."""

    def test_italian_abbrevs_produce_correct_patches(self):
        it_abbrevs = {
            "poison": "PSN",     # same as EN → skipped
            "burn": "SCT",
            "freeze": "CON",
            "paralysis": "PAR",  # same as EN → skipped
            "sleep": "SON",
            "faint": "KO",       # not in the table → ignored
        }
        patches = _patches_from_registry(it_abbrevs)
        targets = {e["index"]: e["fr"] for e in patches}
        # poison (PSN==PSN) and paralysis (PAR==PAR) must be absent
        self.assertNotIn(1, targets)  # poison
        self.assertNotIn(2, targets)  # paralysis
        # actual changes
        self.assertEqual(targets[3], "SCT")  # burn
        self.assertEqual(targets[4], "CON")  # freeze
        self.assertEqual(targets[0], "SON")  # sleep

    def test_german_abbrevs_produce_correct_patches(self):
        de_abbrevs = {
            "poison": "GIF",
            "burn": "VBR",
            "freeze": "GEF",
            "paralysis": "PAR",  # same as EN → skipped
            "sleep": "SCH",
            "faint": "KO",
        }
        patches = _patches_from_registry(de_abbrevs)
        targets = {e["index"]: e["fr"] for e in patches}
        self.assertNotIn(2, targets)  # PAR == PAR
        self.assertEqual(targets[0], "SCH")  # sleep
        self.assertEqual(targets[1], "GIF")  # poison
        self.assertEqual(targets[3], "VBR")  # burn
        self.assertEqual(targets[4], "GEF")  # freeze

    def test_prior_set_is_empty_for_registry_derived_patches(self):
        patches = _patches_from_registry({"sleep": "SON"})
        self.assertEqual(patches[0]["prior"], set())

    def test_all_same_as_en_returns_empty(self):
        all_same = {"sleep": "SLP", "poison": "PSN", "paralysis": "PAR",
                    "burn": "BRN", "freeze": "FRZ"}
        self.assertEqual(_patches_from_registry(all_same), [])

    def test_apply_to_rom_uses_registry_patches(self):
        rom, _ = _build_synthetic_rom(
            {0: "SLP", 1: "PSN", 2: "PAR", 3: "BRN", 4: "FRZ"}
        )
        it_patches = _patches_from_registry({
            "sleep": "SON", "poison": "PSN", "paralysis": "PAR",
            "burn": "SCT", "freeze": "CON", "faint": "KO",
        })
        changed = apply_to_rom(rom, patches=it_patches)
        self.assertEqual(changed, 3)  # sleep, burn, freeze changed; PSN/PAR skipped
        self.assertEqual(_decode_index(rom, 0), "SON")
        self.assertEqual(_decode_index(rom, 1), "PSN")  # unchanged
        self.assertEqual(_decode_index(rom, 2), "PAR")  # unchanged
        self.assertEqual(_decode_index(rom, 3), "SCT")
        self.assertEqual(_decode_index(rom, 4), "CON")


if __name__ == "__main__":
    unittest.main()
