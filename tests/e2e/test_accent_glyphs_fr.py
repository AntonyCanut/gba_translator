"""E2E: é / è render cleanly in the built FR ROM.

Ticket "Accent é": the acute accent looked bad everywhere (screenshot of the
Pokédex "Pokémon" label). Root cause — the standalone é (0x1B) / è (0x1A)
glyphs in the base international font are drawn too high (a 4-row accent that
crushes the letter body). ``patch_font_fr.py`` used to rebuild only à and ç,
so é/è shipped verbatim from that malformed source.

The fix rebuilds é/è from the clean ``e`` body (0xD9) plus the compact 2-row
accent taken from ``á`` — exactly the proven mechanism already used for ``à``.
These tests decode the BUILT FR ROM and assert that, in every render font
block (identified by ``à`` having been patched), é/è now carry the clean e
body instead of the malformed original.
"""

from scripts.patch_font_fr import (
    CP_A,
    CP_ACUTE_E,
    CP_E,
    CP_GRAVE_A,
    CP_GRAVE_E,
    build_acute_e,
    build_grave_a,
    build_grave_e,
    find_font_blocks,
    glyph_pixels,
)

GLYPH_SIZE = 32


def _body_rows(pixels):
    """Rows 2-7 — the letter body, below the rows 0-1 accent zone."""
    return pixels[16:64]


def _tile(font, cp):
    return font[cp * GLYPH_SIZE:(cp + 1) * GLYPH_SIZE]


class TestAccentedEGlyphsInBuiltRom:
    def test_e_accents_rebuilt_in_render_blocks(self, fr_rom_path):
        rom = fr_rom_path.read_bytes()
        blocks = find_font_blocks(rom)
        assert blocks, "no font blocks found in built FR ROM"

        checked = 0
        for block in blocks:
            font = block.decompressed
            # A render block is one whose à was actually patched. Some
            # duplicated blocks are restored to English by the downstream
            # LZ77-repair pass and must not be asserted on.
            if _tile(font, CP_GRAVE_A) != build_grave_a(font):
                continue
            checked += 1

            e_body = _body_rows(glyph_pixels(font, CP_E))
            for cp, builder in (
                (CP_ACUTE_E, build_acute_e),
                (CP_GRAVE_E, build_grave_e),
            ):
                assert _body_rows(glyph_pixels(font, cp)) == e_body, (
                    f"glyph 0x{cp:02X} in a patched block does not carry the "
                    f"clean e body — the malformed accent is still shipping"
                )
                assert _tile(font, cp) == builder(font), (
                    f"glyph 0x{cp:02X} in a patched block is not the rebuilt tile"
                )

        assert checked, "no à-patched render font block found in the built ROM"

    def test_e_accents_are_distinct(self, fr_rom_path):
        """é and è must not collapse to the same tile."""
        rom = fr_rom_path.read_bytes()
        for block in find_font_blocks(rom):
            font = block.decompressed
            if _tile(font, CP_GRAVE_A) != build_grave_a(font):
                continue
            assert _tile(font, CP_ACUTE_E) != _tile(font, CP_GRAVE_E), (
                "é and è resolved to identical glyphs in a patched block"
            )
