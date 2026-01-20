import unittest

from src.core.text_reinserter import SmartReinserter


class SmartReinserterTests(unittest.TestCase):
    def test_reinsert_raw_bytes_with_max_length(self):
        rom = bytearray(b'\x00' * 8)
        reinserter = SmartReinserter(rom, allow_truncate=False)

        translation = {
            'offset': 0,
            'raw_bytes': b'\x01\x02\xFF',
            'encoding': 'pokemon',
            'original_length': 1,
            'max_length': 3,
        }

        success = reinserter.reinsert_text(translation)
        self.assertTrue(success)
        self.assertEqual(bytes(rom[:3]), b'\x01\x02\xFF')

    def test_reinsert_raw_bytes_too_long(self):
        rom = bytearray(b'\x00' * 8)
        reinserter = SmartReinserter(rom, allow_truncate=False)

        translation = {
            'offset': 0,
            'raw_bytes': b'\x01\x02\x03\xFF',
            'encoding': 'pokemon',
            'original_length': 1,
            'max_length': 3,
        }

        success = reinserter.reinsert_text(translation)
        self.assertFalse(success)
        report = reinserter.get_report()
        self.assertEqual(report['statistics']['skipped_too_long'], 1)


if __name__ == '__main__':
    unittest.main()
