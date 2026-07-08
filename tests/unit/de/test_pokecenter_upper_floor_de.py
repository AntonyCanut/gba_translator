"""Regression guard for the upper-floor Pokécenter Teala dialogue."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.core.text_codec import TextEncoder  # noqa: E402


class TestPokecenterUpperFloorDe(unittest.TestCase):
    def test_teala_intro_fits_the_fixed_slot(self):
        text = (
            "Hallo, {PLAYER}!\\p"
            "Ich bin Teala, die 2F-Assistentin im Pokémon-Center.\\p"
            "Fragen zum Link?"
        )
        encoded = TextEncoder.encode(text.replace('\\p', '<0xFB>'), 'pokemon')
        self.assertLessEqual(
            len(encoded),
            117,
            "0x1BDB85 must stay within the original Pokecenter slot",
        )

    def test_teala_intro_is_not_english(self):
        text = (
            "Hallo, {PLAYER}!\\p"
            "Ich bin Teala, die 2F-Assistentin im Pokémon-Center.\\p"
            "Fragen zum Link?"
        )
        self.assertNotIn("Hello", text)
        self.assertNotIn("Wireless", text)
        self.assertIn("Teala", text)


if __name__ == "__main__":
    unittest.main()
