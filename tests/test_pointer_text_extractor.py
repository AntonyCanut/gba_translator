import tempfile
import unittest
from pathlib import Path

from src.core.text_codec import TextEncoder
from src.extractors.pointer_text_extractor import PointerTextExtractor


class PointerTextExtractorTests(unittest.TestCase):
    def test_read_text_detects_pokemon(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            rom_path = Path(tmp_dir) / 'dummy.gba'
            rom_size = 16 * 1024 * 1024
            rom_data = bytearray(rom_size)

            text = 'Hola'
            encoded = TextEncoder.encode_pokemon(text)
            offset = 0x100
            rom_data[offset:offset + len(encoded)] = encoded

            rom_path.write_bytes(rom_data)

            extractor = PointerTextExtractor(
                rom_path=rom_path,
                output_dir=Path(tmp_dir),
                detect_scan=64,
            )
            entry = extractor._read_text(offset)

            self.assertIsNotNone(entry)
            self.assertEqual(entry['decoded_text'], text)

    def test_scan_all_pointers_unaligned(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            rom_path = Path(tmp_dir) / 'dummy_unaligned.gba'
            rom_size = 16 * 1024 * 1024
            rom_data = bytearray(rom_size)

            text = 'Choose a character.'
            encoded = TextEncoder.encode_pokemon(text)
            text_offset = 0x100
            rom_data[text_offset:text_offset + len(encoded)] = encoded

            ptr_value = 0x08000000 + text_offset
            ptr_offset = 0x202  # unaligned (alignment 2)
            rom_data[ptr_offset:ptr_offset + 4] = ptr_value.to_bytes(4, 'little')

            rom_path.write_bytes(rom_data)

            extractor = PointerTextExtractor(
                rom_path=rom_path,
                output_dir=Path(tmp_dir),
                scan_all_pointers=True,
                scan_alignments=[2],
            )
            data = extractor.extract()
            offsets = {item['offset'] for item in data['texts']}

            self.assertIn(text_offset, offsets)


if __name__ == '__main__':
    unittest.main()
