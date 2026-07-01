import unittest
from pathlib import Path

from scripts.patch_font_fr import (
    CP_A,
    CP_ACUTE_E,
    CP_E,
    CP_GRAVE_A,
    CP_GRAVE_E,
    WIDTH_TABLE_OFFSETS,
    apply_patches,
    build_acute_e,
    build_grave_a,
    build_grave_e,
    find_font_blocks,
    glyph_density,
    glyph_pixels,
    is_font_block,
    lz77_decompress,
    tile_to_pixels,
)


EN_ROM = Path('input/roms/englishrom.gba')


def _body_rows(pixels):
    """Rows 2-7 (the letter body, excluding the rows 0-1 accent zone)."""
    return pixels[16:64]


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


class TestAccentedEGlyphs(unittest.TestCase):
    """é (0x1B) / è (0x1A) must be rebuilt from the clean ``e`` body plus the
    compact á accent — the standalone é/è in the base international font are
    drawn too high and crush the letter body."""

    @unittest.skipUnless(EN_ROM.exists(), 'English ROM missing')
    def setUp(self) -> None:
        blocks = find_font_blocks(EN_ROM.read_bytes())
        self.assertTrue(blocks, 'No font blocks found in ROM')
        self.font = blocks[0].decompressed

    def test_e_body_is_preserved(self) -> None:
        e_body = _body_rows(glyph_pixels(self.font, CP_E))
        for cp, builder in ((CP_ACUTE_E, build_acute_e), (CP_GRAVE_E, build_grave_e)):
            rebuilt = _body_rows(tile_to_pixels(builder(self.font)))
            self.assertEqual(
                rebuilt, e_body,
                f'rebuilt glyph 0x{cp:02X} must keep the clean e body (rows 2-7)',
            )

    def test_rebuilt_replaces_malformed_original(self) -> None:
        for cp, builder in ((CP_ACUTE_E, build_acute_e), (CP_GRAVE_E, build_grave_e)):
            original_body = _body_rows(glyph_pixels(self.font, cp))
            e_body = _body_rows(glyph_pixels(self.font, CP_E))
            # The malformed original does NOT share the e body...
            self.assertNotEqual(
                original_body, e_body,
                f'sanity: original 0x{cp:02X} should differ from e before the fix',
            )
            # ...but the rebuilt glyph does, and thus changes the tile.
            self.assertNotEqual(
                builder(self.font),
                self.font[cp * 32:(cp + 1) * 32],
                f'rebuilt 0x{cp:02X} must differ from the malformed original',
            )

    def test_acute_and_grave_are_distinct(self) -> None:
        self.assertNotEqual(
            build_acute_e(self.font), build_grave_e(self.font),
            'é and è must be distinguishable glyphs, not identical tiles',
        )

    def test_accent_lives_in_rows_0_1(self) -> None:
        """The rebuilt glyph only differs from bare ``e`` in the accent zone."""
        e_pixels = glyph_pixels(self.font, CP_E)
        for builder in (build_acute_e, build_grave_e):
            rebuilt = tile_to_pixels(builder(self.font))
            changed_rows = {i // 8 for i in range(64) if rebuilt[i] != e_pixels[i]}
            self.assertTrue(changed_rows <= {0, 1}, f'accent leaked into rows {changed_rows}')

    def test_apply_patches_rewrites_e_accents(self) -> None:
        rom = bytearray(EN_ROM.read_bytes())
        apply_patches(rom)
        patched_blocks = [b for b in find_font_blocks(bytes(rom))]
        self.assertTrue(patched_blocks)
        checked = 0
        for block in patched_blocks:
            font = block.decompressed
            # Only render blocks where à was actually patched carry the fix;
            # some duplicate blocks are restored to English downstream.
            if font[CP_GRAVE_A * 32:(CP_GRAVE_A + 1) * 32] != build_grave_a(font):
                continue
            checked += 1
            self.assertEqual(
                font[CP_ACUTE_E * 32:(CP_ACUTE_E + 1) * 32], build_acute_e(font),
                'é not rebuilt in a patched font block',
            )
            self.assertEqual(
                font[CP_GRAVE_E * 32:(CP_GRAVE_E + 1) * 32], build_grave_e(font),
                'è not rebuilt in a patched font block',
            )
        self.assertTrue(checked, 'no à-patched font block found to verify é/è')

    def test_width_tables_alias_e_accents_to_e(self) -> None:
        rom = bytearray(EN_ROM.read_bytes())
        apply_patches(rom)
        checked = 0
        for offset in WIDTH_TABLE_OFFSETS:
            if offset + 0x100 > len(rom):
                continue
            e_width = rom[offset + CP_E]
            if e_width == 0:
                continue
            checked += 1
            self.assertEqual(rom[offset + CP_ACUTE_E], e_width, 'é width != e width')
            self.assertEqual(rom[offset + CP_GRAVE_E], e_width, 'è width != e width')
        self.assertTrue(checked, 'no width table with a live e width found')
