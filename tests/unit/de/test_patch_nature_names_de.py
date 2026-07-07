"""Regression guard for languages/de/patches/nature_names.py.

The relocate+repoint mechanics are byte-identical to the French version
(tests/test_nature_names_fr.py already exercises the live-pointer-table
regression against a real built ROM); this file covers what's DE-specific:
every official German nature name is encodable, none collides with its
English original, and the generic apply()/verify() contract works end-to-end
on a small synthetic ROM (using ``targets=`` overrides rather than the real
fixed 0x463xxx addresses, so it needs neither a built ROM nor the full
25-entry pointer tables).
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from src.core.text_codec import GERMAN_UMLAUT_CHARS, TextEncoder  # noqa: E402
from languages.de.patches import nature_names as mod  # noqa: E402

TARGETS = mod.TARGETS
ROM_POINTER_BASE = mod.ROM_POINTER_BASE


class TestNatureNameData(unittest.TestCase):
    def test_exactly_25_natures(self):
        self.assertEqual(len(TARGETS), 25)

    def test_every_name_is_encodable(self):
        for offset, name in TARGETS.items():
            TextEncoder.encode(name, "pokemon")  # raises if any char is unmapped

    def test_known_canonical_mappings(self):
        by_offset = TARGETS
        self.assertEqual(by_offset[0x463DBC], "Robust")  # Hardy
        self.assertEqual(by_offset[0x463DFA], "Lasch")    # Lax
        self.assertEqual(by_offset[0x463DFE], "Scheu")    # Timid
        self.assertEqual(by_offset[0x463E57], "Kauzig")   # Quirky

    def test_names_are_unique(self):
        names = list(TARGETS.values())
        self.assertEqual(len(names), len(set(names)), names)

    def test_names_with_umlauts_are_present(self):
        # Issue #53 follow-up: "Kühn" (Bold) and "Mäßig" (Modest) must keep
        # their umlaut, not the ASCII-folded "Kuhn"/"Maßig".
        names = list(TARGETS.values())
        self.assertIn("Kühn", names)
        self.assertIn("Mäßig", names)


class TestApplyAndVerify(unittest.TestCase):
    """Exercise the index/table-based apply()+verify() on a small synthetic ROM.

    Two 25×4-byte pointer tables are placed at small offsets (the real
    0x463E60 / 0x1FE65F4 wouldn't fit a synthetic ROM) and pre-seeded to point
    at English strings — mimicking a fresh EN ROM. This mirrors what the DE
    build actually needs: repointing must work off the table *index*, never a
    referrer-search on the original offsets (the B-158 blocker).
    """

    TABLE_A = 0x40
    TABLE_B = 0xE0
    TABLES = (TABLE_A, TABLE_B)

    def _build_rom(self, en_names: list[str]) -> bytearray:
        rom = bytearray(b"\xff" * 0x10000)  # 0xFF == free space for the allocator
        # Pack EN strings back-to-back well below the 0x230000 excluded range,
        # then point both tables' entry i at the shared string, like the EN ROM.
        cursor = 0x200
        for i, name in enumerate(en_names):
            encoded = TextEncoder.encode(name, "pokemon")
            rom[cursor: cursor + len(encoded)] = encoded
            ptr = struct.pack("<I", ROM_POINTER_BASE + cursor)
            rom[self.TABLE_A + 4 * i: self.TABLE_A + 4 * i + 4] = ptr
            rom[self.TABLE_B + 4 * i: self.TABLE_B + 4 * i + 4] = ptr
            cursor += len(encoded)
        return rom

    def test_apply_repoints_both_tables_by_index(self):
        en = ["Hardy", "Lonely", "Brave"]
        de = ["Robust", "Einsam", "Mutig"]
        rom = self._build_rom(en)
        stats = mod.apply(rom, names=de, tables=self.TABLES)
        self.assertEqual(stats["relocated"], 3)
        self.assertEqual(stats["repointed"], 6)  # 3 names × 2 tables
        self.assertEqual(stats["failed"], 0)

        for i, name in enumerate(de):
            pa = struct.unpack_from("<I", rom, self.TABLE_A + 4 * i)[0]
            pb = struct.unpack_from("<I", rom, self.TABLE_B + 4 * i)[0]
            self.assertEqual(pa, pb, "both tables must share the relocated string")
            off = pa - ROM_POINTER_BASE
            want = TextEncoder.encode(name, "pokemon")
            self.assertEqual(bytes(rom[off: off + len(want)]), want)

    def test_verify_clean_after_apply(self):
        en = ["Hardy", "Lonely", "Brave"]
        de = ["Robust", "Einsam", "Mutig"]
        rom = self._build_rom(en)
        mod.apply(rom, names=de, tables=self.TABLES)
        self.assertEqual(mod.verify(rom, names=de, tables=self.TABLES), [])

    def test_verify_flags_unrepointed_entry(self):
        # A table still aimed at the (shorter) English original must be flagged.
        en = ["Hardy", "Lonely", "Brave"]
        de = ["Robust", "Einsam", "Mutig"]
        rom = self._build_rom(en)
        bad = mod.verify(rom, names=de, tables=self.TABLES)
        self.assertEqual(len(bad), 3, bad)

    def test_apply_is_idempotent(self):
        en = ["Hardy", "Lonely", "Brave"]
        de = ["Robust", "Einsam", "Mutig"]
        rom = self._build_rom(en)
        mod.apply(rom, names=de, tables=self.TABLES)
        stats = mod.apply(rom, names=de, tables=self.TABLES)
        self.assertEqual(stats["relocated"], 0)
        self.assertEqual(stats["skipped"], 3)
        self.assertEqual(mod.verify(rom, names=de, tables=self.TABLES), [])

    def test_apply_preserves_umlauts_in_official_names(self):
        # Issue #53 follow-up: TextEncoder.encode(text, "pokemon") without
        # skip_aliases=GERMAN_UMLAUT_CHARS folds ü/ä/ö to ASCII (u/a/o) via
        # ENCODE_ALIASES before the umlaut glyph slots (0xF1-0xF6) are ever
        # reached, so "Kühn" was relocated into the ROM as "Kuhn" — matching
        # the in-game screenshot report. apply() must use the umlaut-aware
        # encoding, same as languages/de/patches/item_names.py and
        # pokedex.py.
        en = ["Bold", "Modest"]
        de = ["Kühn", "Mäßig"]
        rom = self._build_rom(en)
        mod.apply(rom, names=de, tables=self.TABLES)

        for i, name in enumerate(de):
            pa = struct.unpack_from("<I", rom, self.TABLE_A + 4 * i)[0]
            off = pa - ROM_POINTER_BASE
            want = TextEncoder.encode(name, "pokemon", skip_aliases=GERMAN_UMLAUT_CHARS)
            got = bytes(rom[off: off + len(want)])
            self.assertEqual(got, want, f"{name!r} lost its umlaut glyph: {got.hex()}")

        self.assertEqual(mod.verify(rom, names=de, tables=self.TABLES), [])

    def test_default_allocation_does_not_require_spanish_reserved_space(self):
        # The full DE release build runs this patch late, after the generic
        # reinserter has already honored the Spanish pointer-proof ROM. CI run
        # #29 exposed that reserving Spanish-populated bytes again can exhaust
        # all available blocks, even though the current DE ROM has safe room.
        en = ["Hardy", "Lonely", "Brave"]
        de = ["Robust", "Einsam", "Mutig"]
        reserved = b"\x00" * 0x10000
        rom_with_reservation = self._build_rom(en)
        self.assertEqual(
            mod.apply(
                rom_with_reservation,
                names=de,
                tables=self.TABLES,
                reserved_rom=reserved,
            )["failed"],
            3,
        )

        rom_without_reservation = self._build_rom(en)
        stats = mod.apply(rom_without_reservation, names=de, tables=self.TABLES)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(mod.verify(rom_without_reservation, names=de, tables=self.TABLES), [])


if __name__ == "__main__":
    unittest.main()
