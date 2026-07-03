"""E2E: à/è/é/ì/ò/ù render cleanly in the built Italian ROM.

Italian accents split across two different mechanisms:

- à/è/é reuse the shared FR font patch (``languages/it/lang.yaml`` documents
  that Italian's grave/acute vowel set is already covered by the FR glyph
  work, and ``build_language.py``'s ``_font_script_for`` falls back to
  ``patch_font_fr.py`` for every non-German language). Mirrors
  ``tests/e2e/fr/test_accent_glyphs.py`` and
  ``tests/e2e/de/test_accent_glyphs.py``, applied to the built IT ROM.
- ì/ò/ù are native CFRU charmap codepoints (0x1E/0x22/0x26) that ship
  pre-drawn in the base international font — no patch step touches them.
  These are verified via a codec round-trip and by locating real Italian
  words that use them inside the built ROM.
"""

from __future__ import annotations

from scripts.patch_font_fr import (
    CP_ACUTE_E,
    CP_E,
    CP_GRAVE_A,
    CP_GRAVE_E,
    acute_accent_positions,
    build_acute_e,
    build_grave_a,
    build_grave_e,
    find_font_blocks,
    glyph_pixels,
)
from src.core.text_codec import TextDecoder, TextEncoder

GLYPH_SIZE = 32


def _body_rows(pixels):
    """Rows 2-7 — the letter body, below the rows 0-1 accent zone."""
    return pixels[16:64]


def _tile(font, cp):
    return font[cp * GLYPH_SIZE:(cp + 1) * GLYPH_SIZE]


class TestAccentedAEGlyphsInBuiltRom:
    """à/é/è must carry the same font-patch fix already proven for FR/DE."""

    def test_e_accents_rebuilt_in_render_blocks(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        blocks = find_font_blocks(rom)
        assert blocks, "no font blocks found in built IT ROM"

        checked = 0
        for block in blocks:
            font = block.decompressed
            if _tile(font, CP_GRAVE_A) != build_grave_a(font):
                continue  # this block's à copy was never patched (or reverted)
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

        assert checked, "no à-patched render font block found in the built IT ROM"

    def test_e_accents_are_distinct(self, it_rom_path):
        """é and è must not collapse to the same tile in blocks that carry an accent."""
        rom = it_rom_path.read_bytes()
        checked = 0
        for block in find_font_blocks(rom):
            font = block.decompressed
            if _tile(font, CP_GRAVE_A) != build_grave_a(font):
                continue
            if not acute_accent_positions(font):
                continue  # no accent source -> à/é/è render as bare letters
            checked += 1
            assert _tile(font, CP_ACUTE_E) != _tile(font, CP_GRAVE_E), (
                "é and è resolved to identical glyphs in a patched block"
            )
        assert checked, "no accent-bearing render block found to compare é/è"


class TestNativeAccentedVowelsRoundtrip:
    """ì/ò/ù are pre-existing charmap codepoints — verify the codec agrees."""

    def test_grave_i_o_u_encode_to_expected_codepoints(self):
        assert TextEncoder.encode_pokemon("ì") == bytes([0x1E, 0xFF])
        assert TextEncoder.encode_pokemon("ò") == bytes([0x22, 0xFF])
        assert TextEncoder.encode_pokemon("ù") == bytes([0x26, 0xFF])

    def test_grave_i_o_u_roundtrip(self):
        for char in "ìòù":
            encoded = TextEncoder.encode_pokemon(char)[:-1]  # drop terminator
            decoded = TextDecoder.decode_pokemon(encoded, preserve_unknown=True)
            assert decoded == char, f"{char!r} did not round-trip: got {decoded!r}"


class TestItalianWordsWithAccentsInBuiltRom:
    """Real Italian words carrying ì/ò/ù must be present verbatim in the ROM."""

    WORDS_BY_CHAR = {
        "ù": "più",
        "ì": "così",
        "ò": "però",
    }

    def _encode(self, text: str) -> bytes:
        return TextEncoder.encode_pokemon(text)[:-1]  # drop terminator

    def test_words_present_in_built_rom(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        for char, word in self.WORDS_BY_CHAR.items():
            signature = self._encode(word)
            assert rom.find(signature) != -1, (
                f"Italian word {word!r} (carrying accented {char!r}) not found "
                "in the built IT ROM — translations using this glyph may be "
                "missing or the charmap encoding may have regressed."
            )
