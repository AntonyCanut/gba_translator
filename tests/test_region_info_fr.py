"""
Regression guard: the Fallshore Pokénav region-info blurb must stay French.

Why this test exists
--------------------
``combined_fr.txt`` carried the entry::

    0x74B2DF: Fallshore\\pLa capitale des cascades de Borrius.

Commit c7c1ede ("correct 'And' to 'Et' in move-learning dialogue") regenerated
combined_fr.txt and *collaterally deleted 36 region/label entries*. The team
later restored the 14 World Map labels (commit 108c0d7, guarded by
``test_location_names_fr.py``) but missed this region-info description, so the
live pointer at 0x74B2D7 kept rendering the English source
"Fallshore City\\pThe waterfall capital of Borrius." in-game.

The French (48 bytes incl. terminator) fits inside the English slot (49 bytes),
so it is written in place at 0x74B2DF with no relocation.

Run standalone:   pytest tests/test_region_info_fr.py -v
Run via Makefile: make test-rom
"""

import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder, TextEncoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")

FALLSHORE_INFO_OFFSET = 0x74B2DF
FALLSHORE_INFO_POINTER = 0x74B2D7  # GBA pointer (0x0874B2DF) that reaches the blurb
EXPECTED_FR = "Fallshore<0xFB>La capitale des cascades de Borrius."
_ENGLISH_BYTES = TextEncoder.encode_pokemon("The waterfall capital of Borrius")


def _read_at(rom: bytes, offset: int, limit: int = 200) -> str:
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xff")
    raw = chunk if end == -1 else chunk[: end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


@pytest.mark.rom
class TestRegionInfoFR(unittest.TestCase):
    """Fallshore region-info blurb must survive every build in French."""

    @classmethod
    def setUpClass(cls):
        if not FR_ROM.exists():
            raise unittest.SkipTest(f"FR ROM not found: {FR_ROM}")
        cls.rom = FR_ROM.read_bytes()

    def test_fallshore_region_info_is_french(self):
        """0x74B2DF renders the French region blurb, not the English source."""
        text = _read_at(self.rom, FALLSHORE_INFO_OFFSET).strip()
        self.assertEqual(
            text,
            EXPECTED_FR,
            f"Region info at 0x{FALLSHORE_INFO_OFFSET:08X}: expected "
            f"{EXPECTED_FR!r}, got {text!r} (English regression from c7c1ede?)",
        )

    def test_pointer_still_reaches_french_blurb(self):
        """The live pointer at 0x74B2D7 must resolve to the French text."""
        ptr = struct.unpack_from("<I", self.rom, FALLSHORE_INFO_POINTER)[0]
        self.assertEqual(
            ptr,
            0x08000000 + FALLSHORE_INFO_OFFSET,
            f"Pointer at 0x{FALLSHORE_INFO_POINTER:08X} no longer targets the blurb",
        )
        text = _read_at(self.rom, ptr - 0x08000000).strip()
        self.assertIn("cascades de Borrius", text)
        self.assertNotIn("waterfall", text)

    def test_no_english_waterfall_residue(self):
        """The English 'waterfall capital' bytes must not linger in the ROM."""
        self.assertEqual(
            self.rom.find(_ENGLISH_BYTES),
            -1,
            "English 'The waterfall capital of Borrius' bytes still present",
        )


if __name__ == "__main__":
    unittest.main()
