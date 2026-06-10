"""Tests for the shrink-to-fit fallback synthesizer and its reinserter wiring."""

import unittest

from src.core.fallback_translator import FallbackSynthesizer
from src.core.text_codec import TextEncoder
from src.core.text_reinserter import SmartReinserter


class FallbackSynthesizerTests(unittest.TestCase):
    def setUp(self):
        self.synth = FallbackSynthesizer()

    def _encoded_len(self, text):
        return len(TextEncoder.encode(text, "pokemon"))

    def test_already_fits_is_unchanged(self):
        result = self.synth.shrink_to_fit("Salut", "pokemon", 32)
        self.assertEqual(result.strategy, "none")
        self.assertTrue(result.fits)
        self.assertEqual(result.text, "Salut")

    def test_whitespace_is_lossless_first_resort(self):
        # "A    B" -> "A B" saves 3 bytes, no information lost.
        result = self.synth.shrink_to_fit("A    B", "pokemon", 4)
        self.assertEqual(result.strategy, "whitespace")
        self.assertTrue(result.fits)
        self.assertEqual(result.text, "A B")

    def test_abbreviation_when_whitespace_not_enough(self):
        text = "Réponds s'il te plaît"
        budget = self._encoded_len("Réponds stp")  # exactly the abbreviated size
        result = self.synth.shrink_to_fit(text, "pokemon", budget)
        self.assertEqual(result.strategy, "abbreviate")
        self.assertIn("stp", result.text)
        self.assertTrue(result.fits)

    def test_truncates_at_word_boundary(self):
        text = "hello world foo"
        budget = 12  # room for "hello world" + terminator
        result = self.synth.shrink_to_fit(text, "pokemon", budget)
        self.assertEqual(result.strategy, "truncate")
        self.assertTrue(result.fits)
        self.assertEqual(result.text, "hello world")  # no dangling half-word

    def test_truncation_always_fits_the_budget(self):
        text = "abcdefghijklmnop"  # one long word, no spaces to cut on
        budget = 6
        result = self.synth.shrink_to_fit(text, "pokemon", budget)
        self.assertTrue(result.fits)
        self.assertLessEqual(self._encoded_len(result.text), budget)

    def test_control_tokens_are_never_split(self):
        import re

        # A "<0xNN>" escape must survive whole — never clipped to a lone "<0x".
        text = "Bonjour<0xFD>le monde entier vraiment long"
        budget = 12
        result = self.synth.shrink_to_fit(text, "pokemon", budget)
        self.assertTrue(result.fits)
        self.assertLessEqual(self._encoded_len(result.text), budget)
        # Every "<0x" fragment in the output is part of a complete token.
        complete = len(re.findall(r"<(?:0x)?[0-9A-Fa-f]{2}>", result.text))
        self.assertEqual(result.text.count("<0x"), complete)


class ReinserterFallbackTests(unittest.TestCase):
    def test_too_long_text_is_synthesized_instead_of_skipped(self):
        rom = bytearray(b"\x00" * 64)
        reinserter = SmartReinserter(rom, allow_fallback=True)

        translation = {
            "offset": 0,
            "translation": "Voici une phrase beaucoup trop longue pour ce slot",
            "encoding": "pokemon",
            "original_length": 4,
            "max_length": 8,  # only 8 bytes available (terminator included)
        }

        success = reinserter.reinsert_text(translation)
        report = reinserter.get_report()

        self.assertTrue(success)
        self.assertEqual(report["statistics"]["fallback_used"], 1)
        self.assertEqual(report["statistics"]["skipped_too_long"], 0)
        # Something French was written and it is terminated within the slot.
        self.assertNotEqual(rom[0], 0)
        self.assertIn(TextEncoder.POKEMON_TERMINATOR, rom[:8])

    def test_without_fallback_still_skips(self):
        rom = bytearray(b"\x00" * 64)
        reinserter = SmartReinserter(rom, allow_fallback=False)

        translation = {
            "offset": 0,
            "translation": "Phrase beaucoup trop longue",
            "encoding": "pokemon",
            "original_length": 4,
            "max_length": 8,
        }

        success = reinserter.reinsert_text(translation)
        report = reinserter.get_report()

        self.assertFalse(success)
        self.assertEqual(report["statistics"]["skipped_too_long"], 1)


if __name__ == "__main__":
    unittest.main()
