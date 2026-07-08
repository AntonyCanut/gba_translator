"""Regression tests for the FR DexNav header graphics patch.

The DexNav screen's four column headers ("SEARCH LEVEL", "METHOD", "HIDDEN
ABILITY", "HELD ITEMS") are baked into Unbound's custom DexNav background
tileset (4bpp tiles inside an LZ77 block) — never handled by the text
pipeline. The built FR ROM must render the French replacements in all four.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.font import lz77_compress, lz77_decompress
from languages.fr.patches.dexnav_headers import (
    BG,
    FILL,
    GHOST_TILES,
    HEADERS,
    TILE,
    TILESET_DECOMP_LEN,
    TILESET_OFFSET,
    _clear_ghost_tail,
    _stamp_text,
    _text_width,
    _tiles_hex,
)

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"


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


class TestDexNavHeaderDefinitions(unittest.TestCase):
    def test_french_text_fits_dedicated_tile_width(self):
        for _row, _first_tile, ntiles, french, _known_good in HEADERS:
            self.assertLessEqual(
                _text_width(french), ntiles * 8,
                f"{french!r} overflows its {ntiles} dedicated tiles",
            )

    def test_recompressed_tileset_fits_original_budget(self):
        # The tilemap block follows the tileset with zero padding, so the
        # recompressed tileset must never exceed the ROM's original
        # compressed length (see patch_dexnav_headers_fr module docstring).
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        rom_bytes = bytearray(BUILT_FR_ROM.read_bytes())
        result = lz77_decompress(rom_bytes, TILESET_OFFSET)
        self.assertIsNotNone(result)
        tiles_data, orig_comp_len = result
        self.assertEqual(len(tiles_data), TILESET_DECOMP_LEN)

        tiles = bytearray(tiles_data)
        for _row, first_tile, ntiles, french, known_good in HEADERS:
            current = _tiles_hex(tiles, first_tile, ntiles)
            if current == known_good:
                _stamp_text(tiles, first_tile, ntiles, french)
            # else: already patched (idempotent) — tiles already French.

        recompressed = lz77_compress(bytes(tiles))
        self.assertLessEqual(
            len(recompressed), orig_comp_len,
            "recompressed DexNav tileset overflows into the adjacent tilemap block",
        )


@pytest.mark.rom
class TestBuiltFrRomShowsFrenchHeaders(unittest.TestCase):
    """The shipped FR ROM must show French text in all four header rows."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba not built")
        cls.rom = bytearray(BUILT_FR_ROM.read_bytes())
        result = lz77_decompress(cls.rom, TILESET_OFFSET)
        assert result is not None
        cls.tiles_data, _ = result

    def test_headers_are_no_longer_english(self):
        for _row, first_tile, ntiles, _french, known_good in HEADERS:
            current = _tiles_hex(bytearray(self.tiles_data), first_tile, ntiles)
            self.assertNotEqual(
                current, known_good,
                f"tile {first_tile}: still shows the original English art",
            )

    def test_headers_render_expected_french_text(self):
        for _row, first_tile, ntiles, french, known_good in HEADERS:
            # Rebuild what the patch would draw starting from the known
            # English original, and require the live ROM to match exactly.
            base = bytearray(self.tiles_data)
            start = first_tile * 32
            base[start:start + len(known_good) // 2] = bytes.fromhex(known_good)
            _stamp_text(base, first_tile, ntiles, french)
            expected_hex = _tiles_hex(base, first_tile, ntiles)
            actual_hex = _tiles_hex(bytearray(self.tiles_data), first_tile, ntiles)
            self.assertEqual(
                actual_hex, expected_hex,
                f"tile {first_tile}: does not render {french!r}",
            )

    def test_no_ghost_text_below_headers(self):
        # Regression test for issue #90: the shipped ROM must not show a
        # leftover English letter-tail ghost under the shortened French labels.
        tiles = bytearray(self.tiles_data)
        all_ghost_tiles = [t for ids in GHOST_TILES.values() for t in ids]
        leftover = _isolated_ghost_pixels(tiles, all_ghost_tiles)
        self.assertFalse(
            leftover,
            f"built FR ROM still shows ghost pixels below DexNav headers: {leftover}",
        )


if __name__ == "__main__":
    unittest.main()
