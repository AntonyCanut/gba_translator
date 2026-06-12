import unittest

from src.core.text_codec import TextEncoder, TextDecoder


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

    def test_electhor_species_name_bytes(self):
        """Matches the species-name table of the source ROM (Électhor)."""
        encoded = TextEncoder.encode_pokemon('Électhor')
        self.assertEqual(
            encoded,
            bytes([0x06, 0xE0, 0xD9, 0xD7, 0xE8, 0xDC, 0xE3, 0xE6, 0xFF]),
        )


if __name__ == '__main__':
    unittest.main()
