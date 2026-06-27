"""Regression guard for battle 'super effective' messages (ticket B-54).

The following pointer slots in the battle string table must point to French text
after every ``make build-fr`` rebuild:

    0x9EB8F4  "It's super effective on\n<name>!"  -> "C'est super efficace sur\n<FD10> !"
    0x3FE284  "It's super effective!"              -> "C'est super efficace !"

Root cause of the original regression: combined_fr.txt had the entry keyed to
0xA4A8DD (3 bytes too early). The engine reads the string at 0xA4A8E0 — the only
offset in the EN extraction — so apply_combined_fr.py --extend could never add it.

Subsequent regression (B-54 follow-up): commit 33535eb overwrote the living block
of combined_fr.txt and silently dropped the 0xa4a8e0 entry added by 6512547.
Fix: data/critical_strings_fr.txt now pins the entry permanently.
"""

from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")
COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
CRITICAL_STRINGS = Path(__file__).resolve().parent.parent / "data" / "critical_strings_fr.txt"


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


def _parse_combined(path: Path) -> dict[int, str]:
    line_re = re.compile(r"^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$")
    entries: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = line_re.match(line)
        if m:
            entries[int(m.group(1), 16)] = m.group(2)
    return entries


class TestBattleSuperEffectiveFr(unittest.TestCase):
    """Verify that all 'super effective' battle strings are translated in the FR ROM."""

    @classmethod
    def setUpClass(cls) -> None:
        if not FR_ROM.exists():
            raise unittest.SkipTest(f"FR ROM not found: {FR_ROM}")
        cls.rom = FR_ROM.read_bytes()

    def _follow(self, slot: int) -> str:
        return _follow_ptr(self.rom, slot)

    def test_super_effective_on_name_slot(self) -> None:
        """0x9EB8F4: 'It's super effective on <name>' must be in French."""
        text = self._follow(0x9EB8F4)
        self.assertNotIn("super effective", text.lower(),
                         f"Slot 0x9EB8F4 is still English: {text!r}")
        self.assertIn("efficace", text.lower(),
                      f"Slot 0x9EB8F4 missing French text: {text!r}")

    def test_super_effective_short_slot(self) -> None:
        """0x3FE284: 'It's super effective!' must be in French."""
        text = self._follow(0x3FE284)
        self.assertNotIn("super effective", text.lower(),
                         f"Slot 0x3FE284 is still English: {text!r}")
        self.assertIn("efficace", text.lower(),
                      f"Slot 0x3FE284 missing French text: {text!r}")


class TestCriticalStringsGuard(unittest.TestCase):
    """Verify that data/critical_strings_fr.txt entries are present in combined_fr.txt.

    This test catches the regression where a future agent edits the living block
    of combined_fr.txt and accidentally drops a critical entry.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.combined = _parse_combined(COMBINED_FR)
        cls.critical: dict[int, str] = {}
        line_re = re.compile(r"^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$")
        for line in CRITICAL_STRINGS.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = line_re.match(line)
            if m:
                cls.critical[int(m.group(1), 16)] = m.group(2)

    def test_critical_strings_file_exists(self) -> None:
        self.assertTrue(CRITICAL_STRINGS.exists(),
                        f"Critical strings guard file missing: {CRITICAL_STRINGS}")

    def test_critical_strings_file_non_empty(self) -> None:
        self.assertGreater(len(self.critical), 0,
                           "data/critical_strings_fr.txt has no entries")

    def test_super_effective_on_name_in_combined(self) -> None:
        """0xa4a8e0 must be present in combined_fr.txt with raw-byte token."""
        entries = self.combined
        self.assertIn(0xa4a8e0, entries,
                      "0xa4a8e0 not found in combined_fr.txt — entry was lost")
        text = entries[0xa4a8e0]
        self.assertNotIn("{B_DEF_NAME_WITH_PREFIX}", text,
                         f"0xa4a8e0 uses placeholder syntax: {text!r}")
        self.assertIn("<0xFD><0x10>", text,
                      f"0xa4a8e0 missing raw token <0xFD><0x10>: {text!r}")

    def test_no_effect_on_name_in_combined(self) -> None:
        """0x800880 must be present in combined_fr.txt with raw-byte token."""
        entries = self.combined
        self.assertIn(0x800880, entries,
                      "0x800880 not found in combined_fr.txt — entry was lost")
        text = entries[0x800880]
        self.assertNotIn("{B_DEF_NAME_WITH_PREFIX}", text,
                         f"0x800880 uses placeholder syntax: {text!r}")
        self.assertIn("<0xFD><0x10>", text,
                      f"0x800880 missing raw token <0xFD><0x10>: {text!r}")

    def test_all_critical_entries_in_combined(self) -> None:
        """Every entry in data/critical_strings_fr.txt must be in combined_fr.txt."""
        missing = [hex(o) for o in self.critical if o not in self.combined]
        self.assertEqual(missing, [],
                         f"Critical offsets missing from combined_fr.txt: {missing}")
