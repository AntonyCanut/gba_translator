"""Regression tests for the DE DexNav header graphics patch.

The DexNav screen's four column headers ("SEARCH LEVEL", "METHOD", "HIDDEN
ABILITY", "HELD ITEMS") are baked into Unbound's custom DexNav background
tileset (4bpp tiles inside an LZ77 block) — never handled by the text
pipeline. The built DE ROM must render the German replacements in all four.

Sibling of ``test_patch_dexnav_headers_fr.py``. The tileset block is EN==ES
stable and untouched by the pipeline, so the German build still holds the
English source art until the patch runs; the compression-budget test therefore
exercises the patch against the English ROM (always available) rather than
requiring a built DE ROM.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.font import lz77_compress, lz77_decompress
from languages.de.patches.dexnav_headers import (
    HEADERS,
    TILESET_DECOMP_LEN,
    TILESET_OFFSET,
    _FONT,
    _stamp_text,
    _text_width,
    _tiles_hex,
)

ENGLISH_ROM = Path(__file__).parent.parent / "input" / "roms" / "englishrom.gba"
BUILT_DE_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-de.gba"


class TestDexNavHeaderDefinitions(unittest.TestCase):
    def test_german_text_fits_dedicated_tile_width(self):
        for _row, _first_tile, ntiles, german, _known_good in HEADERS:
            self.assertLessEqual(
                _text_width(german), ntiles * 8,
                f"{german!r} overflows its {ntiles} dedicated tiles",
            )

    def test_every_glyph_is_drawable(self):
        for _row, _first_tile, _ntiles, german, _known_good in HEADERS:
            for ch in german:
                self.assertIn(ch, _FONT, f"no glyph for {ch!r} in {german!r}")

    def test_drawn_pixels_stay_within_dedicated_tiles(self):
        # _text_width undercounts spaces (mirrors the FR helper), so guard the
        # real drawn extent: the rightmost lit column must stay inside the run.
        for _row, _first_tile, ntiles, german, _known_good in HEADERS:
            x = 0
            max_col = -1
            for ch in german:
                w = len(_FONT[ch][0])
                if ch != " ":
                    max_col = max(max_col, x + w - 1)
                x += w + 1
            self.assertLess(
                max_col, ntiles * 8,
                f"{german!r} draws past its {ntiles} dedicated tiles",
            )


class TestPatchAgainstEnglishArt(unittest.TestCase):
    """Apply the patch to the English source art (what the DE build starts
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
        for _row, first_tile, ntiles, _german, known_good in HEADERS:
            self.assertEqual(
                _tiles_hex(tiles, first_tile, ntiles), known_good,
                f"tile {first_tile}: English art drifted from the known-good "
                f"fingerprint — the patch would skip this header",
            )

    def test_recompressed_tileset_fits_original_budget(self):
        # The tilemap block follows the tileset with zero padding, so the
        # recompressed tileset must never exceed the original compressed length.
        tiles = bytearray(self.tiles_data)
        for _row, first_tile, ntiles, german, _known_good in HEADERS:
            _stamp_text(tiles, first_tile, ntiles, german)
        recompressed = lz77_compress(bytes(tiles))
        self.assertLessEqual(
            len(recompressed), self.orig_comp_len,
            "recompressed DexNav tileset overflows into the adjacent tilemap block",
        )

    def test_patched_headers_no_longer_english(self):
        tiles = bytearray(self.tiles_data)
        for _row, first_tile, ntiles, german, known_good in HEADERS:
            _stamp_text(tiles, first_tile, ntiles, german)
            self.assertNotEqual(
                _tiles_hex(tiles, first_tile, ntiles), known_good,
                f"tile {first_tile}: still shows the original English art",
            )


@pytest.mark.rom
class TestBuiltDeRomShowsGermanHeaders(unittest.TestCase):
    """The shipped DE ROM must show German text in all four header rows."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_DE_ROM.exists():
            pytest.skip("GenedRom-de.gba not built")
        cls.rom = bytearray(BUILT_DE_ROM.read_bytes())
        result = lz77_decompress(cls.rom, TILESET_OFFSET)
        assert result is not None
        cls.tiles_data, _ = result

    def test_headers_are_no_longer_english(self):
        for _row, first_tile, ntiles, _german, known_good in HEADERS:
            current = _tiles_hex(bytearray(self.tiles_data), first_tile, ntiles)
            self.assertNotEqual(
                current, known_good,
                f"tile {first_tile}: still shows the original English art",
            )

    def test_headers_render_expected_german_text(self):
        for _row, first_tile, ntiles, german, known_good in HEADERS:
            base = bytearray(self.tiles_data)
            start = first_tile * 32
            base[start:start + len(known_good) // 2] = bytes.fromhex(known_good)
            _stamp_text(base, first_tile, ntiles, german)
            expected_hex = _tiles_hex(base, first_tile, ntiles)
            actual_hex = _tiles_hex(bytearray(self.tiles_data), first_tile, ntiles)
            self.assertEqual(
                actual_hex, expected_hex,
                f"tile {first_tile}: does not render {german!r}",
            )


if __name__ == "__main__":
    unittest.main()
