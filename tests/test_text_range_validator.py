import unittest

from src.validators.text_range_validator import validate_text_ranges


class TextRangeValidatorTests(unittest.TestCase):
    def test_validate_text_ranges_detects_mismatch(self):
        output_rom = bytearray(64)
        reference_rom = bytearray(64)

        reference_rom[10:13] = b'HI\x00'
        output_rom[20:23] = b'HI\x00'

        reference_rom[30:33] = b'OK\x00'
        output_rom[40:43] = b'NO\x00'

        offset_map = [
            {'english_offset': 20, 'spanish_offset': 10, 'status': 'matched'},
            {'english_offset': 40, 'spanish_offset': 30, 'status': 'matched'},
        ]

        reference_texts = {
            10: {'byte_length': 3, 'encoding': 'ascii', 'decoded_text': 'HI'},
            30: {'byte_length': 3, 'encoding': 'ascii', 'decoded_text': 'OK'},
        }

        report = validate_text_ranges(
            output_rom=bytes(output_rom),
            reference_rom=bytes(reference_rom),
            offset_map=offset_map,
            reference_texts=reference_texts,
            sample_rate=1.0,
            max_mismatches=10,
        )

        stats = report['statistics']
        self.assertEqual(stats['total_compared'], 2)
        self.assertEqual(stats['total_mismatched'], 1)
        self.assertEqual(stats['total_matched'], 1)

        mismatch = report['mismatches'][0]
        self.assertEqual(mismatch['expected_text'], 'OK')
        self.assertEqual(mismatch['actual_text'], 'NO')


if __name__ == '__main__':
    unittest.main()
