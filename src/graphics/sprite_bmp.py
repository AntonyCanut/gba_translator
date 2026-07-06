#!/usr/bin/env python3
"""4bpp indexed BMP <-> GBA tile pixel-grid conversion (ticket F-108).

UI sprites (buttons, status badges, …) are stored in the ROM as 4bpp
(16-color) tiles inside LZ77-compressed blocks. The palette index (0-15) *is*
the tile's pixel value — the ROM never stores RGB. This module reads/writes a
standard Windows 4bpp indexed BMP whose raw pixel indices map 1:1 onto those
tile values, so any editor that can open/save 16-color indexed BMPs (Aseprite,
GIMP, Usenti, …) can be used to redraw a sprite by hand.

The BMP's own embedded palette is cosmetic only — it exists so the image
looks reasonable while editing — and is never read back on insert. Only the
pixel indices round-trip.
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
_PALETTE_SIZE = 16 * 4  # 16 entries x BGRA


def write_indexed_bmp(path: Path, width: int, height: int, grid: Grid,
                       palette: Palette = DEFAULT_PALETTE) -> None:
    """Write *grid* (height rows x width cols, values 0-15) as a 4bpp BMP.

    ``grid[0]`` is the top row, ``grid[y][0]`` the leftmost pixel — BMP's
    bottom-up row order is handled internally.
    """
    if len(palette) != 16:
        raise ValueError("palette must have exactly 16 entries")
    if len(grid) != height or any(len(row) != width for row in grid):
        raise ValueError(f"grid must be {height}x{width}")

    row_bytes = (width + 1) // 2
    stride = (row_bytes + 3) & ~3
    img_size = stride * height
    off_bits = _FILE_HEADER_SIZE + _INFO_HEADER_SIZE + _PALETTE_SIZE
    file_size = off_bits + img_size

    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, off_bits)
    info_header = struct.pack(
        "<IiiHHIIiiII",
        _INFO_HEADER_SIZE, width, height, 1, 4, 0,
        img_size, 2835, 2835, 16, 0,
    )
    pal_bytes = b"".join(
        struct.pack("<BBBB", b, g, r, 0) for (r, g, b) in palette
    )

    body = bytearray(img_size)
    for y in range(height):
        src_row = grid[height - 1 - y]  # BMP stores rows bottom-up
        base = y * stride
        for x in range(width):
            val = src_row[x] & 0xF
            byte_off = base + x // 2
            if x % 2 == 0:
                body[byte_off] |= val << 4  # BMP: high nibble = left pixel
            else:
                body[byte_off] |= val

    path.write_bytes(file_header + info_header + pal_bytes + bytes(body))


def read_indexed_bmp(path: Path) -> Tuple[int, int, Grid]:
    """Return ``(width, height, grid)`` for a 4bpp indexed BMP.

    The embedded palette is ignored — only pixel indices are returned.
    """
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError(f"{path}: not a BMP file")

    off_bits = struct.unpack("<I", data[10:14])[0]
    width, raw_height = struct.unpack("<ii", data[18:26])
    bpp = struct.unpack("<H", data[28:30])[0]
    compression = struct.unpack("<I", data[30:34])[0]
    if bpp != 4:
        raise ValueError(f"{path}: expected a 4bpp indexed BMP, got {bpp}bpp")
    if compression != 0:
        raise ValueError(f"{path}: compressed BMPs are not supported")

    bottom_up = raw_height > 0
    height = abs(raw_height)
    row_bytes = (width + 1) // 2
    stride = (row_bytes + 3) & ~3

    grid: Grid = [[0] * width for _ in range(height)]
    for y in range(height):
        base = off_bits + y * stride
        dest_row = grid[height - 1 - y] if bottom_up else grid[y]
        for x in range(width):
            byte = data[base + x // 2]
            dest_row[x] = (byte >> 4) if x % 2 == 0 else (byte & 0xF)
    return width, height, grid
