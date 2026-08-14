"""Regression tests for the FR mon-icon graphics repair (issue #104).

The FR build rotates a handful of bytes inside several mon icons' frame-1 tile data
(the level-up banner reads frame 1), scrambling e.g. Rattata's banner icon while the
party-list icon — frame 0 — stays clean. Icons are never translated, so the fix
restores the live mon-icon graphics region from the source ROM.
"""

import sys
import unittest
from pathlib import Path

import pytest

pytestmark = pytest.mark.rom

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.mon_icon_repair import (
    ICON_REGION_END,
    ICON_REGION_START,
    region_bounds,
    restore_region,
)

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"
SOURCE_ROM = Path(__file__).parent.parent / "input" / "roms" / "englishrom.gba"

# The confirmed Rattata frame-1 corruption window (from the mGBA investigation).
RATTATA_FRAME1 = 0xE2C400  # duplicate icon copy; the live one is inside the region
CORRUPT_AT = 0x18A0F80     # live-icon (gMonIconTable) Rattata frame-1 corruption


class TestRestoreRegion(unittest.TestCase):
    def test_restores_only_differing_bytes(self):
        source = bytearray(64)
        source[10:16] = b"\x11\x22\x33\x44\x55\x66"  # "icon" data
        rom = bytearray(source)
        rom[12] = 0x00  # a corruption
        rom[13] = 0x00
        restored = restore_region(rom, bytes(source), 0, len(source))
        self.assertEqual(restored, 2)
        self.assertEqual(bytes(rom), bytes(source))

    def test_noop_when_clean(self):
        source = bytes(range(0, 256)) * 4
        rom = bytearray(source)
        self.assertEqual(restore_region(rom, source, 0, len(source)), 0)

    def test_only_touches_bounded_region(self):
        source = bytes([0xAB] * 100)
        rom = bytearray([0xCD] * 100)  # everything differs
        restored = restore_region(rom, source, 40, 60)
        self.assertEqual(restored, 20)
        # outside [40,60) is untouched
        self.assertEqual(rom[39], 0xCD)
        self.assertEqual(rom[60], 0xCD)
        self.assertTrue(all(rom[i] == 0xAB for i in range(40, 60)))


class TestRegionBounds(unittest.TestCase):
    def test_falls_back_to_constants_without_table(self):
        # A ROM whose icon table holds no valid pointers falls back to the constants.
        # (sized past gMonIconTable so the table read stays in bounds)
        rom = bytes(0x1A30000)
        lo, hi = region_bounds(rom)
        self.assertEqual((lo, hi), (ICON_REGION_START, ICON_REGION_END))


@pytest.mark.skipif(
    not (BUILT_FR_ROM.exists() and SOURCE_ROM.exists()),
    reason="built FR ROM and/or source ROM not present",
)
class TestBuiltRom(unittest.TestCase):
    def test_icon_region_matches_source(self):
        built = BUILT_FR_ROM.read_bytes()
        source = SOURCE_ROM.read_bytes()
        lo, hi = region_bounds(built)
        diffs = [i for i in range(lo, hi) if built[i] != source[i]]
        self.assertEqual(
            diffs, [],
            f"{len(diffs)} corrupted mon-icon byte(s) remain in the built ROM "
            f"(first at 0x{diffs[0]:07X})" if diffs else "",
        )

    def test_rattata_live_icon_clean(self):
        built = BUILT_FR_ROM.read_bytes()
        source = SOURCE_ROM.read_bytes()
        # the byte window that used to be rotated in the level-up banner icon
        self.assertEqual(
            built[CORRUPT_AT:CORRUPT_AT + 0x40],
            source[CORRUPT_AT:CORRUPT_AT + 0x40],
        )


if __name__ == "__main__":
    unittest.main()
