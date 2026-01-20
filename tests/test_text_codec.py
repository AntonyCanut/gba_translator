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

        self.assertEqual(
            TextEncoder.encode_pokemon('ê'),
            TextEncoder.encode_pokemon('e'),
        )
        self.assertNotEqual(
            TextEncoder.encode_pokemon('à')[0],
            TextEncoder.encode_pokemon('á')[0],
        )
        self.assertEqual(
            TextEncoder.encode_pokemon('œ'),
            TextEncoder.encode_pokemon('oe'),
        )


if __name__ == '__main__':
    unittest.main()
