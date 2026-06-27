import struct
import unittest
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.patch_version_fr import (
    _CHAR_PIXELS,
    _VER_FG,
    _VER_BG,
    _VER_GRID_COLS,
    _VER_GRID_ROWS,
    _VER_TILE_START,
    _NFS_TILESET_PTR_OFF,
    _lz77_compress,
    _lz77_decompress,
    _compute_checksum,
    _read_gba_ptr,
    _render_version_band,
    _blit_band_to_tiles,
    version_string,
    patch_version,
    patch_intro_version,
)

EN_ROM = Path(__file__).parent.parent / "input" / "roms" / "englishrom.gba"


# ---------------------------------------------------------------------------
# LZ77 round-trip
# ---------------------------------------------------------------------------

class TestLz77(unittest.TestCase):
    def test_roundtrip_small(self):
        data = bytes(range(256)) * 4
        compressed = _lz77_compress(data)
        result = _lz77_decompress(compressed, 0)
        self.assertIsNotNone(result)
        decompressed, _ = result
        self.assertEqual(decompressed, data)

    def test_roundtrip_repeated(self):
        data = b"\xAB\xCD" * 500
        compressed = _lz77_compress(data)
        result = _lz77_decompress(compressed, 0)
        self.assertIsNotNone(result)
        decompressed, _ = result
        self.assertEqual(decompressed, data)

    def test_magic_byte(self):
        data = b"\x00" * 32
        compressed = _lz77_compress(data)
        self.assertEqual(compressed[0], 0x10)

    def test_none_on_bad_magic(self):
        self.assertIsNone(_lz77_decompress(b"\x00" * 16, 0))


# ---------------------------------------------------------------------------
# Character pixel map
# ---------------------------------------------------------------------------

class TestCharPixels(unittest.TestCase):
    def test_all_chars_have_5_rows(self):
        for ch, rows in _CHAR_PIXELS.items():
            self.assertEqual(len(rows), 5, f"char '{ch}' does not have 5 rows")

    def test_all_rows_have_4_cols(self):
        for ch, rows in _CHAR_PIXELS.items():
            for ri, row in enumerate(rows):
                self.assertEqual(len(row), 4,
                                 f"char '{ch}' row {ri} does not have 4 columns")

    def test_all_values_are_0_or_1(self):
        for ch, rows in _CHAR_PIXELS.items():
            for ri, row in enumerate(rows):
                for ci, v in enumerate(row):
                    self.assertIn(v, (0, 1), f"char '{ch}'[{ri}][{ci}] = {v}")

    def test_required_chars_present(self):
        # Every character that can appear in "FR.2.0.<build_number>".
        for ch in "FR.0123456789 ":
            self.assertIn(ch, _CHAR_PIXELS, f"missing char '{ch}'")

    def test_language_prefix_chars_present(self):
        # The other buildable language prefixes (IT, DE) need their letters too.
        for ch in "ITDE":
            self.assertIn(ch, _CHAR_PIXELS, f"missing language prefix char '{ch}'")

    def test_glyph_bitmaps_are_unique(self):
        # The blind OCR decoder relies on every non-space glyph being a distinct
        # bitmap; a collision would make IT/DE/FR misread.
        seen = {}
        for ch, rows in _CHAR_PIXELS.items():
            if ch == " ":
                continue
            key = tuple(tuple(r) for r in rows)
            self.assertNotIn(
                key, seen, f"glyph '{ch}' collides with '{seen.get(key)}'"
            )
            seen[key] = ch


# ---------------------------------------------------------------------------
# version_string
# ---------------------------------------------------------------------------

class TestVersionString(unittest.TestCase):
    def test_format(self):
        self.assertEqual(version_string(5), "FR.2.0.5")
        self.assertEqual(version_string(42), "FR.2.0.42")
        self.assertEqual(version_string(0), "FR.2.0.0")

    def test_default_is_french(self):
        # Omitting lang_code must keep the proven FR behaviour byte-for-byte.
        self.assertEqual(version_string(42), version_string(42, "fr"))

    def test_language_prefix(self):
        self.assertEqual(version_string(5, "it"), "IT.2.0.5")
        self.assertEqual(version_string(42, "de"), "DE.2.0.42")
        # Codes are upper-cased so the descriptor's lowercase code works.
        self.assertEqual(version_string(7, "IT"), "IT.2.0.7")

    def test_fits_band_width(self):
        # The band is _VER_GRID_COLS * 8 px wide; 4 px per glyph.
        band_px = _VER_GRID_COLS * 8
        for build in (1, 99, 999, 9999):
            for lang in ("fr", "it", "de"):
                self.assertLessEqual(
                    len(version_string(build, lang)) * 4, band_px,
                    f"build {build}/{lang} version string overflows band")


# ---------------------------------------------------------------------------
# _render_version_band / _blit_band_to_tiles
# ---------------------------------------------------------------------------

class TestRenderBand(unittest.TestCase):
    def test_band_dimensions(self):
        band = _render_version_band("FR.2.0.5")
        self.assertEqual(len(band), _VER_GRID_ROWS * 8)
        self.assertEqual(len(band[0]), _VER_GRID_COLS * 8)

    def test_background_filled_with_bg_index(self):
        # A space-only string leaves the whole band at the background index.
        band = _render_version_band(" ")
        self.assertTrue(all(p == _VER_BG for row in band for p in row))

    def test_text_paints_fg_pixels(self):
        band = _render_version_band("FR.2.0.5")
        fg_pixels = sum(1 for row in band for p in row if p == _VER_FG)
        self.assertGreater(fg_pixels, 0)
        # Only the two configured indices should ever appear.
        self.assertTrue(all(p in (_VER_FG, _VER_BG) for row in band for p in row))

    def test_blit_roundtrips_through_4bpp_tiles(self):
        band = _render_version_band("FR.2.0.5")
        n_tiles = _VER_GRID_COLS * _VER_GRID_ROWS
        tileset = bytearray(32 * (_VER_TILE_START + n_tiles))
        _blit_band_to_tiles(tileset, band)
        # Decode the version tiles back and compare to the band.
        for ty in range(_VER_GRID_ROWS):
            for tx in range(_VER_GRID_COLS):
                tile = _VER_TILE_START + ty * _VER_GRID_COLS + tx
                base = tile * 32
                for py in range(8):
                    for px in range(8):
                        b = tileset[base + py * 4 + (px >> 1)]
                        idx = (b & 0xF) if (px & 1) == 0 else (b >> 4)
                        self.assertEqual(idx, band[ty * 8 + py][tx * 8 + px])


# ---------------------------------------------------------------------------
# patch_version (header byte)
# ---------------------------------------------------------------------------

class TestPatchVersion(unittest.TestCase):
    def _minimal_rom(self, version_byte: int = 0x00) -> bytearray:
        rom = bytearray(0x100)
        rom[0xB2] = 0x96   # GBA magic
        rom[0xBC] = version_byte
        rom[0xBD] = _compute_checksum(rom)
        return rom

    def test_changes_version_byte(self):
        rom = self._minimal_rom(0x00)
        changed = patch_version(rom, 42)
        self.assertTrue(changed)
        self.assertEqual(rom[0xBC], 42 & 0xFF)

    def test_updates_checksum(self):
        rom = self._minimal_rom(0x00)
        patch_version(rom, 42)
        self.assertEqual(rom[0xBD], _compute_checksum(rom))

    def test_truncates_to_byte(self):
        rom = self._minimal_rom(0x00)
        patch_version(rom, 300)
        self.assertEqual(rom[0xBC], 300 & 0xFF)

    def test_idempotent_returns_false(self):
        rom = self._minimal_rom(0x2A)
        changed = patch_version(rom, 42)
        self.assertFalse(changed)
        self.assertEqual(rom[0xBC], 0x2A)


# ---------------------------------------------------------------------------
# patch_intro_version — requires EN ROM
# ---------------------------------------------------------------------------

@pytest.mark.rom
class TestPatchIntroVersion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not EN_ROM.exists():
            pytest.skip("englishrom.gba not found")
        cls.rom_data = EN_ROM.read_bytes()

    def _patched(self, build_number: int) -> bytearray:
        data = bytearray(self.rom_data)
        patch_intro_version(data, build_number)
        return data

    def test_returns_true(self):
        data = bytearray(self.rom_data)
        self.assertTrue(patch_intro_version(data, 42))

    def test_tileset_pointer_changes(self):
        orig = struct.unpack_from("<I", self.rom_data, _NFS_TILESET_PTR_OFF)[0]
        data = self._patched(42)
        new = struct.unpack_from("<I", data, _NFS_TILESET_PTR_OFF)[0]
        self.assertNotEqual(orig, new)

    def test_new_tileset_decompresses_to_same_size(self):
        orig_off = _read_gba_ptr(bytearray(self.rom_data), _NFS_TILESET_PTR_OFF)
        orig_ts, _ = _lz77_decompress(self.rom_data, orig_off)
        data = self._patched(42)
        new_off = _read_gba_ptr(data, _NFS_TILESET_PTR_OFF)
        new_ts, _ = _lz77_decompress(data, new_off)
        self.assertEqual(len(new_ts), len(orig_ts))

    def test_only_version_tiles_change(self):
        orig_off = _read_gba_ptr(bytearray(self.rom_data), _NFS_TILESET_PTR_OFF)
        orig_ts, _ = _lz77_decompress(self.rom_data, orig_off)
        data = self._patched(42)
        new_off = _read_gba_ptr(data, _NFS_TILESET_PTR_OFF)
        new_ts, _ = _lz77_decompress(data, new_off)
        n_tiles = _VER_GRID_COLS * _VER_GRID_ROWS
        lo = _VER_TILE_START * 32
        hi = (_VER_TILE_START + n_tiles) * 32
        # Everything outside the version band is untouched.
        self.assertEqual(orig_ts[:lo], new_ts[:lo])
        self.assertEqual(orig_ts[hi:], new_ts[hi:])
        # The version band itself changed.
        self.assertNotEqual(orig_ts[lo:hi], new_ts[lo:hi])

    def test_version_band_matches_render(self):
        data = self._patched(7)
        new_off = _read_gba_ptr(data, _NFS_TILESET_PTR_OFF)
        new_ts, _ = _lz77_decompress(data, new_off)
        expected = bytearray(len(new_ts))
        _blit_band_to_tiles(expected, _render_version_band(version_string(7)))
        n_tiles = _VER_GRID_COLS * _VER_GRID_ROWS
        lo = _VER_TILE_START * 32
        hi = (_VER_TILE_START + n_tiles) * 32
        self.assertEqual(new_ts[lo:hi], bytes(expected[lo:hi]))

    def test_different_build_numbers_differ(self):
        a = self._patched(5)
        b = self._patched(8)
        a_ts, _ = _lz77_decompress(a, _read_gba_ptr(a, _NFS_TILESET_PTR_OFF))
        b_ts, _ = _lz77_decompress(b, _read_gba_ptr(b, _NFS_TILESET_PTR_OFF))
        self.assertNotEqual(a_ts, b_ts)


if __name__ == "__main__":
    unittest.main()
