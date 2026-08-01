"""PNG indexé <-> grille de pixels 4/8 bpp pour les sprites GBA.

Les indices de palette sont les données utiles : les couleurs RGB de la
palette embarquée ne servent qu'à la prévisualisation. L'écriture produit un
PNG indexé 4 bpp (16 couleurs) ou 8 bpp (256 couleurs). La lecture accepte les
deux profondeurs, y compris après une retouche dans un éditeur graphique.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import List, Tuple

from src.graphics.sprite_bmp import DEFAULT_PALETTE

Palette = List[Tuple[int, int, int]]
Grid = List[List[int]]

_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", checksum)
    )


def _validate_grid(width: int, height: int, grid: Grid, max_index: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if len(grid) != height or any(len(row) != width for row in grid):
        raise ValueError(f"grid must be {height}x{width}")
    if any(not 0 <= pixel <= max_index for row in grid for pixel in row):
        raise ValueError(f"pixel indices must be in the 0..{max_index} range")


def write_indexed_png(
    path: Path,
    width: int,
    height: int,
    grid: Grid,
    palette: Palette = DEFAULT_PALETTE,
) -> None:
    """Écrit *grid* dans un PNG indexé 4 ou 8 bpp."""
    if len(palette) not in (16, 256):
        raise ValueError("palette must have exactly 16 or 256 entries")
    bit_depth = 4 if len(palette) == 16 else 8
    _validate_grid(width, height, grid, len(palette) - 1)

    rows = bytearray()
    for row in grid:
        rows.append(0)  # filtre PNG « None »
        if bit_depth == 4:
            for x in range(0, width, 2):
                left = row[x]
                right = row[x + 1] if x + 1 < width else 0
                rows.append((left << 4) | right)
        else:
            rows.extend(row)

    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, 3, 0, 0, 0)
    plte = b"".join(bytes(rgb) for rgb in palette)
    path.write_bytes(
        _SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"PLTE", plte)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _chunk(b"IEND", b"")
    )


def _paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def _unfilter(raw: bytes, height: int, row_bytes: int) -> list[bytes]:
    expected = height * (row_bytes + 1)
    if len(raw) != expected:
        raise ValueError(
            f"invalid PNG pixel payload: expected {expected} bytes, got {len(raw)}"
        )

    rows: list[bytes] = []
    previous = bytes(row_bytes)
    cursor = 0
    # Indexed 4/8 bpp pixels use one byte as the PNG filter unit.
    bytes_per_pixel = 1
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        filtered = raw[cursor : cursor + row_bytes]
        cursor += row_bytes
        decoded = bytearray(row_bytes)

        for x, value in enumerate(filtered):
            left = decoded[x - bytes_per_pixel] if x >= bytes_per_pixel else 0
            up = previous[x]
            upper_left = previous[x - bytes_per_pixel] if x >= bytes_per_pixel else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                predictor = _paeth(left, up, upper_left)
            else:
                raise ValueError(f"unsupported PNG filter type {filter_type}")
            decoded[x] = (value + predictor) & 0xFF

        row = bytes(decoded)
        rows.append(row)
        previous = row
    return rows


def read_indexed_png(path: Path) -> tuple[int, int, Grid]:
    """Lit un PNG indexé 4/8 bpp et renvoie ``(largeur, hauteur, grille)``."""
    data = path.read_bytes()
    if not data.startswith(_SIGNATURE):
        raise ValueError(f"{path}: not a PNG file")

    cursor = len(_SIGNATURE)
    ihdr: bytes | None = None
    palette: bytes | None = None
    compressed = bytearray()
    saw_end = False

    while cursor + 12 <= len(data):
        length = struct.unpack(">I", data[cursor : cursor + 4])[0]
        kind = data[cursor + 4 : cursor + 8]
        payload_start = cursor + 8
        payload_end = payload_start + length
        crc_end = payload_end + 4
        if crc_end > len(data):
            raise ValueError(f"{path}: truncated PNG chunk")
        payload = data[payload_start:payload_end]
        expected_crc = struct.unpack(">I", data[payload_end:crc_end])[0]
        actual_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError(f"{path}: invalid PNG checksum for {kind!r}")

        if kind == b"IHDR":
            ihdr = payload
        elif kind == b"PLTE":
            palette = payload
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            saw_end = True
            break
        cursor = crc_end

    if ihdr is None or len(ihdr) != 13 or palette is None or not compressed or not saw_end:
        raise ValueError(f"{path}: incomplete indexed PNG")

    width, height, bit_depth, colour_type, compression, filtering, interlace = (
        struct.unpack(">IIBBBBB", ihdr)
    )
    if width <= 0 or height <= 0:
        raise ValueError(f"{path}: invalid PNG dimensions")
    if colour_type != 3 or bit_depth not in (4, 8):
        raise ValueError(f"{path}: expected a 4/8bpp indexed PNG")
    if compression != 0 or filtering != 0 or interlace != 0:
        raise ValueError(f"{path}: unsupported PNG encoding")
    if len(palette) < 3 or len(palette) % 3:
        raise ValueError(f"{path}: invalid PNG palette")
    palette_colours = len(palette) // 3
    if palette_colours > 256:
        raise ValueError(f"{path}: indexed PNG palette exceeds 256 colours")

    row_bytes = (width * bit_depth + 7) // 8
    try:
        raw = zlib.decompress(bytes(compressed))
    except zlib.error as exc:
        raise ValueError(f"{path}: invalid compressed PNG data") from exc
    packed_rows = _unfilter(raw, height, row_bytes)

    grid: Grid = []
    for packed in packed_rows:
        if bit_depth == 4:
            row = [
                (packed[x // 2] >> 4) if x % 2 == 0 else (packed[x // 2] & 0xF)
                for x in range(width)
            ]
        else:
            row = list(packed[:width])
        if any(pixel >= palette_colours for pixel in row):
            raise ValueError(f"{path}: pixel index exceeds the PNG palette")
        grid.append(row)
    return width, height, grid
