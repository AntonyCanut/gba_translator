"""Unit tests for the 4bpp indexed BMP <-> pixel-grid conversion (F-108)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.graphics.sprite_bmp import DEFAULT_PALETTE, read_indexed_bmp, write_indexed_bmp


def _checkerboard(width: int, height: int) -> list:
    return [[(x + y) % 16 for x in range(width)] for y in range(height)]


def test_round_trip_preserves_pixel_indices(tmp_path):
    width, height = 16, 8
    grid = _checkerboard(width, height)
    out = tmp_path / "sprite.bmp"

    write_indexed_bmp(out, width, height, grid)
    read_w, read_h, read_grid = read_indexed_bmp(out)

    assert (read_w, read_h) == (width, height)
    assert read_grid == grid


def test_round_trip_odd_width(tmp_path):
    # Odd width forces row padding — verify padding bytes don't leak pixels.
    width, height = 5, 3
    grid = [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10 % 16], [11 % 16, 12 % 16, 13 % 16, 14 % 16, 15]]
    out = tmp_path / "odd.bmp"

    write_indexed_bmp(out, width, height, grid)
    _, _, read_grid = read_indexed_bmp(out)

    assert read_grid == grid


def test_round_trip_8bpp_preserves_all_palette_indices(tmp_path):
    width, height = 17, 3
    grid = [[(x + y * width) % 256 for x in range(width)] for y in range(height)]
    palette = [(index, 255 - index, index // 2) for index in range(256)]
    out = tmp_path / "screen.bmp"

    write_indexed_bmp(out, width, height, grid, palette)
    read_w, read_h, read_grid = read_indexed_bmp(out)

    assert (read_w, read_h) == (width, height)
    assert read_grid == grid
    assert int.from_bytes(out.read_bytes()[28:30], "little") == 8


def test_file_header_fields(tmp_path):
    width, height = 8, 8
    grid = [[0] * width for _ in range(height)]
    out = tmp_path / "min.bmp"
    write_indexed_bmp(out, width, height, grid)

    data = out.read_bytes()
    assert data[:2] == b"BM"
    import struct
    off_bits = struct.unpack("<I", data[10:14])[0]
    assert off_bits == 14 + 40 + 64  # file header + info header + 16-color palette
    bpp = struct.unpack("<H", data[28:30])[0]
    assert bpp == 4


def test_rejects_wrong_palette_size(tmp_path):
    with pytest.raises(ValueError):
        write_indexed_bmp(tmp_path / "bad.bmp", 8, 8, [[0] * 8 for _ in range(8)],
                           palette=DEFAULT_PALETTE[:15])


def test_rejects_mismatched_grid_shape(tmp_path):
    with pytest.raises(ValueError):
        write_indexed_bmp(tmp_path / "bad.bmp", 8, 8, [[0] * 8 for _ in range(4)])


def test_rejects_non_bmp(tmp_path):
    bogus = tmp_path / "not_a_bmp.bmp"
    bogus.write_bytes(b"not a bmp file")
    with pytest.raises(ValueError):
        read_indexed_bmp(bogus)


def test_rejects_wrong_bit_depth(tmp_path):
    # Seuls les BMP indexés 4/8 bpp correspondent aux sprites GBA pris en charge.
    import struct
    width, height = 8, 8
    off_bits = 14 + 40 + 2 * 4
    file_header = struct.pack("<2sIHHI", b"BM", off_bits + width * height, 0, 0, off_bits)
    info_header = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 1, 0,
                               width * height, 0, 0, 2, 0)
    path = tmp_path / "onebpp.bmp"
    path.write_bytes(file_header + info_header + b"\x00" * (2 * 4) + b"\x00" * width * height)
    with pytest.raises(ValueError):
        read_indexed_bmp(path)
