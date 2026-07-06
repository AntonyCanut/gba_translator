import unittest

from src.core.text_codec import TextEncoder, TextDecoder, GERMAN_UMLAUT_CHARS


class TextCodecTests(unittest.TestCase):
    def test_roundtrip_pokemon_samples(self):
        samples = [
            'Látigo',
            'Rápido',
            'Sonámbulo',
            'Pétalo',
            'Mimético',
            'Kinético',
            'Pokémon',
            'Pisotón',
            'Puño',
            'Cuídate mucho!',
            'música de batalla',
        ]
        for text in samples:
            encoded = TextEncoder.encode_pokemon(text)
            decoded = TextDecoder.decode_pokemon(encoded)
            reencoded = TextEncoder.encode_pokemon(decoded)
            self.assertEqual(
                encoded,
                reencoded,
                msg=f"Round-trip mismatch for sample: {text}",
            )

    def test_roundtrip_pokemon_newline(self):
        text = 'Hola\nAdios'
        encoded = TextEncoder.encode_pokemon(text)
        self.assertIn(0xFE, encoded)
        decoded = TextDecoder.decode_pokemon(encoded)
        reencoded = TextEncoder.encode_pokemon(decoded)
        self.assertEqual(encoded, reencoded)

    def test_encode_inverted_punctuation_aliases(self):
        text = '¿Que? ¡Si!'
        encoded = TextEncoder.encode_pokemon(text)
        self.assertIn(0xAC, encoded)
        self.assertIn(0xAB, encoded)
        decoded = TextDecoder.decode_pokemon(encoded)
        reencoded = TextEncoder.encode_pokemon(decoded)
        self.assertEqual(encoded, reencoded)

    def test_french_accents_and_aliases(self):
        encoded = TextEncoder.encode_pokemon('àçèâî')
        self.assertEqual(encoded[0], 0x16)
        self.assertEqual(encoded[1], 0x19)
        self.assertEqual(encoded[2], 0x1A)
        self.assertEqual(encoded[3], 0x68)
        self.assertEqual(encoded[4], 0x20)
        self.assertEqual(encoded[-1], TextEncoder.POKEMON_TERMINATOR)
        decoded = TextDecoder.decode_pokemon(bytes([0x16, 0x19, 0x1A, 0x68, 0x20, 0xFF]))
        self.assertEqual(decoded, 'àçèâî')

        self.assertNotEqual(
            TextEncoder.encode_pokemon('à')[0],
            TextEncoder.encode_pokemon('á')[0],
        )

    def test_standard_gen3_accent_codepoints(self):
        """Accents must use the standard Gen III international charmap.

        The ROM fonts (dialogue and intro fullscreen, verified by mGBA
        screenshot probes) carry glyphs at the standard codepoints only:
        the old mappings (É at 0x84, ù at 0x7F…) hit the superscript-e or
        empty glyphs, which rendered "Électhor" as "ᵉlecthor".
        """
        expected = {
            'À': 0x01, 'Ç': 0x04, 'È': 0x05, 'É': 0x06, 'Ê': 0x07,
            'Ë': 0x08, 'Î': 0x0B, 'Ï': 0x0C, 'Ô': 0x0F, 'Œ': 0x10,
            'Ù': 0x11, 'Û': 0x13,
            'ê': 0x1C, 'ë': 0x1D, 'ï': 0x21, 'ô': 0x24, 'œ': 0x25,
            'ù': 0x26, 'û': 0x28,
        }
        for char, byte in expected.items():
            encoded = TextEncoder.encode_pokemon(char)
            self.assertEqual(
                encoded[0], byte,
                msg=f"{char!r} should encode to 0x{byte:02X}, got 0x{encoded[0]:02X}",
            )
            self.assertEqual(TextDecoder.decode_pokemon(bytes([byte, 0xFF])), char)

    def test_quotes_encode_to_quote_glyphs_not_ellipsis(self):
        """Quotation marks must render as quotes, never as the ellipsis glyph.

        In the FireRed/CFRU font 0xB0 is "…" (the ellipsis), and the real
        double-quote glyphs are 0xB1 "“" / 0xB2 "”" — the bytes the English
        ROM uses itself (<0xB1>evolution this<0xB2>). Folding guillemets and
        curly quotes onto 0xB0 made « cellules » render in-game as
        "… cellules …" (ticket: Zygarde cells/cores dialogue). Guillemets and
        curly double quotes must map directionally to 0xB1/0xB2 and emit no
        0xB0.
        """
        for text in ('« cellules »', '“cellules”', '«noyaux»'):
            encoded = TextEncoder.encode_pokemon(text)
            self.assertNotIn(
                0xB0, encoded,
                msg=f"{text!r} must not encode the ellipsis byte 0xB0",
            )
            self.assertIn(0xB1, encoded, msg=f"{text!r} missing open-quote 0xB1")
            self.assertIn(0xB2, encoded, msg=f"{text!r} missing close-quote 0xB2")

        # Opening guillemet/curly → 0xB1, closing → 0xB2 (directional).
        self.assertEqual(TextEncoder.encode_pokemon('«')[0], 0xB1)
        self.assertEqual(TextEncoder.encode_pokemon('»')[0], 0xB2)
        self.assertEqual(TextEncoder.encode_pokemon('“')[0], 0xB1)
        self.assertEqual(TextEncoder.encode_pokemon('”')[0], 0xB2)
        self.assertEqual(TextDecoder.decode_pokemon(bytes([0xB1, 0xB2, 0xFF])), '“”')

    def test_straight_quotes_resolve_to_directional_glyphs(self):
        """Ambiguous straight " becomes alternating “ ”, never the ellipsis.

        The font has no straight-quote glyph (0xB0 is the ellipsis), so a
        balanced pair "x" must render as “x”, not "…x…".
        """
        encoded = TextEncoder.encode_pokemon('"x"')
        self.assertNotIn(0xB0, encoded)
        self.assertEqual(encoded[0], 0xB1)   # opening
        self.assertEqual(encoded[2], 0xB2)   # closing
        # The ellipsis character itself stays the literal three dots (0xAD*3),
        # so this change does not touch genuine ellipses.
        self.assertEqual(TextEncoder.encode_pokemon('Hmm…'), bytes(
            [0xC2, 0xE1, 0xE1, 0xAD, 0xAD, 0xAD, 0xFF]))

    def test_electhor_species_name_bytes(self):
        """Matches the species-name table of the source ROM (Électhor)."""
        encoded = TextEncoder.encode_pokemon('Électhor')
        self.assertEqual(
            encoded,
            bytes([0x06, 0xE0, 0xD9, 0xD7, 0xE8, 0xDC, 0xE3, 0xE6, 0xFF]),
        )

    def test_german_umlauts_fold_to_ascii_by_default(self):
        """Without skip_aliases, ä/ö/ü/Ä/Ö/Ü fold to ASCII (FR/IT/ES safe).

        ENCODE_ALIASES maps them to a/o/u/A/O/U before table lookup, so no
        byte from slots 0xF1-0xF6 is emitted — those slots have no glyph in
        the FR/IT/ES font.
        """
        self.assertEqual(TextEncoder.encode_pokemon('ä')[0], 0xD5)  # 'a'
        self.assertEqual(TextEncoder.encode_pokemon('ö')[0], 0xE3)  # 'o'
        self.assertEqual(TextEncoder.encode_pokemon('ü')[0], 0xE9)  # 'u'
        self.assertEqual(TextEncoder.encode_pokemon('Ä')[0], 0xBB)  # 'A'
        self.assertEqual(TextEncoder.encode_pokemon('Ö')[0], 0xC9)  # 'O'
        self.assertEqual(TextEncoder.encode_pokemon('Ü')[0], 0xCF)  # 'U'

    def test_german_umlauts_encode_to_de_slots_with_skip_aliases(self):
        """With skip_aliases=GERMAN_UMLAUT_CHARS, umlauts reach slots 0xF1-0xF6.

        These slots have real glyphs in the DE ROM (drawn by
        languages/de/patches/font.py). The test proves the fix for B-81 / F-50:
        ENCODE_ALIASES was stripping umlauts before table lookup, so the umlaut
        slots were never emitted. The slots must match the game font — 0xF1-0xF6,
        the same values as src/text/charmap_data.py and font.py — NOT the stale
        0x60-0x65 the encoder table used to hold.
        """
        expected = {
            'Ä': 0xF1, 'Ö': 0xF2, 'Ü': 0xF3,
            'ä': 0xF4, 'ö': 0xF5, 'ü': 0xF6,
        }
        for char, byte in expected.items():
            encoded = TextEncoder.encode_pokemon(char, skip_aliases=GERMAN_UMLAUT_CHARS)
            self.assertEqual(
                encoded[0], byte,
                msg=f"DE: {char!r} should encode to 0x{byte:02X}, got 0x{encoded[0]:02X}",
            )

    def test_german_umlaut_word_de(self):
        """Full word 'Talhöhle' with skip_aliases encodes ö as 0xF5."""
        encoded = TextEncoder.encode_pokemon('Talhöhle', skip_aliases=GERMAN_UMLAUT_CHARS)
        # T=0xCE a=0xD5 l=0xE0 h=0xDC ö=0xF5 h=0xDC l=0xE0 e=0xD9 FF
        self.assertEqual(encoded[4], 0xF5, "ö in 'Talhöhle' must encode to 0xF5 (DE slot)")
        # Sanity: without skip_aliases, ö folds to o (0xE3)
        encoded_fr = TextEncoder.encode_pokemon('Talhöhle')
        self.assertEqual(encoded_fr[4], 0xE3)

    def test_french_accents_unaffected_by_skip_aliases(self):
        """French accented chars (à ç è etc.) are unaffected by DE skip_aliases."""
        fr_chars = {'à': 0x16, 'ç': 0x19, 'è': 0x1A, 'é': 0x1B, 'ê': 0x1C}
        for char, byte in fr_chars.items():
            encoded = TextEncoder.encode_pokemon(char, skip_aliases=GERMAN_UMLAUT_CHARS)
            self.assertEqual(
                encoded[0], byte,
                msg=f"FR accent {char!r} should be unaffected by DE skip_aliases",
            )

    def test_decode_german_umlaut_slots(self):
        """Decoder correctly maps bytes 0xF1-0xF6 back to Ä Ö Ü ä ö ü."""
        cases = [
            (0xF1, 'Ä'), (0xF2, 'Ö'), (0xF3, 'Ü'),
            (0xF4, 'ä'), (0xF5, 'ö'), (0xF6, 'ü'),
        ]
        for byte, char in cases:
            decoded = TextDecoder.decode_pokemon(bytes([byte, 0xFF]))
            self.assertEqual(decoded, char, msg=f"0x{byte:02X} should decode to {char!r}")


if __name__ == '__main__':
    unittest.main()
