"""Regression guard for the move-forget animation text (GitHub issue #14).

When a Pokemon forgets a move to learn a new one, the game shows the classic
"1, 2, and... Poof!" sequence. The official French games render this as
"1, 2, et... TADAA!" (not a literal "Pouf !" translation).

combined_fr.txt carries five copies of this template at fixed offsets
(0x3FCC07, 0x41B2FF, 0x416EC6, 0x41E493, 0x8AA942). Two of them ("Poof!<0xFB>"
alone and the longer "...forgot how to use..." variant) are one byte longer
in French ("TADAA!" vs "Poof!") and get relocated by the generic builder
(--allow-relocate); the other three fit in place. Each must be checked via
its LIVE pointer target, not the original EN offset, since a relocated
entry leaves stale English bytes behind at the old location.
"""

from __future__ import annotations

import struct
import unittest
from pathlib import Path

import pytest

pytestmark = pytest.mark.rom

from src.core.text_codec import TextDecoder

EN_ROM = Path("input/roms/englishrom.gba")
FR_ROM = Path("output/roms/GenedRom-fr.gba")
BASE = 0x08000000

# Offsets fit in-place in French (same byte length as English).
INPLACE_OFFSETS = (0x3FCC07, 0x41E493, 0x8AA942)

# Offsets one byte too long in French ("TADAA!" vs "Poof!") -> relocated.
RELOCATED_OFFSETS = (0x41B2FF, 0x416EC6)


def _decode_at(rom: bytes, offset: int, limit: int = 300) -> str:
    raw = rom[offset : offset + limit]
    end = raw.find(b"\xff")
    raw = raw[: end + 1] if end != -1 else raw
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def _live_offset(en_rom: bytes, fr_rom: bytes, en_offset: int) -> int:
    """Follow the pointer to en_offset from EN ROM into its FR ROM target."""
    needle = struct.pack("<I", BASE + en_offset)
    ptr_loc = en_rom.find(needle)
    assert ptr_loc != -1, f"no pointer found for {hex(en_offset)} in EN ROM"
    fr_value = struct.unpack_from("<I", fr_rom, ptr_loc)[0]
    return fr_value - BASE


@pytest.mark.rom
class TestMoveForgetTadaaFr(unittest.TestCase):
    """Every copy of the move-forget template must say TADAA, not Pouf/Poof."""

    @classmethod
    def setUpClass(cls) -> None:
        if not FR_ROM.exists() or not EN_ROM.exists():
            raise unittest.SkipTest("FR/EN ROM not found")
        cls.fr_rom = FR_ROM.read_bytes()
        cls.en_rom = EN_ROM.read_bytes()

    def test_inplace_offsets_say_tadaa(self) -> None:
        for offset in INPLACE_OFFSETS:
            with self.subTest(offset=hex(offset)):
                text = _decode_at(self.fr_rom, offset)
                self.assertIn("TADAA", text, f"{hex(offset)}: {text!r}")
                self.assertNotIn("Pouf", text, f"{hex(offset)}: {text!r}")
                self.assertNotIn("Poof", text, f"{hex(offset)}: {text!r}")

    def test_relocated_offsets_say_tadaa(self) -> None:
        for offset in RELOCATED_OFFSETS:
            with self.subTest(offset=hex(offset)):
                live = _live_offset(self.en_rom, self.fr_rom, offset)
                text = _decode_at(self.fr_rom, live)
                self.assertIn("TADAA", text, f"{hex(offset)} -> {hex(live)}: {text!r}")
                self.assertNotIn("Poof", text, f"{hex(offset)} -> {hex(live)}: {text!r}")


if __name__ == "__main__":
    unittest.main()
