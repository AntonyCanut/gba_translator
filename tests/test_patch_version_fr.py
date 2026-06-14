import struct
import unittest
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.patch_version_fr import (
    _CHAR_PIXELS,
    _BG,
    _DC,
    _FG,
    _TILESET_PTR_OFF,
    _TILEMAP_PTR_OFF,
    _lz77_compress,
    _lz77_decompress,
    _make_char_tile,
    _compute_checksum,
    patch_version,
    patch_title_screen_version,
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
                    self.assertIn(v, (0, 1),
                                  f"char '{ch}'[{ri}][{ci}] = {v}")

    def test_required_chars_present(self):
        for ch in "FR.0123456789 ":
            self.assertIn(ch, _CHAR_PIXELS, f"missing char '{ch}'")


# ---------------------------------------------------------------------------
# _make_char_tile
# ---------------------------------------------------------------------------

class TestMakeCharTile(unittest.TestCase):
    def _decode_tile(self, tile: bytes) -> list[list[int]]:
        """Decode a 4bpp tile into an 8×8 list of palette indices."""
        rows = []
        for r in range(8):
            row = []
            for c in range(4):
                b = tile[r * 4 + c]
                row.append(b & 0xF)
                row.append((b >> 4) & 0xF)
            rows.append(row)
        return rows

    def test_tile_is_32_bytes(self):
        tile = _make_char_tile('F', 'R')
        self.assertEqual(len(tile), 32)

    def test_row0_is_blank(self):
        tile = _make_char_tile('F', 'R')
        grid = self._decode_tile(tile)
        self.assertTrue(all(p == _BG for p in grid[0]))

    def test_row7_is_blank(self):
        tile = _make_char_tile('F', 'R')
        grid = self._decode_tile(tile)
        self.assertTrue(all(p == _BG for p in grid[7]))

    def test_row6_is_decorative(self):
        tile = _make_char_tile('F', 'R')
        grid = self._decode_tile(tile)
        self.assertTrue(all(p == _DC for p in grid[6]))

    def test_space_char_is_all_background(self):
        tile = _make_char_tile(' ', ' ')
        grid = self._decode_tile(tile)
        for r in range(5):
            # Rows 1-5 should be all _BG for two spaces
            self.assertTrue(all(p == _BG for p in grid[r + 1]))

    def test_left_char_maps_to_cols_0_3(self):
        """Verify 'F' appears in cols 0-3 (left half of the tile)."""
        tile = _make_char_tile('F', ' ')
        grid = self._decode_tile(tile)
        expected = _CHAR_PIXELS['F']
        for ri, row in enumerate(expected, 1):
            for ci, pixel in enumerate(row):
                pal = _FG if pixel else _BG
                self.assertEqual(grid[ri][ci], pal,
                                 f"'F' pixel mismatch at row {ri} col {ci}")
        # Right half (space) must be all background in content rows
        for ri in range(1, 6):
            for ci in range(4, 8):
                self.assertEqual(grid[ri][ci], _BG)

    def test_right_char_maps_to_cols_4_7(self):
        """Verify 'R' appears in cols 4-7 (right half of the tile)."""
        tile = _make_char_tile(' ', 'R')
        grid = self._decode_tile(tile)
        expected = _CHAR_PIXELS['R']
        for ri, row in enumerate(expected, 1):
            for ci, pixel in enumerate(row):
                pal = _FG if pixel else _BG
                self.assertEqual(grid[ri][ci + 4], pal,
                                 f"'R' pixel mismatch at row {ri} col {ci + 4}")


# ---------------------------------------------------------------------------
# patch_version (header byte)
# ---------------------------------------------------------------------------

class TestPatchVersion(unittest.TestCase):
    def _minimal_rom(self, version_byte: int = 0x00) -> bytearray:
        rom = bytearray(0x100)
        rom[0xB2] = 0x96   # GBA magic
        rom[0xBC] = version_byte
        # pre-seed a valid checksum
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
# patch_title_screen_version — requires EN ROM
# ---------------------------------------------------------------------------

@pytest.mark.rom
class TestPatchTitleScreenVersion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not EN_ROM.exists():
            pytest.skip("englishrom.gba not found")
        cls.rom_data = EN_ROM.read_bytes()

    def _patched(self, build_number: int) -> bytearray:
        data = bytearray(self.rom_data)
        patch_title_screen_version(data, build_number)
        return data

    def test_returns_true(self):
        data = bytearray(self.rom_data)
        result = patch_title_screen_version(data, 42)
        self.assertTrue(result)

    def test_tileset_pointer_changes(self):
        orig_ts_off = struct.unpack_from("<I", self.rom_data, _TILESET_PTR_OFF)[0]
        data = self._patched(42)
        new_ts_off = struct.unpack_from("<I", data, _TILESET_PTR_OFF)[0]
        self.assertNotEqual(orig_ts_off, new_ts_off)

    def test_tilemap_pointer_changes(self):
        orig_tm_off = struct.unpack_from("<I", self.rom_data, _TILEMAP_PTR_OFF)[0]
        data = self._patched(42)
        new_tm_off = struct.unpack_from("<I", data, _TILEMAP_PTR_OFF)[0]
        self.assertNotEqual(orig_tm_off, new_tm_off)

    def test_new_tileset_decompresses(self):
        from scripts.patch_version_fr import _read_gba_ptr
        data = self._patched(42)
        ts_off = _read_gba_ptr(data, _TILESET_PTR_OFF)
        result = _lz77_decompress(data, ts_off)
        self.assertIsNotNone(result)
        tileset, _ = result
        self.assertEqual(len(tileset) % 32, 0)

    def test_new_tileset_has_more_tiles(self):
        from scripts.patch_version_fr import _read_gba_ptr
        data = self._patched(42)
        ts_off = _read_gba_ptr(data, _TILESET_PTR_OFF)
        tileset, _ = _lz77_decompress(data, ts_off)
        # 138 original + new character tiles
        self.assertGreater(len(tileset) // 32, 138)

    def test_new_tilemap_decompresses_to_correct_size(self):
        from scripts.patch_version_fr import _read_gba_ptr
        data = self._patched(42)
        tm_off = _read_gba_ptr(data, _TILEMAP_PTR_OFF)
        result = _lz77_decompress(data, tm_off)
        self.assertIsNotNone(result)
        tilemap, _ = result
        self.assertEqual(len(tilemap), 32 * 20 * 2)  # 1280 bytes

    def test_version_row2_has_new_tile_indices(self):
        from scripts.patch_version_fr import _read_gba_ptr
        data = self._patched(42)
        ts_off = _read_gba_ptr(data, _TILESET_PTR_OFF)
        tileset, _ = _lz77_decompress(data, ts_off)
        tm_off = _read_gba_ptr(data, _TILEMAP_PTR_OFF)
        tilemap, _ = _lz77_decompress(data, tm_off)
        orig_tile_count = 138  # EN tileset tile count
        found_new_tile = False
        for col in range(10, 20):
            entry = struct.unpack_from("<H", tilemap, (2 * 32 + col) * 2)[0]
            tile_idx = entry & 0x3FF
            if tile_idx >= orig_tile_count:
                found_new_tile = True
                break
        self.assertTrue(found_new_tile, "No new tile indices found in row 2 version area")

    def test_different_build_numbers_produce_different_tiles(self):
        from scripts.patch_version_fr import _read_gba_ptr
        data1 = self._patched(5)
        data2 = self._patched(42)
        ts_off1 = _read_gba_ptr(data1, _TILESET_PTR_OFF)
        ts_off2 = _read_gba_ptr(data2, _TILESET_PTR_OFF)
        ts1, _ = _lz77_decompress(data1, ts_off1)
        ts2, _ = _lz77_decompress(data2, ts_off2)
        # The new tiles should differ between build #5 and build #42
        self.assertNotEqual(ts1, ts2)

    def test_version_string_fr_2_0(self):
        """Every build should start the version string with 'FR.2.0.'"""
        from scripts.patch_version_fr import _read_gba_ptr
        for build in (1, 10, 99, 1000):
            data = self._patched(build)
            ts_off = _read_gba_ptr(data, _TILESET_PTR_OFF)
            ts, _ = _lz77_decompress(data, ts_off)
            tm_off = _read_gba_ptr(data, _TILEMAP_PTR_OFF)
            tm, _ = _lz77_decompress(data, tm_off)
            # First new tile (index 138) must represent 'F'+'R'
            first_new_tile = ts[138 * 32:139 * 32]
            fr_tile = _make_char_tile('F', 'R')
            self.assertEqual(first_new_tile, fr_tile,
                             f"build {build}: tile 138 is not 'FR'")


if __name__ == "__main__":
    unittest.main()
