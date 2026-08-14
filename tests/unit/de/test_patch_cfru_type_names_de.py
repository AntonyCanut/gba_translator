"""Regression guard for languages/de/patches/cfru_type_names.py.

Mirrors tests/test_patch_cfru_type_names_fr.py: pins the type table at
0x3FE890 to German abbreviations, checks every slot fits its EN-original byte
budget, and exercises the in-place patcher end-to-end (apply from a fresh
English ROM, idempotent re-run, ignore unexpected current values).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from languages.de.patches import cfru_type_names as mod  # noqa: E402

CONDITION_PATCHES = mod.CONDITION_PATCHES
TYPE_PATCHES = mod.TYPE_PATCHES
_read_until = mod._read_until
apply_patches = mod.apply_patches
encode = mod.encode

ICE_OFFSET = 0x3FE95F


def _seed_rom(seed_overrides: dict[int, str] | None = None) -> bytearray:
    overrides = seed_overrides or {}
    size = 0x3FE980
    rom = bytearray(b"\x00" * size)
    for offset, en_expected, _de in TYPE_PATCHES:
        text = overrides.get(offset, en_expected)
        data = encode(text)
        rom[offset : offset + len(data)] = data
        rom[offset + len(data)] = 0x00  # space terminator
    for offset, en_expected, _de in CONDITION_PATCHES:
        text = overrides.get(offset, en_expected)
        data = encode(text)
        rom[offset : offset + len(data)] = data
        rom[offset + len(data)] = 0xFF
    return rom


def _apply_on(rom: bytearray) -> tuple[int, bytearray]:
    with TemporaryDirectory() as d:
        p = Path(d) / "rom.gba"
        p.write_bytes(rom)
        n = apply_patches(p)
        return n, bytearray(p.read_bytes())


class TestCfruTypeNamesDe(unittest.TestCase):
    def test_no_de_name_overflows_its_slot(self):
        for offset, en, de in TYPE_PATCHES:
            self.assertLessEqual(
                len(encode(de)), len(en), f"DE «{de}» overflows EN «{en}» at 0x{offset:X}"
            )

    def test_every_de_name_encodes(self):
        for _off, _en, de in (*TYPE_PATCHES, *CONDITION_PATCHES):
            encode(de)  # raises KeyError if any char is outside the charmap

    def test_normal_type_is_not_in_type_patches(self):
        # NORMAL is identical in German — no patch entry should exist for it.
        offsets = {off for off, _en, _de in TYPE_PATCHES}
        self.assertNotIn(0x3FE894, offsets)

    def test_ice_type_is_eis(self):
        de_by_offset = {off: de for off, _en, de in TYPE_PATCHES}
        self.assertEqual(de_by_offset[ICE_OFFSET], "EIS")

    def test_constrained_type_cells_use_stable_official_stems(self):
        de_by_english = {en: de for _off, en, de in TYPE_PATCHES}
        self.assertEqual(de_by_english["ROCK"], "GES")
        self.assertEqual(de_by_english["BUG"], "KÄF")
        self.assertEqual(de_by_english["FIRE"], "FEU")
        self.assertEqual(de_by_english["WATER"], "WAS")
        self.assertEqual(de_by_english["GRASS"], "PFL")
        self.assertEqual(de_by_english["DARK"], "UNL")
        self.assertEqual(CONDITION_PATCHES, [(0x3FE846, "ice", "gef")])

    def test_applies_from_english_and_is_idempotent(self):
        n, patched = _apply_on(_seed_rom())
        self.assertEqual(n, len(TYPE_PATCHES) + len(CONDITION_PATCHES))
        for offset, _en, de in TYPE_PATCHES:
            self.assertEqual(_read_until(patched, offset, 0x00), de, hex(offset))
        for offset, _en, de in CONDITION_PATCHES:
            self.assertEqual(_read_until(patched, offset, 0xFF), de, hex(offset))
        # Re-running is a no-op
        n2, _ = _apply_on(patched)
        self.assertEqual(n2, 0)

    def test_replaces_condition_pretranslated_by_generic_pipeline(self):
        condition_offset, _english, expected = CONDITION_PATCHES[0]
        n, patched = _apply_on(_seed_rom({condition_offset: "Eis"}))
        self.assertEqual(n, len(TYPE_PATCHES) + 1)
        self.assertEqual(_read_until(patched, condition_offset, 0xFF), expected)

    def test_skips_unexpected_current_value(self):
        rom = _seed_rom({ICE_OFFSET: "XYZ"})  # neither EN nor DE
        _n, patched = _apply_on(rom)
        self.assertEqual(_read_until(patched, ICE_OFFSET, 0x00), "XYZ")  # untouched


if __name__ == "__main__":
    unittest.main()
