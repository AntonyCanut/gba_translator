"""
Regression guard: all 25 Pokémon nature names must resolve to their official
French names through the LIVE pointer tables in every ``make build-fr`` rebuild.

Why this test exists (the "Lax" false-positive trap)
----------------------------------------------------
The 25 nature names ("Hardy", "Lonely", "Lax"…) are packed back-to-back as
``0xFF``-terminated strings at ``0x463DBC``-``0x463E5D``. They are read only
through two 25-entry pointer tables:
  - ``gNatureNamePointers`` at 0x463E60 (vanilla FireRed table)
  - a CFRU duplicate at 0x1FE65F4 (upper expanded ROM)

The in-game "Il a la nature {X}." message buffers the nature name from one of
those tables — never from the packed cell directly.

Any French name longer than its English original (Assuré>Bold, Lâche>Lax,
Timide>Timid, Pressé>Hasty, Jovial>Jolly, Modeste>Modest, Discret>Quiet,
Foufou>Rash, Calme>Calm, Malpoli>Sassy) cannot fit in place, so the build
pipeline **relocates** it into free space and repoints *both* tables. The
original packed cell is left untouched — it still decodes to the English word
("Lax"), but nothing references it any more.

Decoding the original offset therefore gives a false "still English" reading
(reported in the F-66 ticket for "Lax"). The truth is what the live pointer
resolves to. This guard asserts the live pointers, so a real regression (a
nature that drops back to English because its combined_fr.txt entry was erased
or the relocation was lost) is caught immediately, while the harmless dead
English cell never trips a false alarm.

Run standalone:   pytest tests/test_nature_names_fr.py -v
"""

import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")

POINTER_BASE = 0x08000000

# The two 25-entry nature-name pointer tables. Every nature-name display in the
# game reads from one of these; there is no third table (verified statically:
# the first string 0x463DBC has exactly these two referrers).
NATURE_NAME_TABLES = (0x463E60, 0x1FE65F4)

# Nature index (0=Hardy .. 24=Quirky) -> (english_original, official_french).
# The French column is the single source of truth this guard enforces.
NATURES = [
    ("Hardy", "Hardi"),
    ("Lonely", "Solo"),
    ("Brave", "Brave"),
    ("Adamant", "Rigide"),
    ("Naughty", "Mauvais"),
    ("Bold", "Assuré"),
    ("Docile", "Docile"),      # identical spelling EN/FR — still correct FR
    ("Relaxed", "Relax"),
    ("Impish", "Malin"),
    ("Lax", "Lâche"),          # F-66 headline: must NOT be "Lax"
    ("Timid", "Timide"),
    ("Hasty", "Pressé"),
    ("Serious", "Sérieux"),
    ("Jolly", "Jovial"),
    ("Naive", "Naïf"),
    ("Modest", "Modeste"),
    ("Mild", "Doux"),
    ("Quiet", "Discret"),
    ("Bashful", "Pudique"),
    ("Rash", "Foufou"),
    ("Calm", "Calme"),
    ("Gentle", "Gentil"),
    ("Sassy", "Malpoli"),
    ("Careful", "Prudent"),
    ("Quirky", "Bizarre"),
]


def _read_at(rom: bytes, offset: int, limit: int = 64) -> str:
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xff")
    raw = chunk if end == -1 else chunk[:end]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def _follow_slot(rom: bytes, table_base: int, index: int) -> str:
    """Decode the string reached by table_base[index] (a live GBA pointer)."""
    ptr_off = table_base + index * 4
    ptr = struct.unpack_from("<I", rom, ptr_off)[0]
    if ptr < POINTER_BASE or ptr >= POINTER_BASE + len(rom):
        return ""
    return _read_at(rom, ptr - POINTER_BASE)


@pytest.mark.skipif(not FR_ROM.exists(), reason="FR ROM not built")
class TestNatureNamesFr(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = FR_ROM.read_bytes()

    def test_both_tables_resolve_to_official_french(self):
        """Every nature in BOTH pointer tables resolves to its official FR name."""
        for table in NATURE_NAME_TABLES:
            for index, (en, fr) in enumerate(NATURES):
                got = _follow_slot(self.rom, table, index)
                self.assertEqual(
                    got,
                    fr,
                    f"nature #{index} ({en}) via table 0x{table:X} "
                    f"should be {fr!r}, got {got!r}",
                )

    def test_lax_is_lache(self):
        """F-66 headline: nature index 9 (Lax) must display 'Lâche', not 'Lax'."""
        for table in NATURE_NAME_TABLES:
            self.assertEqual(_follow_slot(self.rom, table, 9), "Lâche")

    def test_no_nature_stays_english(self):
        """No live nature slot may resolve to its English original word."""
        english = {en for en, fr in NATURES if en != fr}
        for table in NATURE_NAME_TABLES:
            for index, (en, fr) in enumerate(NATURES):
                got = _follow_slot(self.rom, table, index)
                self.assertNotIn(
                    got,
                    english,
                    f"nature #{index} via 0x{table:X} still English: {got!r}",
                )


if __name__ == "__main__":
    unittest.main()
