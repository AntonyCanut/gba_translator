#!/usr/bin/env python3
"""Extract/insert a rectangular tile sprite from/into an LZ77-compressed ROM
block (ticket F-108).

This is the ROM-facing half of the sprite pipeline: it converts between a
flat run of 4bpp 8x8 tiles (as stored inside an LZ77 block) and the pixel
grid consumed by ``sprite_bmp``. Recompression follows the same
padding-tolerant overflow rule already used by ``status_badges.py`` /
``hp_labels.py``: a recompressed block may grow past the original compressed
length as long as the extra bytes it would overwrite are 0x00/0xFF padding.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import (  # noqa: E402
    lz77_compress,
    lz77_decompress,
    pixels_to_tile,
    tile_to_pixels,
)

TILE_BYTES = 32  # bytes per 4bpp 8x8 tile
TILE_PX = 8

Grid = List[List[int]]


def tiles_to_grid(tiles: bytes, tiles_wide: int, tiles_tall: int) -> Grid:
    """Arrange a flat run of tiles (row-major, ``tiles_wide`` per row) into a
    single pixel grid of size ``tiles_tall*8`` rows x ``tiles_wide*8`` cols."""
    width = tiles_wide * TILE_PX
    height = tiles_tall * TILE_PX
    grid: Grid = [[0] * width for _ in range(height)]
    for ty in range(tiles_tall):
        for tx in range(tiles_wide):
            idx = ty * tiles_wide + tx
            tile_bytes = tiles[idx * TILE_BYTES:(idx + 1) * TILE_BYTES]
            pixels = tile_to_pixels(tile_bytes)
            for r in range(TILE_PX):
                row = grid[ty * TILE_PX + r]
                base = r * TILE_PX
                row[tx * TILE_PX:tx * TILE_PX + TILE_PX] = pixels[base:base + TILE_PX]
    return grid


def grid_to_tiles(grid: Grid, tiles_wide: int, tiles_tall: int) -> bytes:
    """Inverse of ``tiles_to_grid``."""
    out = bytearray()
    for ty in range(tiles_tall):
        for tx in range(tiles_wide):
            pixels: List[int] = []
            for r in range(TILE_PX):
                row = grid[ty * TILE_PX + r]
                pixels.extend(row[tx * TILE_PX:tx * TILE_PX + TILE_PX])
            out.extend(pixels_to_tile(pixels))
    return bytes(out)


def extract_block(rom: bytes, offset: int, tiles_wide: int, tiles_tall: int,
                   compressed: bool = True) -> Tuple[Grid, int, int]:
    """Return the pixel grid for the sprite block at *offset*.

    When *compressed* is true (the default) the block is an LZ77-compressed
    blob (see ``insert_block``). Some small OBJ tilesets — e.g. the naming
    keyboard's help panel — are instead stored as a flat run of raw 4bpp
    tiles with no compression; pass ``compressed=False`` for those.

    Returns ``(grid, decompressed_len, compressed_len)``. Raises ``ValueError``
    if the block can't be decompressed or is smaller than the sprite needs.
    """
    needed = tiles_wide * tiles_tall * TILE_BYTES
    if not compressed:
        if offset + needed > len(rom):
            raise ValueError(f"0x{offset:08X}: raw block overflows ROM")
        raw = rom[offset:offset + needed]
        grid = tiles_to_grid(raw, tiles_wide, tiles_tall)
        return grid, needed, needed

    result = lz77_decompress(rom, offset)
    if result is None:
        raise ValueError(f"0x{offset:08X}: failed to decompress LZ77 block")
    decompressed, comp_len = result
    if len(decompressed) < needed:
        raise ValueError(
            f"0x{offset:08X}: decompressed size {len(decompressed)} < needed {needed}"
        )
    grid = tiles_to_grid(decompressed[:needed], tiles_wide, tiles_tall)
    return grid, len(decompressed), comp_len


def insert_block(rom: bytearray, offset: int, grid: Grid,
                  tiles_wide: int, tiles_tall: int,
                  compressed: bool = True) -> None:
    """Re-encode *grid* into tiles and write it back at *offset*.

    When *compressed* is true (the default), recompress with LZ77; raises
    ``ValueError`` if the block can't be decompressed, is too small, or the
    recompressed result would overwrite non-padding bytes. When false, the
    tiles are written back raw (fixed size, no compression) — see
    ``extract_block``.
    """
    needed = tiles_wide * tiles_tall * TILE_BYTES
    if not compressed:
        if offset + needed > len(rom):
            raise ValueError(f"0x{offset:08X}: raw block overflows ROM")
        rom[offset:offset + needed] = grid_to_tiles(grid, tiles_wide, tiles_tall)
        return

    result = lz77_decompress(rom, offset)
    if result is None:
        raise ValueError(f"0x{offset:08X}: failed to decompress LZ77 block")
    decompressed, comp_len = result
    if len(decompressed) < needed:
        raise ValueError(
            f"0x{offset:08X}: decompressed size {len(decompressed)} < needed {needed}"
        )

    tiles = bytearray(decompressed)
    tiles[:needed] = grid_to_tiles(grid, tiles_wide, tiles_tall)
    compressed_out = lz77_compress(bytes(tiles))

    if offset + len(compressed_out) > len(rom):
        raise ValueError(f"0x{offset:08X}: recompressed block overflows ROM")
    if len(compressed_out) > comp_len:
        extra = rom[offset + comp_len:offset + len(compressed_out)]
        if any(b not in (0x00, 0xFF) for b in extra):
            raise ValueError(
                f"0x{offset:08X}: recompressed ({len(compressed_out)}) > original "
                f"({comp_len}) and tail is non-padding"
            )
    rom[offset:offset + len(compressed_out)] = compressed_out
