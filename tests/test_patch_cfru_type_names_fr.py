"""Regression guard for scripts/patch_cfru_type_names_fr.py.

Covers the bug fixed for ticket « Corriger les traductions des types Pokémon » :
the Ice type was abbreviated to « GEL », which is the *frozen status* word
(FRZ→GEL). A type must never be displayed with a status name. These tests pin
the type table at 0x3FE890 to French abbreviations, prove no type collides with
the « GEL » / « gel » status strings, and exercise the in-place patcher
end-to-end (including the GEL→GLA migration on an already-built FR ROM).
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.patch_cfru_type_names_fr import (
    CONDITION_PATCHES,
    MIGRATE_FROM,
    TYPE_PATCHES,
    _read_until,
    apply_patches,
    encode,
)

ICE_OFFSET = 0x3FE95F
ROCK_OFFSET = 0x3FE8DC
FROZEN_CONDITION_OFFSET = 0x3FE846


def _seed_rom(seed_overrides: dict[int, str] | None = None) -> bytearray:
    """Build a synthetic ROM seeded with the EN originals of every slot.

    Type slots are written as ``<NAME>\\x00`` (0x00 = space terminator inside the
    packed « a TYPE move » template); condition slots as ``<name>\\xff``.
    ``seed_overrides`` lets a test seed a slot with a different current value
    (e.g. the previous FR « GEL ») to exercise migration.
    """
    overrides = seed_overrides or {}
    size = 0x3FE980
    rom = bytearray(b"\x00" * size)
    for offset, en_expected, _fr in TYPE_PATCHES:
        text = overrides.get(offset, en_expected)
        data = encode(text)
        rom[offset : offset + len(data)] = data
        rom[offset + len(data)] = 0x00  # space terminator
    for offset, en_expected, _fr in CONDITION_PATCHES:
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


class TestCfruTypeNamesFr(unittest.TestCase):
    def test_ice_type_is_glace_not_frozen_status(self):
        """The core bug: Ice (type) must be « GLA », never the « GEL » status."""
        fr_by_offset = {off: fr for off, _en, fr in TYPE_PATCHES}
        self.assertEqual(fr_by_offset[ICE_OFFSET], "GLA")
        self.assertNotEqual(fr_by_offset[ICE_OFFSET], "GEL")

    def test_no_type_name_uses_a_status_word(self):
        """No *type* may reuse a *status* string — that is the status/type confusion."""
        status_words = {"GEL", "gel"}  # FRZ→GEL / frozen condition « gel »
        for _off, _en, fr in TYPE_PATCHES:
            self.assertNotIn(fr, status_words, f"type «{fr}» collides with a status word")

    def test_frozen_condition_stays_gel(self):
        """The frozen *status* condition is legitimately « gel » and stays so."""
        cond = {off: (en, fr) for off, en, fr in CONDITION_PATCHES}
        self.assertEqual(cond[FROZEN_CONDITION_OFFSET], ("ice", "gel"))

    def test_no_fr_name_overflows_its_slot(self):
        for offset, en, fr in TYPE_PATCHES:
            self.assertLessEqual(
                len(encode(fr)), len(en), f"FR «{fr}» overflows EN «{en}» at 0x{offset:X}"
            )

    def test_every_fr_name_encodes(self):
        for _off, _en, fr in (*TYPE_PATCHES, *CONDITION_PATCHES):
            encode(fr)  # raises KeyError if any char is outside the charmap

    def test_applies_from_english_and_is_idempotent(self):
        n, patched = _apply_on(_seed_rom())
        self.assertEqual(n, len(TYPE_PATCHES) + len(CONDITION_PATCHES))
        # Every slot now decodes to its FR value
        for offset, _en, fr in TYPE_PATCHES:
            self.assertEqual(_read_until(patched, offset, 0x00), fr, hex(offset))
        for offset, _en, fr in CONDITION_PATCHES:
            self.assertEqual(_read_until(patched, offset, 0xFF), fr, hex(offset))
        # Re-running is a no-op
        n2, _ = _apply_on(patched)
        self.assertEqual(n2, 0)

    def test_ice_in_rom_decodes_to_gla_not_gel(self):
        _n, patched = _apply_on(_seed_rom())
        self.assertEqual(_read_until(patched, ICE_OFFSET, 0x00), "GLA")
        self.assertEqual(_read_until(patched, ROCK_OFFSET, 0x00), "ROC")

    def test_migrates_previous_gel_to_gla(self):
        """An already-built FR ROM still holding « GEL » must upgrade to « GLA »."""
        self.assertIn(ICE_OFFSET, MIGRATE_FROM)
        self.assertIn("GEL", MIGRATE_FROM[ICE_OFFSET])
        rom = _seed_rom({ICE_OFFSET: "GEL"})
        _n, patched = _apply_on(rom)
        self.assertEqual(_read_until(patched, ICE_OFFSET, 0x00), "GLA")

    def test_skips_unexpected_current_value(self):
        rom = _seed_rom({ICE_OFFSET: "XYZ"})  # neither EN nor a known prior FR
        _n, patched = _apply_on(rom)
        self.assertEqual(_read_until(patched, ICE_OFFSET, 0x00), "XYZ")  # untouched


if __name__ == "__main__":
    unittest.main()
