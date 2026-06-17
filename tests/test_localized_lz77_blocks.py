import unittest
from pathlib import Path

from scripts.patch_font_fr import lz77_decompress


EN_ROM = Path('input/roms/englishrom.gba')
ES_ROM = Path('input/roms/spanishrom.gba')
FR_ROM = Path('output/roms/GenedRom-fr.gba')

# Blocks where the Spanish translation is copied verbatim into the FR ROM
# by repair_localized_lz77_blocks.py (run 8 of build-fr).
# NOTE: 0xB1E280 was originally in this list (ES "DEB" fainted label) but is
# now further patched by patch_status_badges_fr.py to "KO" — a FR-specific
# override that differs from both EN and ES.  It is verified in
# TestStatusBadgeKo below.
LOCALIZED_BLOCKS = [
    0xA9B5FC,
    0xE9B4B8,
    0xE9B598,
    0xE9BA30,
]

# Fainted-status badge block patched to "KO" by patch_status_badges_fr.py.
# palette: bg=0xE (gray), letter=0x2 (white), border=0x9.
# Content tile 1 (tile 25 inside the 32-tile block) encodes "K" + left half of
# "O" across cols 0-7; row 1 pixels = [E,2,E,E,2,E,E,2].
_KO_BADGE_BLOCK = 0xB1E280
_KO_SLOT = 6          # fainted badge index inside the 32-tile block
_KO_TILE_BYTES = 32
_KO_TILES_PER_BADGE = 4
# Expected row-1 pixels of content-tile1 (4bpp lo/hi pairs):
# [BG, K0, K1, K2, K3, BG, O0, O1] = [E,2,E,E,2,E,E,2]
_KO_ROW1 = [0xE, 0x2, 0xE, 0xE, 0x2, 0xE, 0xE, 0x2]


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

    @unittest.skipUnless(FR_ROM.exists(), 'FR ROM missing')
    def test_fainted_badge_is_ko(self) -> None:
        """Block 0xB1E280 (originally ES « DEB ») must now show « KO »."""
        french = FR_ROM.read_bytes()
        result = lz77_decompress(french, _KO_BADGE_BLOCK)
        self.assertIsNotNone(result, f'Cannot decompress block 0x{_KO_BADGE_BLOCK:06X}')
        dec, _comp_len = result
        self.assertGreaterEqual(len(dec), 32 * _KO_TILE_BYTES, 'Block too small for 32 tiles')

        slot_base = _KO_SLOT * _KO_TILES_PER_BADGE * _KO_TILE_BYTES
        c1_off = slot_base + _KO_TILE_BYTES  # content tile 1

        # Decode row 1 (bytes 4-7 of the tile = 8 pixels)
        row1_bytes = dec[c1_off + 4 : c1_off + 8]
        pixels = []
        for b in row1_bytes:
            pixels.append(b & 0xF)
            pixels.append((b >> 4) & 0xF)

        self.assertEqual(
            pixels,
            _KO_ROW1,
            f'Fainted badge at slot {_KO_SLOT} tile25 row1: expected KO pattern '
            f'{_KO_ROW1} but got {pixels}. '
            'Run patch_status_badges_fr.py against the built ROM.',
        )
