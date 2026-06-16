"""
Regression guard: location names visible on the World Map and in NPC dialogue
must survive every ``make build-fr`` rebuild.

Why translations disappear
--------------------------
The build pipeline rewrites the JSON translation from scratch on every run.
An entry that is in ``combined_fr.txt`` but is silently dropped (e.g. because
``apply_combined_fr.py --extend`` was skipped, the inline-overrides pass failed,
or the text was too long with no free pointer) will be absent from the next ROM
with no error message.  These tests catch that regression immediately after
``make build-fr``.

Run standalone:   pytest tests/test_location_names_fr.py -v
Run via Makefile: make test-rom
"""

import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")

# Pre-encoded byte sequences (CFRU charmap, no terminator)
_THUNDERCAP_BYTES = bytes.fromhex("cedce9e2d8d9e6d7d5e4")  # "Thundercap"
_MONT_FOUDRE_BYTES = bytes.fromhex("c7e3e2e800c0e3e9d8e6d9")  # "Mont Foudre"


def _read_at(rom: bytes, offset: int, limit: int = 200) -> str:
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xff")
    raw = chunk if end == -1 else chunk[: end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def _follow_ptr(rom: bytes, ptr_offset: int, limit: int = 400) -> str:
    """Return decoded text at the GBA pointer stored at ptr_offset."""
    base = 0x08000000
    if ptr_offset + 4 > len(rom):
        return ""
    ptr = struct.unpack_from("<I", rom, ptr_offset)[0]
    if ptr < base or ptr >= base + len(rom):
        return ""
    return _read_at(rom, ptr - base, limit)


@pytest.mark.rom
class TestLocationNamesFR(unittest.TestCase):
    """Location name translations must survive each make build-fr rebuild."""

    @classmethod
    def setUpClass(cls):
        if not FR_ROM.exists():
            raise unittest.SkipTest(f"FR ROM not found: {FR_ROM}")
        cls.rom = FR_ROM.read_bytes()

    # ── Mont Foudre (Thundercap Mt.) ─────────────────────────────────────────

    def test_thundercap_worldmap_label_is_translated(self):
        """World Map label at 0xB5026C must read 'Mont Foudre', not 'Thundercap Mt.'."""
        text = _read_at(self.rom, 0xB5026C)
        self.assertIn(
            "Mont Foudre",
            text,
            f"Expected 'Mont Foudre' at 0xB5026C, got: {repr(text[:40])}",
        )
        self.assertNotIn(
            "Thundercap",
            text,
            f"'Thundercap' survives in World Map label at 0xB5026C: {repr(text[:40])}",
        )

    def test_thundercap_npc_dialogue_pointer_is_french(self):
        """Pointer at 0x7C252E must lead to French NPC dialogue (contains 'Foudre').

        The pipeline relocates the translated string to free space and repoints
        0x7C252E.  The original English bytes at 0x7C2540 remain but are
        unreachable — this test follows the live pointer so a silent revert is
        caught even if the original address still looks untouched.
        """
        text = _follow_ptr(self.rom, 0x7C252E)
        self.assertTrue(text, "Pointer at 0x7C252E is invalid or points outside ROM")
        self.assertIn(
            "Foudre",
            text,
            f"Expected 'Foudre' via ptr@0x7C252E, got: {repr(text[:60])}",
        )
        self.assertNotIn(
            "Thundercap",
            text,
            f"'Thundercap' still in NPC dialogue via ptr@0x7C252E: {repr(text[:60])}",
        )

    def test_no_active_pointer_to_thundercap(self):
        """No GBA pointer in the ROM should point to a 'Thundercap' string.

        31 occurrences of the raw bytes are expected (original inline text
        left in place after pointer relocation) but none should be pointed to
        by an active ROM pointer.
        """
        base = 0x08000000
        rom = self.rom
        live: list = []
        pos = 0
        while True:
            p = rom.find(_THUNDERCAP_BYTES, pos)
            if p == -1:
                break
            ptr_val = struct.pack("<I", p + base)
            count = rom.count(ptr_val)
            if count > 0:
                end = rom.find(b"\xff", p)
                txt = TextDecoder.decode_pokemon(rom[p : end + 1])
                live.append((hex(p), count, txt[:60]))
            pos = p + 1
        self.assertEqual(
            live,
            [],
            f"Found {len(live)} live pointer(s) to 'Thundercap' string(s): {live}",
        )


if __name__ == "__main__":
    unittest.main()
