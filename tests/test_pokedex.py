import json
import unittest
from pathlib import Path

from src.core import pokedex
from src.core.pokedex import (
    DEX_LINE_WIDTH,
    DEX_MAX_LINES,
    fits,
    is_description,
    line_width,
    rewrap,
    wrap_lines,
)
from src.core.text_codec import TextEncoder

OVERRIDES = (
    Path(__file__).resolve().parent.parent
    / "languages" / "fr" / "data" / "pokedex_fr_overrides.json"
)


class WrapTests(unittest.TestCase):
    def test_short_text_stays_one_line(self):
        self.assertEqual(wrap_lines("Un petit Pokémon."), ["Un petit Pokémon."])

    def test_four_line_french_is_rewrapped_to_three(self):
        text = (
            "Il évite agilement les attaques\nennemies et crache des boules de\n"
            "feu par le groin. Il aime\ngriller des Baies."
        )
        wrapped = rewrap(text)
        self.assertLessEqual(wrapped.count("\n") + 1, DEX_MAX_LINES)
        # wording preserved, only breaks moved
        self.assertEqual(wrapped.replace("\n", " "), text.replace("\n", " "))

    def test_every_line_within_window(self):
        text = (
            "Quand il fait vibrer la bosse sur sa tête, il provoque "
            "des ondulations dans l'eau."
        )
        for line in rewrap(text).split("\n"):
            self.assertLessEqual(line_width(line), DEX_LINE_WIDTH)

    def test_fits_rejects_overlong_text(self):
        too_long = (
            "Lorsqu'il rassemble ses forces, les piquants souples qui "
            "recouvrent sa tête deviennent si durs et acérés qu'ils "
            "pourraient transpercer un rocher massif."
        )
        self.assertFalse(fits(too_long))

    def test_rewrap_never_adds_a_fourth_line(self):
        # even an unfittable text is capped at DEX_MAX_LINES lines
        too_long = "mot " * 60
        self.assertLessEqual(rewrap(too_long.strip()).count("\n") + 1, DEX_MAX_LINES)

    def test_rewrap_is_idempotent(self):
        text = "Il esquive les attaques avec agilité et crache des boules de feu par le groin."
        once = rewrap(text)
        self.assertEqual(rewrap(once), once)


class IsDescriptionTests(unittest.TestCase):
    def test_accepts_a_real_description(self):
        self.assertTrue(is_description("Un Pokémon paisible et docile."))

    def test_accepts_degree_sign(self):
        self.assertTrue(is_description("Son corps incandescent atteint 1 200 °C."))

    def test_rejects_ability_name(self):
        self.assertFalse(is_description("Bouclier"))

    def test_rejects_control_tokens(self):
        self.assertFalse(is_description("Un texte avec <0xFD><0x01> dedans ici."))


class IterEntriesTests(unittest.TestCase):
    def setUp(self):
        # Shrink the table to a handful of records over a small ROM.
        self._base, self._count = pokedex.DEX_TABLE_BASE, pokedex.DEX_TABLE_COUNT
        pokedex.DEX_TABLE_BASE = 0x100
        pokedex.DEX_TABLE_COUNT = 4

    def tearDown(self):
        pokedex.DEX_TABLE_BASE, pokedex.DEX_TABLE_COUNT = self._base, self._count

    def test_finds_pointed_descriptions(self):
        rom = bytearray(0x4000)
        text_at = 0x800
        desc = TextEncoder.encode_pokemon("Un Pokémon vif et curieux.")
        rom[text_at:text_at + len(desc)] = desc
        # struct 0 points at the description; its pointer is at table base
        rom[0x100:0x104] = (text_at + 0x08000000).to_bytes(4, "little")
        entries = list(pokedex.iter_entries(rom))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].index, 0)
        self.assertEqual(entries[0].text_offset, text_at)
        self.assertEqual(entries[0].text, "Un Pokémon vif et curieux.")


class OverridesDataTests(unittest.TestCase):
    """The curated short descriptions must all fit the three-line window."""

    def test_overrides_file_present_and_valid(self):
        self.assertTrue(OVERRIDES.exists(), OVERRIDES)
        data = json.loads(OVERRIDES.read_text(encoding="utf-8"))
        self.assertGreater(len(data), 100)
        for offset, text in data.items():
            self.assertTrue(offset.isdigit(), offset)
            self.assertTrue(is_description(text), text)
            self.assertTrue(fits(text), f"override does not fit: {text!r}")
            self.assertLessEqual(len(text), 112, text)


if __name__ == "__main__":
    unittest.main()
