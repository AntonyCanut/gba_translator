"""Regression guard for the Mega Evolution reaction messages (ticket P-70 split).

When a trainer (e.g. Vega) Mega Evolves, the battle engine shows:

    "<mon>'s <stone> is reacting\nto <trainer>'s <Mega Cuff>!"

Two distinct templates back this message and both must be French in the FR ROM
after every ``make build-fr`` rebuild:

    0x83008C  buffers 0/1/2/3  → "Le <FD01> de <FD00> réagit\nau <FD03> de <FD02>!"
    0x96CC1C  buffers 0/16/39/1 → "Le <FD16> de <FD00> réagit\nau <FD01> de <FD39>!"

Both were shipping in English:
  * 0x83008C had a French entry in combined_fr.txt but it was 34 bytes for a
    31-byte slot (``too_long``) → dropped at injection (engine region, no repoint).
  * 0x96CC1C was absent from combined_fr.txt entirely → never translated.

The fix trims both to exactly 31 bytes (``à la ``→``au ``, drop the thin space
before ``!``) so they inject in-place. These strings live at fixed offsets in the
battle-string region (read directly, not via a pointer slot).
"""

from __future__ import annotations

import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")

# Fixed offsets of the two Mega-Cuff reaction templates in the battle-string region.
# Each is read directly (not via a pointer slot) and must decode to French.
MEGA_REACTION_OFFSETS = (0x83008C, 0x96CC1C)


def _decode_at(rom: bytes, offset: int, limit: int = 60) -> str:
    raw = rom[offset : offset + limit]
    end = raw.find(b"\xff")
    raw = raw[: end + 1] if end != -1 else raw
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


@pytest.fixture(scope="module")
def fr_rom() -> bytes:
    if not FR_ROM.exists():
        pytest.skip(f"FR ROM not found: {FR_ROM}")
    return FR_ROM.read_bytes()


class TestBattleMegaReactionFr(unittest.TestCase):
    """Verify both Mega-Cuff reaction templates are translated in the FR ROM."""

    @classmethod
    def setUpClass(cls) -> None:
        if not FR_ROM.exists():
            raise unittest.SkipTest(f"FR ROM not found: {FR_ROM}")
        cls.rom = FR_ROM.read_bytes()

    def test_reaction_templates_are_french(self) -> None:
        for offset in MEGA_REACTION_OFFSETS:
            with self.subTest(offset=hex(offset)):
                text = _decode_at(self.rom, offset)
                self.assertIn(
                    "réagit",
                    text,
                    f"{hex(offset)} still English (no 'réagit'): {text!r}",
                )
                self.assertNotIn(
                    "reacting",
                    text,
                    f"{hex(offset)} still English ('reacting' present): {text!r}",
                )
                # All four runtime buffer codes (FD xx) must survive the rewrite.
                self.assertEqual(
                    self.rom[offset : self.rom.find(b"\xff", offset, offset + 64)].count(0xFD),
                    4,
                    f"{hex(offset)}: expected 4 FD buffer codes: {text!r}",
                )

    def test_reaction_templates_fit_slot(self) -> None:
        """Each FR string must terminate within the 31-byte EN slot (in-place)."""
        for offset in MEGA_REACTION_OFFSETS:
            with self.subTest(offset=hex(offset)):
                # 0xFF terminator must be at offset+31 (slot length) at the latest.
                term = self.rom.find(b"\xff", offset, offset + 64)
                self.assertNotEqual(term, -1, f"{hex(offset)}: no terminator found")
                self.assertLessEqual(
                    term - offset,
                    31,
                    f"{hex(offset)}: FR string overflows 31-byte slot (len {term - offset})",
                )


if __name__ == "__main__":
    unittest.main()
