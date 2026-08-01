"""Tests du format PNG indexé utilisé pour éditer les sprites GBA."""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.graphics.sprite_bmp import DEFAULT_PALETTE
from src.graphics.sprite_image import (
    read_indexed_image,
    variant_path,
    write_indexed_image,
)
from src.graphics.sprite_png import read_indexed_png, write_indexed_png


def _checkerboard(width: int, height: int) -> list[list[int]]:
    return [[(x + 3 * y) % 16 for x in range(width)] for y in range(height)]


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _write_8bpp_indexed_png(path: Path, grid: list[list[int]]) -> None:
    """Simule un éditeur qui sauvegarde une palette 16 couleurs en 8 bpp."""
    width, height = len(grid[0]), len(grid)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)
    palette = b"".join(bytes(rgb) for rgb in DEFAULT_PALETTE)
    scanlines = b"".join(b"\x00" + bytes(row) for row in grid)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"PLTE", palette)
        + _chunk(b"IDAT", zlib.compress(scanlines))
        + _chunk(b"IEND", b"")
    )


def test_png_round_trip_preserves_palette_indices(tmp_path):
    width, height = 13, 5
    grid = _checkerboard(width, height)
    out = tmp_path / "sprite.png"

    write_indexed_png(out, width, height, grid)

    assert read_indexed_png(out) == (width, height, grid)


def test_png_round_trip_preserves_8bpp_palette_indices(tmp_path):
    # Arrange
    palette = [(index, index, index) for index in range(256)]
    grid = [[0x00, 0x10, 0x80, 0xF3]]
    out = tmp_path / "title-screen.png"

    # Act
    write_indexed_png(out, 4, 1, grid, palette)

    # Assert
    assert out.read_bytes()[24] == 8
    assert read_indexed_png(out) == (4, 1, grid)


def test_png_is_indexed_4bpp_with_sixteen_color_palette(tmp_path):
    out = tmp_path / "sprite.png"
    write_indexed_png(out, 8, 8, [[0] * 8 for _ in range(8)])
    data = out.read_bytes()

    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[24] == 4  # IHDR bit depth
    assert data[25] == 3  # IHDR colour type: indexed
    assert b"PLTE" in data


def test_reader_accepts_8bpp_indexed_png_from_graphics_editor(tmp_path):
    grid = _checkerboard(7, 4)
    out = tmp_path / "edited.png"
    _write_8bpp_indexed_png(out, grid)

    assert read_indexed_png(out) == (7, 4, grid)


@pytest.mark.parametrize("suffix", [".bmp", ".png", ".BMP", ".PNG"])
def test_image_dispatch_round_trip(suffix, tmp_path):
    width, height = 8, 3
    grid = _checkerboard(width, height)
    out = tmp_path / f"sprite{suffix}"

    write_indexed_image(out, width, height, grid)

    assert read_indexed_image(out) == (width, height, grid)


def test_image_dispatch_rejects_unsupported_format(tmp_path):
    with pytest.raises(ValueError, match="format"):
        write_indexed_image(
            tmp_path / "sprite.gif",
            8,
            8,
            [[0] * 8 for _ in range(8)],
        )


def test_bmp_dispatch_rejects_8bpp_palette_indices(tmp_path):
    with pytest.raises(ValueError, match=r"0\.\.15"):
        write_indexed_image(
            tmp_path / "title-screen.bmp",
            2,
            1,
            [[0x00, 0xF3]],
        )


def test_variant_path_keeps_directory_and_extension():
    path = Path("languages/fr/sprites/status_badges.png")
    assert variant_path(path, 3) == Path(
        "languages/fr/sprites/status_badges-3.png"
    )
