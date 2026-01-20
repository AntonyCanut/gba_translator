import tempfile
import unittest
from pathlib import Path

from src.core.text_codec import TextEncoder, TextDecoder
import importlib

builder_module = importlib.import_module('src.translators.19_build_translated_rom_generic')
BuildConfig = builder_module.BuildConfig
TranslatedROMBuilder = builder_module.TranslatedROMBuilder


class InlineTextCopyTests(unittest.TestCase):
    def test_copy_inline_texts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            rom_size = 16 * 1024 * 1024

            english = bytearray(b'\x00' * rom_size)
            spanish = bytearray(b'\x00' * rom_size)

            offset = 0x2000
            en_text = 'The war continued to rage in the...'
            es_text = 'La guerra continuó haciendo estragos...'

            en_bytes = TextEncoder.encode_pokemon(en_text)
            es_bytes = TextEncoder.encode_pokemon(es_text)

            english[offset:offset + len(en_bytes)] = en_bytes
            spanish[offset:offset + len(es_bytes)] = es_bytes

            en_path = tmp_path / 'english.gba'
            es_path = tmp_path / 'spanish.gba'
            en_path.write_bytes(english)
            es_path.write_bytes(spanish)

            config = BuildConfig(
                source_rom=en_path,
                reference_rom=es_path,
                language='spanish',
                copy_inline_texts=True,
            )
            builder = TranslatedROMBuilder(config)
            self.assertTrue(builder._load_roms())
            builder.reference_texts = {}

            builder._copy_inline_texts()

            raw = bytes(builder.output_rom_data[offset:offset + len(es_bytes)])
            decoded = TextDecoder.decode_pokemon(raw, preserve_unknown=True)
            self.assertEqual(decoded, es_text)


if __name__ == '__main__':
    unittest.main()
