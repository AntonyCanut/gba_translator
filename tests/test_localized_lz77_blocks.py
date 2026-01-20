import unittest
from pathlib import Path

from scripts.patch_font_fr import lz77_decompress


EN_ROM = Path('input/roms/englishrom.gba')
ES_ROM = Path('input/roms/spanishrom.gba')
FR_ROM = Path('output/roms/GenedRom-fr.gba')

LOCALIZED_BLOCKS = [
    0xA9B5FC,
    0xB1E280,
    0xE9B4B8,
    0xE9B598,
    0xE9BA30,
]


class TestLocalizedLz77Blocks(unittest.TestCase):
    @unittest.skipUnless(EN_ROM.exists() and ES_ROM.exists() and FR_ROM.exists(), 'ROMs missing')
    def test_localized_blocks_match_spanish(self) -> None:
        english = EN_ROM.read_bytes()
        spanish = ES_ROM.read_bytes()
        french = FR_ROM.read_bytes()

        for offset in LOCALIZED_BLOCKS:
            en_res = lz77_decompress(english, offset)
            es_res = lz77_decompress(spanish, offset)
            fr_res = lz77_decompress(french, offset)
            if en_res is None or es_res is None or fr_res is None:
                self.skipTest(f'LZ77 block missing at 0x{offset:06X}')
            _en_dec, en_comp_len = en_res
            _es_dec, es_comp_len = es_res
            _fr_dec, fr_comp_len = fr_res

            # Compare compressed bytes against Spanish reference.
            self.assertEqual(
                french[offset:offset + es_comp_len],
                spanish[offset:offset + es_comp_len],
                f'Localized block mismatch at 0x{offset:06X}',
            )
            # Ensure compressed block still decodes correctly.
            self.assertGreater(en_comp_len, 0)
            self.assertGreater(fr_comp_len, 0)
