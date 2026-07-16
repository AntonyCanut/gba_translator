"""Regression guard for languages/it/patches/gendered_buffers.py.

Every buffer is a fixed-size slot: the Italian word must encode to no more
bytes (including the 0xFF terminator) than the English original occupied.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.it.patches.gendered_buffers import (
    GENDERED_BUFFERS,
    _decode_word,
    encode_text,
    patch_gendered_buffers,
)


class TestGenderedBuffersIt(unittest.TestCase):
    def test_every_translation_fits_its_budget(self):
        for offset, expected_en, it_text in GENDERED_BUFFERS:
            encoded = encode_text(it_text)
            self.assertLessEqual(
                len(encoded), len(expected_en),
                f"0x{offset:08X}: '{it_text}' ({len(encoded)}B) overflows the "
                f"{len(expected_en)}B EN slot",
            )

    def test_every_translation_terminated(self):
        for _offset, _en, it_text in GENDERED_BUFFERS:
            self.assertEqual(encode_text(it_text)[-1], 0xFF)

    def test_no_duplicate_offsets(self):
        offsets = [offset for offset, _en, _it in GENDERED_BUFFERS]
        self.assertEqual(len(offsets), len(set(offsets)))

    def test_son_boy_girl_excluded_no_short_enough_italian_word(self):
        # "figlio"/"ragazzo"/"ragazza" (6-7 letters) do not fit the 3/4-char
        # budgets freed by "son"/"boy"/"girl" — the IT table intentionally
        # omits those offsets so they stay in English.
        it_texts = {text for _o, _e, text in GENDERED_BUFFERS}
        for word in ("figlio", "ragazzo", "ragazza"):
            self.assertNotIn(word, it_texts)

    def test_him_buffers_are_translated_to_lui(self):
        """Both FD02 object-pronoun slots must not leak the English ``him``."""
        him_offsets = {
            offset
            for offset, expected_en, it_text in GENDERED_BUFFERS
            if expected_en == bytes.fromhex("dcdde1ff") and it_text == "lui"
        }
        self.assertEqual(him_offsets, {0x789224, 0x1FA764E})

    def test_patch_replaces_both_him_buffers(self):
        him_entries = [
            entry for entry in GENDERED_BUFFERS
            if entry[1] == bytes.fromhex("dcdde1ff")
        ]
        rom_size = max(offset + len(expected_en) for offset, expected_en, _ in him_entries)
        with tempfile.TemporaryDirectory() as temp_dir:
            rom_path = Path(temp_dir) / "it.gba"
            rom = bytearray(rom_size)
            for offset, expected_en, _ in him_entries:
                rom[offset:offset + len(expected_en)] = expected_en
            rom_path.write_bytes(rom)

            patch_gendered_buffers(rom_path)

            patched = rom_path.read_bytes()
            for offset, expected_en, _ in him_entries:
                self.assertEqual(
                    patched[offset:offset + len(expected_en)],
                    encode_text("lui").ljust(len(expected_en), b"\x00"),
                )

    def test_decode_word_reads_until_terminator(self):
        data = encode_text("lei") + b"garbage"
        self.assertEqual(_decode_word(data, 0), "lei")


if __name__ == "__main__":
    unittest.main()
