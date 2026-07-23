"""Garde du bandeau graphique « START Tri » du Cube (issue #140)."""

import struct
import zlib
from pathlib import Path

from languages.fr.sprites import SPRITES
from src.graphics.sprite_bmp import read_indexed_bmp


ROOT = Path(__file__).resolve().parents[3]
ASSET = ROOT / "languages/fr/sprites/cube_sort_hint.bmp"
EDITABLE_ASSET = ROOT / "languages/fr/sprites/cube_sort_hint.png"

# Masque blanc (index de palette 3) attendu dans la zone du libellé.
# Le gris d'ombrage est volontairement ignoré : ce masque suffit à empêcher
# le retour du mot anglais « Sort » tout en figeant la lecture « Tri ».
TRI_WHITE_ROWS = (
    "...#####........#.",
    ".....#............",
    ".....#....###...#.",
    ".....#....#..#..#.",
    ".....#....#.....#.",
    ".....#....#.....#.",
    ".....#....#.....#.",
    "..................",
)


def _read_png_pixels(path: Path) -> tuple[int, int, tuple[tuple[int, ...], ...]]:
    """Lit les indices d'un PNG indexé 4 bpp sans dépendance externe."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"

    position = 8
    idat = bytearray()
    while position < len(data):
        length = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
            assert (bit_depth, color_type) == (4, 3)
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            break

    stride = (width + 1) // 2
    encoded = zlib.decompress(idat)
    previous = bytearray(stride)
    rows: list[tuple[int, ...]] = []
    cursor = 0
    for _ in range(height):
        filter_type = encoded[cursor]
        scanline = bytearray(encoded[cursor + 1 : cursor + 1 + stride])
        cursor += stride + 1
        for index, value in enumerate(scanline):
            left = scanline[index - 1] if index else 0
            above = previous[index]
            upper_left = previous[index - 1] if index else 0
            if filter_type == 1:
                scanline[index] = (value + left) & 0xFF
            elif filter_type == 2:
                scanline[index] = (value + above) & 0xFF
            elif filter_type == 3:
                scanline[index] = (value + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                estimate = left + above - upper_left
                distances = (
                    abs(estimate - left),
                    abs(estimate - above),
                    abs(estimate - upper_left),
                )
                predictor = (left, above, upper_left)[distances.index(min(distances))]
                scanline[index] = (value + predictor) & 0xFF
            else:
                assert filter_type == 0
        unpacked = tuple(
            value
            for byte in scanline
            for value in (byte >> 4, byte & 0x0F)
        )
        rows.append(unpacked[:width])
        previous = scanline
    return width, height, tuple(rows)


def test_cube_sort_hint_registry_targets_live_lz77_block() -> None:
    sprite = SPRITES["cube_sort_hint"]
    assert sprite.blocks == (0x00EF1B68,)
    assert (sprite.tiles_wide, sprite.tiles_tall) == (13, 4)
    assert sprite.compressed


def test_cube_sort_hint_asset_draws_tri() -> None:
    width, height, grid = read_indexed_bmp(ASSET)
    assert (width, height) == (104, 32)

    actual = tuple(
        "".join("#" if pixel == 3 else "." for pixel in row[:18])
        for row in grid[12:20]
    )
    assert actual == TRI_WHITE_ROWS


def test_cube_sort_hint_leaves_two_pixels_after_start_keycap() -> None:
    _, _, grid = read_indexed_bmp(ASSET)
    assert all(pixel == 1 for row in grid[12:20] for pixel in row[:2])


def test_cube_sort_hint_editable_png_matches_build_asset() -> None:
    bmp_width, bmp_height, bmp_grid = read_indexed_bmp(ASSET)
    png_width, png_height, png_grid = _read_png_pixels(EDITABLE_ASSET)
    assert (png_width, png_height) == (bmp_width, bmp_height)
    assert png_grid == tuple(tuple(row) for row in bmp_grid)


def test_french_build_inserts_cube_sort_hint() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert (
        "scripts/insert_sprite.py --rom $(FR_BUILD) --lang fr "
        "--sprite cube_sort_hint --bmp languages/fr/sprites/cube_sort_hint.bmp"
    ) in makefile
