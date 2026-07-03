"""Regression tests for the IT DexNav header graphics patch.

The DexNav screen's four column headers ("SEARCH LEVEL", "METHOD", "HIDDEN
ABILITY", "HELD ITEMS") are baked into Unbound's custom DexNav background
tileset (4bpp tiles inside an LZ77 block) — never handled by the text
pipeline. The built IT ROM must render the Italian replacements in all four.

Sibling of ``test_patch_dexnav_headers_de.py``. The tileset block is EN==ES
stable and untouched by the pipeline, so the Italian build still holds the
English source art until the patch runs; the compression-budget test therefore
exercises the patch against the English ROM (always available) rather than
requiring a built IT ROM.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.patch_font_fr import lz77_compress, lz77_decompress
from scripts.patch_dexnav_headers_it import (
    HEADERS,
    TILESET_DECOMP_LEN,
    TILESET_OFFSET,
    _FONT,
    _stamp_text,
    _text_width,
    _tiles_hex,
)

ENGLISH_ROM = Path(__file__).parent.parent.parent.parent / "input" / "roms" / "englishrom.gba"
BUILT_IT_ROM = Path(__file__).parent.parent.parent.parent / "output" / "roms" / "GenedRom-it.gba"


class TestDexNavHeaderDefinitions(unittest.TestCase):
    def test_italian_text_fits_dedicated_tile_width(self):
        for _row, _first_tile, ntiles, italian, _known_good in HEADERS:
            self.assertLessEqual(
                _text_width(italian), ntiles * 8,
                f"{italian!r} overflows its {ntiles} dedicated tiles",
            )

    def test_every_glyph_is_drawable(self):
        for _row, _first_tile, _ntiles, italian, _known_good in HEADERS:
            for ch in italian:
                self.assertIn(ch, _FONT, f"no glyph for {ch!r} in {italian!r}")

    def test_drawn_pixels_stay_within_dedicated_tiles(self):
        # _text_width undercounts spaces (mirrors the FR helper), so guard the
        # real drawn extent: the rightmost lit column must stay inside the run.
        for _row, _first_tile, ntiles, italian, _known_good in HEADERS:
            x = 0
            max_col = -1
            for ch in italian:
                w = len(_FONT[ch][0])
                if ch != " ":
                    max_col = max(max_col, x + w - 1)
                x += w + 1
            self.assertLess(
                max_col, ntiles * 8,
                f"{italian!r} draws past its {ntiles} dedicated tiles",
            )


class TestPatchAgainstEnglishArt(unittest.TestCase):
    """Apply the patch to the English source art (what the IT build starts
    from) and check every header translates and the block stays in budget."""

    @classmethod
    def setUpClass(cls):
        if not ENGLISH_ROM.exists():
            pytest.skip("englishrom.gba not available")
        rom = bytearray(ENGLISH_ROM.read_bytes())
        result = lz77_decompress(rom, TILESET_OFFSET)
        assert result is not None
        cls.tiles_data, cls.orig_comp_len = result

    def test_english_art_matches_known_good_fingerprints(self):
        tiles = bytearray(self.tiles_data)
        self.assertEqual(len(tiles), TILESET_DECOMP_LEN)
        for _row, first_tile, ntiles, _italian, known_good in HEADERS:
            self.assertEqual(
                _tiles_hex(tiles, first_tile, ntiles), known_good,
                f"tile {first_tile}: English art drifted from the known-good "
                f"fingerprint — the patch would skip this header",
            )

    def test_recompressed_tileset_fits_original_budget(self):
        # The tilemap block follows the tileset with zero padding, so the
        # recompressed tileset must never exceed the original compressed length.
        tiles = bytearray(self.tiles_data)
        for _row, first_tile, ntiles, italian, _known_good in HEADERS:
            _stamp_text(tiles, first_tile, ntiles, italian)
        recompressed = lz77_compress(bytes(tiles))
        self.assertLessEqual(
            len(recompressed), self.orig_comp_len,
            "recompressed DexNav tileset overflows into the adjacent tilemap block",
        )

    def test_patched_headers_no_longer_english(self):
        tiles = bytearray(self.tiles_data)
        for _row, first_tile, ntiles, italian, known_good in HEADERS:
            _stamp_text(tiles, first_tile, ntiles, italian)
            self.assertNotEqual(
                _tiles_hex(tiles, first_tile, ntiles), known_good,
                f"tile {first_tile}: still shows the original English art",
            )


@pytest.mark.rom
class TestBuiltItRomShowsItalianHeaders(unittest.TestCase):
    """The shipped IT ROM must show Italian text in all four header rows."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_IT_ROM.exists():
            pytest.skip("GenedRom-it.gba not built")
        cls.rom = bytearray(BUILT_IT_ROM.read_bytes())
        result = lz77_decompress(cls.rom, TILESET_OFFSET)
        assert result is not None
        cls.tiles_data, _ = result

    def test_headers_are_no_longer_english(self):
        for _row, first_tile, ntiles, _italian, known_good in HEADERS:
            current = _tiles_hex(bytearray(self.tiles_data), first_tile, ntiles)
            self.assertNotEqual(
                current, known_good,
                f"tile {first_tile}: still shows the original English art",
            )

    def test_headers_render_expected_italian_text(self):
        for _row, first_tile, ntiles, italian, known_good in HEADERS:
            base = bytearray(self.tiles_data)
            start = first_tile * 32
            base[start:start + len(known_good) // 2] = bytes.fromhex(known_good)
            _stamp_text(base, first_tile, ntiles, italian)
            expected_hex = _tiles_hex(base, first_tile, ntiles)
            actual_hex = _tiles_hex(bytearray(self.tiles_data), first_tile, ntiles)
            self.assertEqual(
                actual_hex, expected_hex,
                f"tile {first_tile}: does not render {italian!r}",
            )


if __name__ == "__main__":
    unittest.main()
