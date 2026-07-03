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

from src.core.text_codec import TextEncoder  # noqa: E402
import patch_nature_names_de as mod  # noqa: E402

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
        self.assertEqual(by_offset[0x463DBC], "Robust")   # Hardy
        self.assertEqual(by_offset[0x463DFA], "Nachlässig")  # Lax
        self.assertEqual(by_offset[0x463DFE], "Ängstlich")   # Timid
        self.assertEqual(by_offset[0x463E57], "Wunderlich")  # Quirky

    def test_names_are_unique(self):
        names = list(TARGETS.values())
        self.assertEqual(len(names), len(set(names)), names)


class TestApplyAndVerify(unittest.TestCase):
    def _build_rom(self, offset: int, en_text: str, referrer_offset: int) -> bytearray:
        size = 0x10000
        rom = bytearray(b"\xff" * size)
        # A large enough free run (below the 0x230000 excluded range) for
        # FreeSpaceAllocator to allocate the relocated German text into.
        encoded_en = TextEncoder.encode(en_text, "pokemon")
        rom[offset: offset + len(encoded_en)] = encoded_en
        rom[referrer_offset: referrer_offset + 4] = struct.pack(
            "<I", ROM_POINTER_BASE + offset
        )
        return rom

    def test_apply_relocates_and_repoints(self):
        offset, referrer = 0x100, 0x50
        rom = self._build_rom(offset, "Hardy", referrer)
        stats = mod.apply(rom, targets={offset: "Robust"})
        self.assertEqual(stats["targets"], 1)
        self.assertEqual(stats["repointed"], 1)
        self.assertEqual(stats["failed"], 0)

        new_ptr = struct.unpack_from("<I", rom, referrer)[0]
        self.assertNotEqual(new_ptr, ROM_POINTER_BASE + offset, "referrer still points at EN cell")
        new_offset = new_ptr - ROM_POINTER_BASE
        decoded_end = rom.find(b"\xff", new_offset)
        self.assertEqual(bytes(rom[new_offset:decoded_end]), TextEncoder.encode("Robust", "pokemon")[:-1])

    def test_verify_reports_no_issues_after_apply(self):
        offset, referrer = 0x100, 0x50
        rom = self._build_rom(offset, "Hardy", referrer)
        targets = {offset: "Robust"}
        mod.apply(rom, targets=targets)

        bad = []
        needle = struct.pack("<I", ROM_POINTER_BASE + offset)
        import re
        for off, text in targets.items():
            if [m.start() for m in re.finditer(re.escape(needle), rom)]:
                bad.append((off, "still points to original"))
        self.assertEqual(bad, [])

    def test_skips_when_no_referrer_found(self):
        offset = 0x100
        rom = bytearray(b"\xff" * 0x10000)
        rom[offset: offset + 6] = TextEncoder.encode("Hardy", "pokemon")
        stats = mod.apply(rom, targets={offset: "Robust"})
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(stats["targets"], 0)


if __name__ == "__main__":
    unittest.main()
