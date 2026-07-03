"""Unit tests for scripts/patch_font_de.py — German umlaut glyph synthesis.

These run against small synthetic font blocks and need neither a built ROM
nor the DE build pipeline, unlike tests/e2e/de/test_accent_glyphs.py which
exercises the same logic against the real (currently unbuilt) GenedRom-de.gba.

Covers the pixel-level glyph algebra `build_umlaut()` relies on: diaeresis
dot extraction (the diff between a reference é/ë-style pair) and umlaut
composition (base letter + dots, shifted down when they would collide).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import patch_font_de as mod  # noqa: E402

GLYPH_SIZE = mod.GLYPH_SIZE  # 32 bytes = 8x8 pixels at 4bpp


def _make_font_with_tiles(tiles: dict[int, bytes]) -> bytes:
    font = bytearray(mod.FONT_SIZE)
    for cp, tile in tiles.items():
        font[cp * GLYPH_SIZE:(cp + 1) * GLYPH_SIZE] = tile
    return bytes(font)


def _solid_row_tile(rows: set[int], color: int = 1) -> bytes:
    """An 8x8 tile with `color` painted across every column of `rows`."""
    pixels = [0] * 64
    for y in rows:
        for x in range(8):
            pixels[y * 8 + x] = color
    return mod.pixels_to_tile(pixels)


class TestPixelTileRoundtrip:
    def test_tile_to_pixels_and_back_is_identity(self):
        tile = bytes(range(GLYPH_SIZE))
        pixels = mod.tile_to_pixels(tile)
        assert mod.pixels_to_tile(pixels) == tile

    def test_glyph_pixels_reads_correct_slot(self):
        cp = 0x63  # CP_A_UMLAUT_LC
        tile = _solid_row_tile({3, 4})
        font = _make_font_with_tiles({cp: tile})
        assert mod.glyph_pixels(font, cp) == mod.tile_to_pixels(tile)


class TestExtractDiaeresisDots:
    def test_dots_present_only_in_the_diaeresis_variant_are_returned(self):
        base_tile = _solid_row_tile({4, 5, 6, 7})  # letter body, bottom half
        # ë = base body + two dots on row 0 at columns 2 and 5.
        with_pixels = mod.tile_to_pixels(base_tile)
        with_pixels[0 * 8 + 2] = 2
        with_pixels[0 * 8 + 5] = 2
        with_tile = mod.pixels_to_tile(with_pixels)

        font = _make_font_with_tiles({
            mod.CP_E_LC: base_tile,
            mod.CP_E_LC_DIAR: with_tile,
        })

        dots = mod.extract_diaeresis_dots(font, mod.CP_E_LC_DIAR, mod.CP_E_LC)

        assert sorted((x, y) for x, y, _ in dots) == [(2, 0), (5, 0)]
        assert all(color == 2 for _, _, color in dots)

    def test_identical_glyphs_yield_no_dots(self):
        tile = _solid_row_tile({3, 4, 5})
        font = _make_font_with_tiles({
            mod.CP_E_LC: tile,
            mod.CP_E_LC_DIAR: tile,
        })
        assert mod.extract_diaeresis_dots(font, mod.CP_E_LC_DIAR, mod.CP_E_LC) == []


class TestBuildUmlaut:
    def test_no_dots_returns_bare_base_letter(self):
        base_tile = _solid_row_tile({4, 5, 6, 7})
        font = _make_font_with_tiles({mod.CP_A_LC: base_tile})
        result = mod.build_umlaut(font, mod.CP_A_LC, diar_dots=[])
        assert result == mod.pixels_to_tile(mod.glyph_pixels(font, mod.CP_A_LC))

    def test_dots_are_placed_without_collision(self):
        # Base letter body starts at row 3 — dots at row 0 don't collide, so
        # the letter is not shifted down.
        base_tile = _solid_row_tile({3, 4, 5, 6, 7})
        font = _make_font_with_tiles({mod.CP_A_LC: base_tile})
        dots = [(2, 0, 3), (5, 0, 3)]

        result_pixels = mod.tile_to_pixels(mod.build_umlaut(font, mod.CP_A_LC, dots))

        assert result_pixels[0 * 8 + 2] == 3
        assert result_pixels[0 * 8 + 5] == 3
        # Letter body preserved at its original rows (no shift needed).
        assert result_pixels[3 * 8 + 0] != 0

    def test_letter_shifts_down_when_dots_would_collide(self):
        # Base letter body starts at row 0 — dots at row 0-1 would overwrite
        # it, so build_umlaut must shift the letter down.
        base_tile = _solid_row_tile({0, 1, 2, 3, 4, 5, 6, 7})
        font = _make_font_with_tiles({mod.CP_A_LC: base_tile})
        dots = [(2, 0, 3), (2, 1, 3)]

        result_pixels = mod.tile_to_pixels(mod.build_umlaut(font, mod.CP_A_LC, dots))

        assert result_pixels[0 * 8 + 2] == 3
        assert result_pixels[1 * 8 + 2] == 3
        # The shifted letter body must no longer occupy row 0 at an
        # untouched column (it moved down by the dot-row count).
        assert result_pixels[0 * 8 + 5] == 0

    def test_umlaut_differs_from_bare_base_letter(self):
        base_tile = _solid_row_tile({3, 4, 5, 6, 7})
        font = _make_font_with_tiles({mod.CP_A_LC: base_tile})
        dots = [(2, 0, 3), (5, 0, 3)]
        umlaut_tile = mod.build_umlaut(font, mod.CP_A_LC, dots)
        assert umlaut_tile != base_tile


class TestIsFontBlock:
    """`is_font_block()` must accept real text fonts and reject uniform
    placeholder blocks that merely pass the per-glyph density heuristic.

    Regression: block 0x46D3A8 in the built DE ROM is a non-font block whose
    every "glyph" is the same 00 10 tile (density 16). It slipped through the
    old density-only check, so its identical A/O/U base letters made Ä/Ö/Ü
    collapse to one glyph (tests/e2e/de/test_accent_glyphs.py::
    test_umlaut_slots_are_distinct_from_each_other).
    """

    SAMPLE = [0xA1, 0xA2, 0xA3, 0xBB, 0xBC, 0xD5, 0xD7]

    def test_diverse_in_range_glyphs_are_recognised_as_a_font(self):
        # Each sampled glyph gets a distinct tile whose density sits in the
        # accepted 5..60 band (a single painted row = density 8).
        tiles = {cp: _solid_row_tile({i}) for i, cp in enumerate(self.SAMPLE)}
        assert mod.is_font_block(_make_font_with_tiles(tiles))

    def test_uniform_placeholder_block_is_rejected(self):
        # Every glyph is the same 00 10 placeholder tile (density 16): passes
        # the density band but has zero glyph diversity — must be rejected so
        # the umlaut patcher never touches it.
        placeholder = bytes.fromhex("0010" * (GLYPH_SIZE // 2))
        assert 5 < mod.glyph_density(_make_font_with_tiles({0xBB: placeholder}), 0xBB) < 60
        tiles = {cp: placeholder for cp in self.SAMPLE}
        assert not mod.is_font_block(_make_font_with_tiles(tiles))

    def test_too_few_in_range_glyphs_is_rejected(self):
        # Only two glyphs are populated — below the 4-glyph density threshold.
        tiles = {0xA1: _solid_row_tile({1}), 0xA2: _solid_row_tile({2})}
        assert not mod.is_font_block(_make_font_with_tiles(tiles))


class TestUmlautTargetCodepoints:
    """CP_*_UMLAUT_* must land on the free charmap slots reserved for German
    (0x60-0x65) — a regression here silently corrupts unrelated glyphs."""

    def test_six_umlaut_slots_are_the_reserved_free_range(self):
        codepoints = {
            mod.CP_A_UMLAUT_UC, mod.CP_O_UMLAUT_UC, mod.CP_U_UMLAUT_UC,
            mod.CP_A_UMLAUT_LC, mod.CP_O_UMLAUT_LC, mod.CP_U_UMLAUT_LC,
        }
        assert codepoints == {0x60, 0x61, 0x62, 0x63, 0x64, 0x65}
