"""Regression guard for the battle 'no effect' messages (ticket B-51 follow-up).

The following pointer slots in the battle string table must point to French text
after every ``make build-fr`` rebuild:

    0x3FDF78  "It had no effect on\n<name>"     → "Aucun effet sur\n<FD10>..."
    0x3FE4B0  "But it had no effect!"            → "Mais cela n'a aucun effet !"
    0x3FE4B4  "<name>'s <move>\nhad no effect..."→ "<FD13> : <FD1A>\ninnefficace ..."

The string at 0x3FDF78 regressed because its EN-ROM offset (0x800880) was absent
from combined_fr.txt — apply_combined_fr.py --extend silently dropped it.
"""

from __future__ import annotations

import struct
import unittest
from pathlib import Path

import pytest

pytestmark = pytest.mark.rom

from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")


def _follow_ptr(rom: bytes, ptr_slot: int, limit: int = 120) -> str:
    base = 0x08000000
    ptr = struct.unpack_from("<I", rom, ptr_slot)[0]
    offset = ptr - base
    if not (0 <= offset < len(rom)):
        return ""
    raw = rom[offset : offset + limit]
    end = raw.find(b"\xff")
    raw = raw[: end + 1] if end != -1 else raw
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


@pytest.fixture(scope="module")
def fr_rom() -> bytes:
    if not FR_ROM.exists():
        pytest.skip(f"FR ROM not found: {FR_ROM}")
    return FR_ROM.read_bytes()


@pytest.mark.rom
class TestBattleNoEffectFr(unittest.TestCase):
    """Verify that all 'no effect' battle strings are translated in the FR ROM."""

    @classmethod
    def setUpClass(cls) -> None:
        if not FR_ROM.exists():
            raise unittest.SkipTest(f"FR ROM not found: {FR_ROM}")
        cls.rom = FR_ROM.read_bytes()

    def _follow(self, slot: int) -> str:
        return _follow_ptr(self.rom, slot)

    def test_no_effect_on_name_main_slot(self) -> None:
        """0x3FDF78: 'It had no effect on <name>' must be in French."""
        text = self._follow(0x3FDF78)
        self.assertNotIn("It had no effect", text,
                         f"Slot 0x3FDF78 is still English: {text!r}")
        self.assertIn("Aucun effet", text,
                      f"Slot 0x3FDF78 missing French text: {text!r}")

    def test_but_no_effect_slot(self) -> None:
        """0x3FE4B0: 'But it had no effect!' must be in French."""
        text = self._follow(0x3FE4B0)
        self.assertNotIn("But it had no effect", text,
                         f"Slot 0x3FE4B0 is still English: {text!r}")
        self.assertIn("aucun effet", text.lower(),
                      f"Slot 0x3FE4B0 missing French text: {text!r}")

    def test_name_had_no_effect_on_slot(self) -> None:
        """0x3FE4B4: '<name>'s <move> had no effect on <name>' must be in French."""
        text = self._follow(0x3FE4B4)
        self.assertNotIn("had no effect on", text,
                         f"Slot 0x3FE4B4 is still English: {text!r}")

    def test_combined_fr_entry_uses_raw_bytes_not_brace_syntax(self) -> None:
        """0x800880 in combined_fr.txt must use <0xFD><0x10> (not {B_DEF_NAME_WITH_PREFIX})."""
        import re
        combined = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
        line_re = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
        entries: dict[int, str] = {}
        for line in combined.read_text(encoding="utf-8").splitlines():
            m = line_re.match(line)
            if m:
                entries[int(m.group(1), 16)] = m.group(2)
        self.assertIn(0x800880, entries,
                      "0x800880 not found in combined_fr.txt — entry missing")
        text = entries[0x800880]
        self.assertNotIn("{B_DEF_NAME_WITH_PREFIX}", text,
                         f"0x800880 uses placeholder syntax (will encode as garbage): {text!r}")
        self.assertIn("<0xFD><0x10>", text,
                      f"0x800880 missing raw token <0xFD><0x10>: {text!r}")
