"""Regression guard for languages/de/patches/gendered_buffers.py.

Every buffer is a fixed-size slot: the German word must encode to no more
bytes (including the 0xFF terminator) than the English original occupied.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.de.patches.gendered_buffers import GENDERED_BUFFERS, encode_text


class TestGenderedBuffersDe(unittest.TestCase):
    def test_every_translation_fits_its_budget(self):
        for offset, expected_en, de_text in GENDERED_BUFFERS:
            encoded = encode_text(de_text)
            self.assertLessEqual(
                len(encoded), len(expected_en),
                f"0x{offset:08X}: '{de_text}' ({len(encoded)}B) overflows the "
                f"{len(expected_en)}B EN slot",
            )

    def test_every_translation_terminated(self):
        for _offset, _en, de_text in GENDERED_BUFFERS:
            self.assertEqual(encode_text(de_text)[-1], 0xFF)

    def test_no_duplicate_offsets(self):
        offsets = [offset for offset, _en, _de in GENDERED_BUFFERS]
        self.assertEqual(len(offsets), len(set(offsets)))

    def test_man_and_son_excluded_no_short_enough_german_word(self):
        # "Sohn"/"Mann" (4 letters) do not fit the 3-char budgets freed by
        # "son"/"man" — the DE table intentionally omits those offsets so
        # they stay in English rather than crash or silently overflow.
        de_texts = {text for _o, _e, text in GENDERED_BUFFERS}
        self.assertNotIn("Sohn", de_texts)
        self.assertNotIn("Mann", de_texts)


if __name__ == "__main__":
    unittest.main()
