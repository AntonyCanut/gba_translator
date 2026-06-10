import struct
import unittest

from src.core.text_codec import TextEncoder
from src.core.text_reinserter import SmartReinserter


class ReinserterRelocationTests(unittest.TestCase):
    def test_relocate_updates_pointer(self):
        rom = bytearray([0xFF] * 0x200)
        original_offset = 0x20
        rom[0:4] = struct.pack('<I', 0x08000000 + original_offset)

        original = TextEncoder.encode_pokemon('Hi')
        rom[original_offset:original_offset + len(original)] = original

        translation = {
            'offset': original_offset,
            'translation': 'Hello world',
            'encoding': 'pokemon',
            'original_length': 2,
            'padding_available': 0,
            'pointer_offsets': [0],
        }

        reinserter = SmartReinserter(rom, allow_relocate=True)
        success = reinserter.reinsert_text(translation)
        self.assertTrue(success)
        reinserter.flush_relocations()

        new_pointer = struct.unpack('<I', rom[0:4])[0] - 0x08000000
        self.assertNotEqual(new_pointer, original_offset)

        expected = TextEncoder.encode_pokemon('Hello world')
        actual = bytes(rom[new_pointer:new_pointer + len(expected)])
        self.assertEqual(expected, actual)


if __name__ == '__main__':
    unittest.main()
