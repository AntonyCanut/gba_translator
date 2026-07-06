"""Regression guard for the wild Pokémon capture message (GitHub issue #12).

The English battle engine shows "Gotcha!\n<mon> was caught!" when a wild
Pokémon is caught. The official French games translate "Gotcha!" as
"Et hop !" (with the French typographic space before the exclamation mark),
not "Attrapé!".

Three strings back this message, all reached through live pointer slots
(the pipeline relocates the FR text, so the original offsets are stale):

    slot 0x3FE338 → EN 0x3FD7A2  "Gotcha!\n{FD3A} was caught!…\\l"   variant
    slot 0x3FE33C → EN 0x3FD7C0  "Gotcha!\n{FD3A} was caught!…{FC08}" variant
    slot 0x1E73ABE → EN 0x1F19A1B "Gotcha!" (standalone CFRU string)

Each test follows the pointer the engine actually reads and decodes the
bytes at its target — the original offsets still hold the EN text and must
not be used for verification.
"""

from __future__ import annotations

import struct
import unittest
from pathlib import Path

from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")

GBA_BASE = 0x08000000

# Live pointer slots for the three capture strings (stable code-region slots).
CAPTURE_POINTER_SLOTS = (0x3FE338, 0x3FE33C, 0x1E73ABE)


def _decode_via_slot(rom: bytes, slot: int, limit: int = 80) -> str:
    target = struct.unpack_from("<I", rom, slot)[0] - GBA_BASE
    raw = rom[target : target + limit]
    end = raw.find(b"\xff")
    raw = raw[: end + 1] if end != -1 else raw
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


class TestCaptureGotchaFr(unittest.TestCase):
    """The capture message must read "Et hop !" in the built FR ROM."""

    @classmethod
    def setUpClass(cls) -> None:
        if not FR_ROM.exists():
            raise unittest.SkipTest(f"FR ROM not found: {FR_ROM}")
        cls.rom = FR_ROM.read_bytes()

    def test_capture_strings_say_et_hop(self) -> None:
        for slot in CAPTURE_POINTER_SLOTS:
            with self.subTest(slot=hex(slot)):
                text = _decode_via_slot(self.rom, slot)
                self.assertIn(
                    "Et hop !",
                    text,
                    f"slot {hex(slot)}: expected 'Et hop !': {text!r}",
                )
                self.assertNotIn(
                    "Gotcha",
                    text,
                    f"slot {hex(slot)}: still English: {text!r}",
                )
                self.assertNotIn(
                    "Attrapé",
                    text,
                    f"slot {hex(slot)}: old FR wording remains: {text!r}",
                )

    def test_battle_variants_keep_buffer_and_space_before_bang(self) -> None:
        """Both battle variants keep the {FD3A} name buffer and French spacing."""
        for slot in (0x3FE338, 0x3FE33C):
            with self.subTest(slot=hex(slot)):
                text = _decode_via_slot(self.rom, slot)
                self.assertIn(
                    "capturé !",
                    text,
                    f"slot {hex(slot)}: missing space before '!': {text!r}",
                )
                target = struct.unpack_from("<I", self.rom, slot)[0] - GBA_BASE
                raw = self.rom[target : self.rom.find(b"\xff", target, target + 80)]
                self.assertEqual(
                    raw.count(0xFD),
                    1,
                    f"slot {hex(slot)}: expected 1 FD buffer code: {text!r}",
                )


if __name__ == "__main__":
    unittest.main()
