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
    BG,
    FILL,
    GHOST_TILES,
    HEADERS,
    TILE,
    TILESET_DECOMP_LEN,
    TILESET_OFFSET,
    _FONT,
    _clear_ghost_tail,
    _stamp_text,
    _text_width,
    _tiles_hex,
)


def _isolated_ghost_pixels(tiles, tile_ids):
    """Pixels in rows 0-1 of ``tile_ids`` that are letter-fill colour but do
    NOT continue into row 2 (i.e. leftover English letter tails, not part of
    a legitimate decorative shape spanning the full tile height)."""
    found = []
    for tile in tile_ids:
        for row in (0, 1):
            for col in range(8):
                off = tile * TILE + row * 4 + col // 2
                b = tiles[off]
                v = b & 0xF if col % 2 == 0 else b >> 4
                off2 = tile * TILE + 2 * 4 + col // 2
                b2 = tiles[off2]
                v2 = b2 & 0xF if col % 2 == 0 else b2 >> 4
                if v == FILL and v2 == BG:
                    found.append((tile, row, col))
    return found

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

    def test_english_art_has_known_ghost_tail(self):
        # Documents the bug fixed here (issue #90): the English source art's
        # two-word headers ("SEARCH"/"LEVEL", "HIDDEN"/"ABILITY",
        # "HELD"/"ITEMS") spill letter pixels into the tile-map row below —
        # GHOST_TILES — which _stamp_text alone never touches.
        tiles = bytearray(self.tiles_data)
        all_ghost_tiles = [t for ids in GHOST_TILES.values() for t in ids]
        self.assertTrue(
            _isolated_ghost_pixels(tiles, all_ghost_tiles),
            "expected the untouched English art to still show a letter-tail "
            "ghost below the headers — GHOST_TILES may be out of date",
        )

    def test_ghost_tail_cleared_after_patch(self):
        tiles = bytearray(self.tiles_data)
        for _row, first_tile, ntiles, german, _known_good in HEADERS:
            _stamp_text(tiles, first_tile, ntiles, german)
            _clear_ghost_tail(tiles, GHOST_TILES[first_tile])
            leftover = _isolated_ghost_pixels(tiles, GHOST_TILES[first_tile])
            self.assertFalse(
                leftover,
                f"tile {first_tile}: ghost pixels remain below {german!r}: {leftover}",
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

    def test_no_ghost_text_below_headers(self):
        # Regression test for issue #90: the shipped ROM must not show a
        # leftover English letter-tail ghost under the shortened German labels.
        tiles = bytearray(self.tiles_data)
        all_ghost_tiles = [t for ids in GHOST_TILES.values() for t in ids]
        leftover = _isolated_ghost_pixels(tiles, all_ghost_tiles)
        self.assertFalse(
            leftover,
            f"built DE ROM still shows ghost pixels below DexNav headers: {leftover}",
        )


if __name__ == "__main__":
    unittest.main()
