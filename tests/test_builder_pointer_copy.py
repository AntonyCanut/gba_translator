import importlib
import unittest
from pathlib import Path

builder_module = importlib.import_module('src.translators.19_build_translated_rom_generic')
BuildConfig = builder_module.BuildConfig
TranslatedROMBuilder = builder_module.TranslatedROMBuilder


class BuilderPointerCopyTests(unittest.TestCase):
    def test_copy_text_pointers_unaligned(self):
        config = BuildConfig(
            source_rom=Path('dummy.gba'),
            reference_rom=None,
            copy_text_pointers=True,
        )
        builder = TranslatedROMBuilder(config)

        base = 0x08000000
        text_offset = 0x10
        ref_ptr = base + text_offset
        en_ptr = base + 0x20

        builder.reference_texts = {text_offset: {'byte_length': 3}}
        builder.reference_rom_data = bytearray(b'\x00' * 64)
        builder.output_rom_data = bytearray(b'\x00' * 64)

        # Unaligned pointer positions
        builder.reference_rom_data[1:5] = ref_ptr.to_bytes(4, 'little')
        builder.output_rom_data[1:5] = en_ptr.to_bytes(4, 'little')

        builder._copy_text_pointers()

        self.assertEqual(builder.output_rom_data[1:5], builder.reference_rom_data[1:5])
        self.assertEqual(builder.stats.text_pointers_copied, 1)


if __name__ == '__main__':
    unittest.main()
