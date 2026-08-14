"""Regression guard for languages/de/patches/battle_string_templates.py.

Same language-neutral control-code cluster restore as the FR script — only
the module under test differs.
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.de.patches.battle_string_templates import (
    CLUSTER_END,
    CLUSTER_START,
    STRINGID0_BODY_OFF,
    STRINGID0_PTR_OFF,
    apply_to_rom,
)

GBA_BASE = 0x08000000


def _make_en(size: int = 0x3FE000) -> bytearray:
    en = bytearray(b"\xff" * size)
    struct.pack_into("<I", en, STRINGID0_PTR_OFF, GBA_BASE + STRINGID0_BODY_OFF)
    # Canonical {FD24}-led template followed by filler up to CLUSTER_END.
    cluster = bytearray(b"\x11" * (CLUSTER_END - CLUSTER_START))
    cluster[0:3] = bytes.fromhex("fd24ff")
    en[CLUSTER_START:CLUSTER_END] = cluster
    return en


def _make_corrupted(en: bytes) -> bytearray:
    rom = bytearray(en)
    # Simulate the FR/DE pipeline overflow corrupting the cluster.
    rom[CLUSTER_START:CLUSTER_END] = bytes([0x00]) * (CLUSTER_END - CLUSTER_START)
    struct.pack_into("<I", rom, STRINGID0_PTR_OFF, GBA_BASE + STRINGID0_BODY_OFF)
    return rom


class TestBattleStringTemplatesDe(unittest.TestCase):
    def test_restores_cluster_from_english(self):
        en = _make_en()
        rom = _make_corrupted(en)
        n = apply_to_rom(rom, bytes(en))
        self.assertEqual(n, 1)
        self.assertEqual(rom[CLUSTER_START:CLUSTER_END], en[CLUSTER_START:CLUSTER_END])

    def test_idempotent(self):
        en = _make_en()
        rom = _make_corrupted(en)
        apply_to_rom(rom, bytes(en))
        self.assertEqual(apply_to_rom(rom, bytes(en)), 0)

    def test_refuses_unexpected_source_rom(self):
        en = _make_en()
        en[CLUSTER_START:CLUSTER_START + 3] = bytes.fromhex("aabbcc")
        rom = _make_corrupted(_make_en())  # normal EN reference for the ROM itself
        n = apply_to_rom(rom, bytes(en))
        self.assertEqual(n, 0)

    def test_restores_fixed_pointer_after_generic_relocation(self):
        en = _make_en()
        rom = _make_corrupted(en)
        struct.pack_into("<I", rom, STRINGID0_PTR_OFF, GBA_BASE + 0x1000)

        self.assertEqual(apply_to_rom(rom, bytes(en)), 1)
        self.assertEqual(
            struct.unpack_from("<I", rom, STRINGID0_PTR_OFF)[0],
            GBA_BASE + STRINGID0_BODY_OFF,
        )
        self.assertEqual(rom[CLUSTER_START:CLUSTER_END], en[CLUSTER_START:CLUSTER_END])


if __name__ == "__main__":
    unittest.main()
