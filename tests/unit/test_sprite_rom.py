"""Unit tests for LZ77 tile-block <-> pixel-grid extract/insert (F-108)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from languages.fr.patches.font import lz77_compress, lz77_decompress
from src.graphics.sprite_rom import (
    TILE_BYTES,
    extract_block,
    grid_to_tiles,
    insert_block,
    tiles_to_grid,
)


def _make_rom_with_block(tiles: bytes, pad_after: int = 16) -> tuple:
    """Build a minimal ROM buffer holding a single LZ77 block at offset 0."""
    compressed = lz77_compress(tiles)
    rom = bytearray(compressed) + b"\xff" * pad_after
    return rom, 0, len(compressed)


def test_tiles_to_grid_and_back_round_trip():
    tiles_wide, tiles_tall = 2, 3
    n_tiles = tiles_wide * tiles_tall
    # Distinct byte pattern per tile so a transposition bug would be caught.
    tiles = bytes((t * 7 + i) & 0xFF for t in range(n_tiles) for i in range(TILE_BYTES))

    grid = tiles_to_grid(tiles, tiles_wide, tiles_tall)
    assert len(grid) == tiles_tall * 8
    assert len(grid[0]) == tiles_wide * 8

    rebuilt = grid_to_tiles(grid, tiles_wide, tiles_tall)
    assert rebuilt == tiles


def test_extract_block_decodes_known_tiles():
    tiles_wide, tiles_tall = 1, 1
    # A single tile, all pixel index 5 (nibble 0x55 repeated).
    tiles = bytes([0x55] * TILE_BYTES)
    rom, offset, _ = _make_rom_with_block(tiles)

    grid, dec_len, comp_len = extract_block(bytes(rom), offset, tiles_wide, tiles_tall)
    assert dec_len == TILE_BYTES
    assert all(px == 5 for row in grid for px in row)


def test_extract_block_rejects_undersized_block():
    tiles = bytes([0x00] * TILE_BYTES)  # only 1 tile available
    rom, offset, _ = _make_rom_with_block(tiles)
    with pytest.raises(ValueError):
        extract_block(bytes(rom), offset, tiles_wide=2, tiles_tall=1)  # needs 2 tiles


def test_insert_block_round_trip():
    tiles_wide, tiles_tall = 2, 2
    n_tiles = tiles_wide * tiles_tall
    original = bytes((t * 3 + i) & 0xFF for t in range(n_tiles) for i in range(TILE_BYTES))
    rom, offset, comp_len = _make_rom_with_block(original, pad_after=64)

    grid = tiles_to_grid(original, tiles_wide, tiles_tall)
    # Flip every pixel to a different, deterministic index.
    new_grid = [[(px + 3) % 16 for px in row] for row in grid]

    insert_block(rom, offset, new_grid, tiles_wide, tiles_tall)

    result = lz77_decompress(bytes(rom), offset)
    assert result is not None
    decompressed, _ = result
    needed = tiles_wide * tiles_tall * TILE_BYTES
    round_tripped_grid = tiles_to_grid(decompressed[:needed], tiles_wide, tiles_tall)
    assert round_tripped_grid == new_grid


def test_insert_block_rejects_overflow_of_non_padding_tail():
    # A block with non-padding bytes right after it that recompresses to
    # something larger must be rejected rather than overwrite live data.
    tiles_wide, tiles_tall = 1, 1
    tiles = bytes([0x00] * TILE_BYTES)  # highly compressible -> tiny compressed size
    rom, offset, comp_len = _make_rom_with_block(tiles, pad_after=0)
    rom = bytearray(rom[:offset + comp_len]) + b"\xab" * 64  # live (non-padding) tail

    # Fully random-looking grid compresses poorly -> almost certainly grows.
    noisy_grid = [[(x * 13 + y * 7) % 16 for x in range(8)] for y in range(8)]

    with pytest.raises(ValueError):
        insert_block(rom, offset, noisy_grid, tiles_wide, tiles_tall)
