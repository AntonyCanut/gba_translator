"""Regression guard for languages/fr/patches/mission_tab_labels.py.

Issue #114: the Mission menu filter tabs rendered as run-on compounds
("ToutesMissions", "ActivesMissions", …) because the menu appends a shared
" Missions" suffix to each already-translated category name. The patch blanks
that suffix (following its live pointer at 0x1EBE988) so each tab shows only its
category word ("Toutes", "Actives", "Inactives", "Terminées").

Issue #46 follow-up: the stock ``Active`` string has two consumers. The filter
tab must render the plural ``Actives``, but the blue status attached to one
mission row must render the singular ``Active``. The patch separates those
pointers after the generic translation pass had repointed both to ``Actives``.
"""

from __future__ import annotations

import struct
import unittest

from languages.fr.patches.mission_tab_labels import (
    GBA_BASE,
    SUFFIX_PTR_OFFSET,
    apply_to_rom,
)
from src.core.text_codec import POKEMON_TABLE

STR_OFFSET = 0x1F56040  # where the suffix lives in the real ROM layout
ACTIVE_INLINE_OFFSET = 0x1F5605C
ACTIVE_RELOCATED_OFFSET = 0x1F57000
ACTIVE_TAB_POINTER = 0x1EBFFC8
ACTIVE_STATUS_POINTER = 0x1FB40B8


def _encode(text: str) -> bytes:
    return bytes(POKEMON_TABLE[c] for c in text) + b"\xff"


def _seed_rom(suffix: str = "Missions", *, shared_active: bool = False) -> bytearray:
    size = 0x200_0000
    rom = bytearray(b"\x00" * size)
    # live pointer at 0x1EBE988 → STR_OFFSET
    struct.pack_into("<I", rom, SUFFIX_PTR_OFFSET, GBA_BASE + STR_OFFSET)
    payload = _encode(suffix)
    rom[STR_OFFSET : STR_OFFSET + len(payload)] = payload
    # a sentinel string right after, must survive
    sentinel = _encode("A-Z")
    rom[STR_OFFSET + len(payload) : STR_OFFSET + len(payload) + len(sentinel)] = sentinel

    # Le build générique relocalise « Actives ». Le test de régression peut
    # reproduire son repointage erroné des deux usages vers cette même cible.
    rom[ACTIVE_INLINE_OFFSET : ACTIVE_INLINE_OFFSET + len(_encode("Active"))] = _encode(
        "Active"
    )
    rom[
        ACTIVE_RELOCATED_OFFSET : ACTIVE_RELOCATED_OFFSET + len(_encode("Actives"))
    ] = _encode("Actives")
    struct.pack_into("<I", rom, ACTIVE_TAB_POINTER, GBA_BASE + ACTIVE_RELOCATED_OFFSET)
    status_target = ACTIVE_RELOCATED_OFFSET if shared_active else ACTIVE_INLINE_OFFSET
    struct.pack_into("<I", rom, ACTIVE_STATUS_POINTER, GBA_BASE + status_target)
    return rom


def _decode_pointer(rom: bytearray, pointer_site: int) -> str:
    (target,) = struct.unpack_from("<I", rom, pointer_site)
    offset = target - GBA_BASE
    end = rom.index(0xFF, offset)
    reverse = {value: key for key, value in POKEMON_TABLE.items()}
    return "".join(reverse[value] for value in rom[offset:end])


class TestPatchMissionTabLabelsFr(unittest.TestCase):
    def test_keeps_plural_tab_but_restores_singular_mission_status(self):
        rom = _seed_rom("Missions", shared_active=True)

        changes = apply_to_rom(rom)

        self.assertEqual(changes, 1)
        self.assertEqual(_decode_pointer(rom, ACTIVE_TAB_POINTER), "Actives")
        self.assertEqual(_decode_pointer(rom, ACTIVE_STATUS_POINTER), "Active")
        self.assertNotEqual(
            struct.unpack_from("<I", rom, ACTIVE_TAB_POINTER)[0],
            struct.unpack_from("<I", rom, ACTIVE_STATUS_POINTER)[0],
        )
        self.assertEqual(apply_to_rom(rom), 0, "second run must be a no-op")

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
