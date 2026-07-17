"""Regression guard for languages/fr/patches/mission_tab_labels.py.

Issue #114: the Mission menu filter tabs rendered as run-on compounds
("ToutesMissions", "ActivesMissions", …) because the menu appends a shared
" Missions" suffix to each already-translated category name. The patch blanks
that suffix (following its live pointer at 0x1EBE988) so each tab shows only its
category word ("Toutes", "Actives", "Inactives", "Terminées").
"""

from __future__ import annotations

import struct
import unittest

from src.core.text_codec import POKEMON_TABLE
from languages.fr.patches.mission_tab_labels import (
    GBA_BASE,
    SUFFIX_PTR_OFFSET,
    apply_to_rom,
)

STR_OFFSET = 0x1F56040  # where the suffix lives in the real ROM layout


def _encode(text: str) -> bytes:
    return bytes(POKEMON_TABLE[c] for c in text) + b"\xff"


def _seed_rom(suffix: str = "Missions") -> bytearray:
    size = 0x200_0000
    rom = bytearray(b"\x00" * size)
    # live pointer at 0x1EBE988 → STR_OFFSET
    struct.pack_into("<I", rom, SUFFIX_PTR_OFFSET, GBA_BASE + STR_OFFSET)
    payload = _encode(suffix)
    rom[STR_OFFSET : STR_OFFSET + len(payload)] = payload
    # a sentinel string right after, must survive
    sentinel = _encode("A-Z")
    rom[STR_OFFSET + len(payload) : STR_OFFSET + len(payload) + len(sentinel)] = sentinel
    return rom


class TestPatchMissionTabLabelsFr(unittest.TestCase):
    def test_blanks_suffix_and_is_idempotent(self):
        rom = _seed_rom("Missions")
        n = apply_to_rom(rom)
        self.assertEqual(n, 1)
        # first byte of the suffix is now the terminator → empty string
        self.assertEqual(rom[STR_OFFSET], 0xFF)

        n2 = apply_to_rom(rom)
        self.assertEqual(n2, 0, "second run must be a no-op")

    def test_handles_en_variant_with_leading_space(self):
        rom = _seed_rom(" Missions")
        n = apply_to_rom(rom)
        self.assertEqual(n, 1)
        self.assertEqual(rom[STR_OFFSET], 0xFF)

    def test_does_not_clobber_next_string(self):
        rom = _seed_rom("Missions")
        apply_to_rom(rom)
        after = STR_OFFSET + len(_encode("Missions"))
        self.assertEqual(bytes(rom[after : after + 4]), _encode("A-Z")[:4])

    def test_skips_unexpected_value(self):
        rom = _seed_rom("Bounties")
        n = apply_to_rom(rom)
        self.assertEqual(n, 0, "must not touch an unexpected string")

    def test_dry_run_reports_but_does_not_write(self):
        rom = _seed_rom("Missions")
        n = apply_to_rom(rom, dry_run=True)
        self.assertEqual(n, 1)
        self.assertNotEqual(rom[STR_OFFSET], 0xFF, "dry-run must not mutate")


if __name__ == "__main__":
    unittest.main()
