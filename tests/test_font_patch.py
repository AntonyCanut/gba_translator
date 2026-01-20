import unittest
from pathlib import Path

from scripts.patch_font_fr import apply_patches, glyph_density, is_font_block, lz77_decompress


EN_ROM = Path('input/roms/englishrom.gba')


def _font_space_densities(rom_data: bytes) -> list[int]:
    ptrs = set()
    rom_len = len(rom_data)
    for i in range(0, rom_len - 3, 4):
        val = int.from_bytes(rom_data[i:i + 4], 'little')
        if 0x08000000 <= val < 0x0A000000:
            off = val - 0x08000000
            if 0 <= off < rom_len:
                ptrs.add(off)

    densities = []
    header = bytes((0x10, 0x00, 0x20, 0x00))
    start = 0
    while True:
        idx = rom_data.find(header, start)
        if idx == -1:
            break
        start = idx + 1
        result = lz77_decompress(rom_data, idx)
        if result is None:
            continue
        decompressed, _comp_len = result
        if len(decompressed) != 0x2000:
            continue
        if idx not in ptrs:
            continue
        if not is_font_block(decompressed):
            continue
        densities.append(glyph_density(decompressed, 0x00))
    return densities


class TestFontPatchSpaceGlyph(unittest.TestCase):
    @unittest.skipUnless(EN_ROM.exists(), 'English ROM missing')
    def test_space_glyphs_preserved(self) -> None:
        original = EN_ROM.read_bytes()
        original_densities = _font_space_densities(original)
        if not original_densities:
            self.skipTest('No fonts found in ROM')

        patched = bytearray(original)
        apply_patches(patched)
        patched_densities = _font_space_densities(bytes(patched))

        self.assertEqual(
            sorted(original_densities),
            sorted(patched_densities),
            'Space glyph densities should be preserved after patching',
        )
