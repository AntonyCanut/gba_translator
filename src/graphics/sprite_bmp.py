#!/usr/bin/env python3
"""4/8bpp indexed BMP <-> GBA tile pixel-grid conversion.

UI sprites (buttons, status badges, …) are stored in the ROM as 4bpp
(16-color) tiles inside LZ77-compressed blocks. The palette index (0-15) *is*
the tile's pixel value — the ROM never stores RGB. This module reads/writes a
standard Windows indexed BMP whose raw pixel indices map 1:1 onto those tile
values, so any editor that preserves 16/256-color palettes can redraw a sprite
by hand. Les écrans 8 bpp, comme le titre, utilisent 256 couleurs.

The BMP's own embedded palette is cosmetic only — it exists so the image
looks reasonable while editing — and is never read back on insert. Only the
pixel indices round-trip. New exports should generally use the equivalent PNG
codec in ``sprite_png.py``; BMP remains supported for existing assets.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import List, Tuple

Palette = List[Tuple[int, int, int]]
Grid = List[List[int]]

# Cosmetic default palette (RGB24), shared by every extracted sprite so the
# exported .bmp previews in a similar way across sprites. Taken from the
# reference art supplied with ticket F-108.
DEFAULT_PALETTE: Palette = [
    (248, 24, 0), (0, 128, 208), (32, 200, 248), (112, 104, 160),
    (72, 152, 48), (16, 104, 64), (232, 8, 8), (16, 160, 16),
    (32, 32, 200), (72, 64, 88), (136, 0, 72), (88, 32, 48),
    (0, 112, 0), (248, 88, 64), (24, 168, 160), (240, 104, 48),
]

_FILE_HEADER_SIZE = 14
_INFO_HEADER_SIZE = 40
def write_indexed_bmp(path: Path, width: int, height: int, grid: Grid,
                       palette: Palette = DEFAULT_PALETTE) -> None:
    """Write *grid* as a 4/8bpp BMP selected from the palette length.

    ``grid[0]`` is the top row, ``grid[y][0]`` the leftmost pixel — BMP's
    bottom-up row order is handled internally.
    """
    if len(palette) not in (16, 256):
        raise ValueError("palette must have exactly 16 or 256 entries")
    if len(grid) != height or any(len(row) != width for row in grid):
        raise ValueError(f"grid must be {height}x{width}")
    max_index = len(palette) - 1
    if any(pixel < 0 or pixel > max_index for row in grid for pixel in row):
        raise ValueError(f"BMP pixel indices must be in 0..{max_index}")

    bits_per_pixel = 4 if len(palette) == 16 else 8
    row_bytes = (width * bits_per_pixel + 7) // 8
    stride = (row_bytes + 3) & ~3
    img_size = stride * height
    palette_size = len(palette) * 4
    off_bits = _FILE_HEADER_SIZE + _INFO_HEADER_SIZE + palette_size
    file_size = off_bits + img_size

    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, off_bits)
    info_header = struct.pack(
        "<IiiHHIIiiII",
        _INFO_HEADER_SIZE, width, height, 1, bits_per_pixel, 0,
        img_size, 2835, 2835, len(palette), 0,
    )
    pal_bytes = b"".join(
        struct.pack("<BBBB", b, g, r, 0) for (r, g, b) in palette
    )

    body = bytearray(img_size)
    for y in range(height):
        src_row = grid[height - 1 - y]  # BMP stores rows bottom-up
        base = y * stride
        if bits_per_pixel == 8:
            body[base:base + width] = bytes(src_row)
        else:
            for x in range(width):
                val = src_row[x]
                byte_off = base + x // 2
                if x % 2 == 0:
                    body[byte_off] |= val << 4  # BMP: high nibble = left pixel
                else:
                    body[byte_off] |= val

    path.write_bytes(file_header + info_header + pal_bytes + bytes(body))


def read_indexed_bmp(path: Path) -> Tuple[int, int, Grid]:
    """Return ``(width, height, grid)`` for a 4/8bpp indexed BMP.

    The embedded palette is ignored — only pixel indices are returned.
    """
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError(f"{path}: not a BMP file")

    off_bits = struct.unpack("<I", data[10:14])[0]
    width, raw_height = struct.unpack("<ii", data[18:26])
    bpp = struct.unpack("<H", data[28:30])[0]
    compression = struct.unpack("<I", data[30:34])[0]
    if bpp not in (4, 8):
        raise ValueError(f"{path}: expected a 4/8bpp indexed BMP, got {bpp}bpp")
    if compression != 0:
        raise ValueError(f"{path}: compressed BMPs are not supported")

    bottom_up = raw_height > 0
    height = abs(raw_height)
    row_bytes = (width * bpp + 7) // 8
    stride = (row_bytes + 3) & ~3

    grid: Grid = [[0] * width for _ in range(height)]
    for y in range(height):
        base = off_bits + y * stride
        dest_row = grid[height - 1 - y] if bottom_up else grid[y]
        if bpp == 8:
            dest_row[:] = data[base:base + width]
        else:
            for x in range(width):
                byte = data[base + x // 2]
                dest_row[x] = (byte >> 4) if x % 2 == 0 else (byte & 0xF)
    return width, height, grid
