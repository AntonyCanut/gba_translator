"""Unit tests for LZ77 tile-block <-> pixel-grid extract/insert (F-108)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from languages.fr.patches.font import lz77_compress, lz77_decompress
from src.graphics.sprite_rom import (
    TILE_BYTES,
    extract_block,
    extract_mapped_block,
    grid_to_tiles,
    insert_block,
    insert_mapped_block,
    tiles_to_grid,
)


def _make_rom_with_block(tiles: bytes, pad_after: int = 16) -> tuple:
    """Build a minimal ROM buffer holding a single LZ77 block at offset 0."""
    compressed = lz77_compress(tiles)
    rom = bytearray(compressed) + b"\xff" * pad_after
    return rom, 0, len(compressed)


def _make_rom_with_tilemap(
    tiles: bytes,
    entries: list[int],
    *,
    tiles_padding: int = 64,
) -> tuple[bytearray, int, int]:
    """Construit une ROM synthétique avec une planche et sa tilemap LZ77."""
    tiles_block = lz77_compress(tiles)
    tilemap_block = lz77_compress(
        b"".join(entry.to_bytes(2, "little") for entry in entries)
    )
    tilemap_offset = len(tiles_block) + tiles_padding
    rom = bytearray(tiles_block)
    rom.extend(b"\xff" * (tilemap_offset - len(rom)))
    rom.extend(tilemap_block)
    rom.extend(b"\xff" * 64)
    return rom, 0, tilemap_offset


def _lz77_back_references(data: bytes, offset: int = 0) -> list[tuple[int, int]]:
    """Return the ``(length, distance)`` pairs encoded in an LZ77 block."""
    size = data[offset + 1] | (data[offset + 2] << 8) | (data[offset + 3] << 16)
    src = offset + 4
    produced = 0
    references = []
    while produced < size:
        flags = data[src]
        src += 1
        for bit in range(8):
            if produced >= size:
                break
            if flags & (0x80 >> bit):
                first, second = data[src:src + 2]
                src += 2
                length = (first >> 4) + 3
                distance = (((first & 0x0F) << 8) | second) + 1
                references.append((length, distance))
                produced += length
            else:
                src += 1
                produced += 1
    return references


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


def test_tiles_to_grid_8bpp_round_trip():
    # Arrange
    tiles = bytes(
        (tile * 97 + x + 17 * y) % 256
        for tile in range(2)
        for y in range(8)
        for x in range(8)
    )

    # Act
    grid = tiles_to_grid(tiles, 2, 1, bits_per_pixel=8)
    rebuilt = grid_to_tiles(grid, 2, 1, bits_per_pixel=8)

    # Assert
    assert rebuilt == tiles


def test_extract_block_decodes_known_tiles():
    tiles_wide, tiles_tall = 1, 1
    # A single tile, all pixel index 5 (nibble 0x55 repeated).
    tiles = bytes([0x55] * TILE_BYTES)
    rom, offset, _ = _make_rom_with_block(tiles)

    grid, dec_len, _ = extract_block(bytes(rom), offset, tiles_wide, tiles_tall)
    assert dec_len == TILE_BYTES
    assert all(px == 5 for row in grid for px in row)


def test_extract_block_selects_tiles_after_start_offset():
    """Une fenêtre partielle doit ignorer les tuiles qui la précèdent."""
    tiles = b"".join(bytes([index * 0x11]) * TILE_BYTES for index in (1, 2, 3))
    rom, offset, _ = _make_rom_with_block(tiles)

    grid, dec_len, _ = extract_block(
        bytes(rom),
        offset,
        tiles_wide=1,
        tiles_tall=1,
        start_tile=1,
    )

    assert dec_len == 3 * TILE_BYTES
    assert all(pixel == 2 for row in grid for pixel in row)


def test_extract_block_rejects_undersized_block():
    tiles = bytes([0x00] * TILE_BYTES)  # only 1 tile available
    rom, offset, _ = _make_rom_with_block(tiles)
    with pytest.raises(ValueError):
        extract_block(bytes(rom), offset, tiles_wide=2, tiles_tall=1)  # needs 2 tiles


def test_insert_block_round_trip():
    tiles_wide, tiles_tall = 2, 2
    n_tiles = tiles_wide * tiles_tall
    original = bytes((t * 3 + i) & 0xFF for t in range(n_tiles) for i in range(TILE_BYTES))
    rom, offset, _ = _make_rom_with_block(original, pad_after=64)

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


def test_insert_block_replaces_only_selected_tile_window():
    """La réinjection partielle doit préserver les tuiles voisines."""
    original = b"".join(bytes([index * 0x11]) * TILE_BYTES for index in (1, 2, 3))
    rom, offset, _ = _make_rom_with_block(original, pad_after=64)
    replacement = [[4] * 8 for _ in range(8)]

    insert_block(
        rom,
        offset,
        replacement,
        tiles_wide=1,
        tiles_tall=1,
        start_tile=1,
    )

    result = lz77_decompress(bytes(rom), offset)
    assert result is not None
    expected = original[:TILE_BYTES] + bytes([0x44]) * TILE_BYTES + original[2 * TILE_BYTES:]
    assert result[0] == expected


def test_insert_block_keeps_explicit_slot_capacity_across_reinsertions():
    """Une écriture courte ne doit pas réduire le slot physique connu."""
    original = bytes(range(TILE_BYTES))
    rom, offset, original_len = _make_rom_with_block(original, pad_after=64)
    compact_grid = [[0] * 8 for _ in range(8)]
    original_grid = tiles_to_grid(original, tiles_wide=1, tiles_tall=1)

    insert_block(
        rom,
        offset,
        compact_grid,
        tiles_wide=1,
        tiles_tall=1,
        max_compressed_size=original_len,
    )
    insert_block(
        rom,
        offset,
        original_grid,
        tiles_wide=1,
        tiles_tall=1,
        max_compressed_size=original_len,
    )

    result = lz77_decompress(bytes(rom), offset)
    assert result is not None
    assert result[0] == original


def test_insert_block_avoids_odd_overlapping_vram_references():
    """Les flux destinés à la VRAM ne doivent pas chevaucher à distance impaire."""
    tiles_wide, tiles_tall = 1, 1
    tiles = bytes([0x00] * TILE_BYTES)
    rom, offset, _ = _make_rom_with_block(tiles, pad_after=64)
    repeated_grid = [[1] * 8 for _ in range(8)]

    insert_block(rom, offset, repeated_grid, tiles_wide, tiles_tall)

    references = _lz77_back_references(bytes(rom), offset)
    assert references
    assert all(length <= distance or distance % 2 == 0 for length, distance in references)


def test_insert_block_supports_compact_non_vram_stream_for_fixed_slot():
    """Les badges tiennent dans leur slot avec le compresseur standard."""
    tiles = bytes([0x00] * TILE_BYTES)
    compressed = lz77_compress(tiles)
    rom = bytearray(compressed) + bytearray(b"\xab" * 16)
    blank_grid = [[0] * 8 for _ in range(8)]

    # Le mode VRAM-safe grandit d'un octet et toucherait les données voisines.
    with pytest.raises(ValueError, match="tail is non-padding"):
        insert_block(bytearray(rom), 0, blank_grid, 1, 1)

    compact_rom = bytearray(rom)
    insert_block(compact_rom, 0, blank_grid, 1, 1, vram_safe=False)
    result = lz77_decompress(bytes(compact_rom), 0)
    assert result is not None
    assert result[0] == tiles


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


def test_insert_block_relocates_overflow_through_known_pointer():
    """Un bloc trop grand est déplacé uniquement via son pointeur vérifié."""
    # Arrange
    tiles = bytes([0x00] * TILE_BYTES)
    compressed = lz77_compress(tiles)
    pointer_offset = len(compressed) + 64
    rom = bytearray(compressed) + bytearray(b"\xAA" * 64)
    rom[pointer_offset:pointer_offset + 4] = (0x08000000).to_bytes(4, "little")
    rom.extend(b"\xAA" * 64 + b"\xFF" * 512)
    noisy_grid = [[(x * 13 + y * 7) % 16 for x in range(8)] for y in range(8)]

    # Act
    insert_block(
        rom,
        0,
        noisy_grid,
        tiles_wide=1,
        tiles_tall=1,
        pointer_offsets=(pointer_offset,),
    )

    # Assert
    relocated_offset = (
        int.from_bytes(rom[pointer_offset:pointer_offset + 4], "little")
        - 0x08000000
    )
    result = lz77_decompress(bytes(rom), relocated_offset)
    assert relocated_offset > pointer_offset
    assert result is not None
    assert result[0] == grid_to_tiles(noisy_grid, 1, 1)


def test_extract_block_raw_reads_uncompressed_tiles():
    tiles_wide, tiles_tall = 1, 1
    tiles = bytes([0x55] * TILE_BYTES)
    rom = bytearray(tiles) + b"\xff" * 16

    grid, dec_len, comp_len = extract_block(
        bytes(rom), 0, tiles_wide, tiles_tall, compressed=False
    )
    assert dec_len == comp_len == TILE_BYTES
    assert all(px == 5 for row in grid for px in row)


def test_insert_block_raw_round_trip_preserves_size():
    tiles_wide, tiles_tall = 2, 2
    n_tiles = tiles_wide * tiles_tall
    original = bytes((t * 3 + i) & 0xFF for t in range(n_tiles) for i in range(TILE_BYTES))
    tail = b"\xab" * 16
    rom = bytearray(original) + bytearray(tail)

    grid = tiles_to_grid(original, tiles_wide, tiles_tall)
    new_grid = [[(px + 3) % 16 for px in row] for row in grid]

    insert_block(rom, 0, new_grid, tiles_wide, tiles_tall, compressed=False)

    needed = n_tiles * TILE_BYTES
    round_tripped_grid = tiles_to_grid(bytes(rom[:needed]), tiles_wide, tiles_tall)
    assert round_tripped_grid == new_grid
    # Raw insert must never touch bytes past the fixed-size block.
    assert bytes(rom[needed:]) == tail


def test_extract_block_raw_rejects_overflow_of_rom():
    tiles_wide, tiles_tall = 2, 1
    rom = bytes([0x00] * TILE_BYTES)  # only 1 tile available, needs 2
    with pytest.raises(ValueError):
        extract_block(rom, 0, tiles_wide, tiles_tall, compressed=False)


def test_extract_mapped_block_applies_tilemap_flips():
    tile_0 = [[1] * 8 for _ in range(8)]
    tile_1 = [[(x + 2 * y) % 16 for x in range(8)] for y in range(8)]
    tile_2 = [[(3 * x + y) % 16 for x in range(8)] for y in range(8)]
    tiles = (
        grid_to_tiles(tile_0, 1, 1)
        + grid_to_tiles(tile_1, 1, 1)
        + grid_to_tiles(tile_2, 1, 1)
    )
    rom, tiles_offset, tilemap_offset = _make_rom_with_tilemap(
        tiles,
        [0, 1 | 0x0400, 2 | 0x0800, 1 | 0x0C00],
    )

    grid, dec_len, _ = extract_mapped_block(
        bytes(rom),
        tiles_offset,
        tilemap_offset,
        tiles_wide=2,
        tiles_tall=2,
    )

    assert dec_len == len(tiles)
    assert grid[0][0] == tile_0[0][0]
    assert grid[0][8] == tile_1[0][7]
    assert grid[8][0] == tile_2[7][0]
    assert grid[8][8] == tile_1[7][7]


def test_extract_mapped_block_8bpp_applies_tilemap_flip():
    # Arrange
    tile_0 = [[(x + 17 * y) % 256 for x in range(8)] for y in range(8)]
    tile_1 = [[(200 + 3 * x + y) % 256 for x in range(8)] for y in range(8)]
    tiles = (
        grid_to_tiles(tile_0, 1, 1, bits_per_pixel=8)
        + grid_to_tiles(tile_1, 1, 1, bits_per_pixel=8)
    )
    rom, tiles_offset, tilemap_offset = _make_rom_with_tilemap(
        tiles,
        [0, 1 | 0x0400],
    )

    # Act
    grid, dec_len, _ = extract_mapped_block(
        bytes(rom),
        tiles_offset,
        tilemap_offset,
        tiles_wide=2,
        tiles_tall=1,
        bits_per_pixel=8,
    )

    # Assert
    assert dec_len == len(tiles)
    assert grid[0][0] == tile_0[0][0]
    assert grid[0][8] == tile_1[0][7]
    assert max(pixel for row in grid for pixel in row) > 15


def test_insert_mapped_block_round_trip_preserves_tiles():
    tile_0 = [[(x + y) % 16 for x in range(8)] for y in range(8)]
    tile_1 = [[(2 * x + y) % 16 for x in range(8)] for y in range(8)]
    tiles = grid_to_tiles(tile_0, 1, 1) + grid_to_tiles(tile_1, 1, 1)
    rom, tiles_offset, tilemap_offset = _make_rom_with_tilemap(
        tiles,
        [0, 1 | 0x0400],
    )
    grid, _, _ = extract_mapped_block(
        bytes(rom), tiles_offset, tilemap_offset, tiles_wide=2, tiles_tall=1
    )

    insert_mapped_block(
        rom,
        tiles_offset,
        tilemap_offset,
        grid,
        tiles_wide=2,
        tiles_tall=1,
    )

    result = lz77_decompress(bytes(rom), tiles_offset)
    assert result is not None
    assert result[0] == tiles


def test_insert_mapped_block_8bpp_round_trip_preserves_tiles():
    # Arrange
    tile_0 = [[(x + 17 * y) % 256 for x in range(8)] for y in range(8)]
    tile_1 = [[(200 + 3 * x + y) % 256 for x in range(8)] for y in range(8)]
    tiles = (
        grid_to_tiles(tile_0, 1, 1, bits_per_pixel=8)
        + grid_to_tiles(tile_1, 1, 1, bits_per_pixel=8)
    )
    rom, tiles_offset, tilemap_offset = _make_rom_with_tilemap(
        tiles,
        [0, 1 | 0x0400],
    )
    grid, _, _ = extract_mapped_block(
        bytes(rom),
        tiles_offset,
        tilemap_offset,
        tiles_wide=2,
        tiles_tall=1,
        bits_per_pixel=8,
    )

    # Act
    insert_mapped_block(
        rom,
        tiles_offset,
        tilemap_offset,
        grid,
        tiles_wide=2,
        tiles_tall=1,
        bits_per_pixel=8,
    )

    # Assert
    result = lz77_decompress(bytes(rom), tiles_offset)
    assert result is not None
    assert result[0] == tiles


def test_insert_mapped_block_remaps_flip_equivalent_shared_tile_edit():
    """Une édition partageable par flip doit réutiliser la planche existante."""
    tile_0 = [[(x + 2 * y) % 16 for x in range(8)] for y in range(8)]
    tile_1 = [[(3 * x + y + 1) % 16 for x in range(8)] for y in range(8)]
    tiles = grid_to_tiles(tile_0, 1, 1) + grid_to_tiles(tile_1, 1, 1)
    rom, tiles_offset, tilemap_offset = _make_rom_with_tilemap(
        tiles,
        [0, 0, 1],
    )
    grid, _, _ = extract_mapped_block(
        bytes(rom), tiles_offset, tilemap_offset, tiles_wide=3, tiles_tall=1
    )
    expected = [row[:] for row in grid]
    for row in range(8):
        expected[row][8:16] = list(reversed(tile_1[row]))

    insert_mapped_block(
        rom,
        tiles_offset,
        tilemap_offset,
        expected,
        tiles_wide=3,
        tiles_tall=1,
    )

    actual, _, _ = extract_mapped_block(
        bytes(rom), tiles_offset, tilemap_offset, tiles_wide=3, tiles_tall=1
    )
    assert actual == expected


def test_insert_mapped_block_extends_compressed_tiles_when_padding_allows():
    """Une planche LZ77 peut gagner une tuile si le bloc recompressé tient."""
    tiles = grid_to_tiles([[5] * 8 for _ in range(8)], 1, 1)
    rom, tiles_offset, tilemap_offset = _make_rom_with_tilemap(tiles, [0, 0])
    expected, _, _ = extract_mapped_block(
        bytes(rom), tiles_offset, tilemap_offset, tiles_wide=2, tiles_tall=1
    )
    expected[0][8] = 7

    insert_mapped_block(
        rom,
        tiles_offset,
        tilemap_offset,
        expected,
        tiles_wide=2,
        tiles_tall=1,
    )

    actual, decompressed_len, _ = extract_mapped_block(
        bytes(rom), tiles_offset, tilemap_offset, tiles_wide=2, tiles_tall=1
    )
    assert decompressed_len == 2 * TILE_BYTES
    assert actual == expected


def test_insert_mapped_block_relocates_tilemap_through_known_pointer():
    """Une tilemap trop grande est déplacée via son pointeur vérifié."""
    tiles = grid_to_tiles([[5] * 8 for _ in range(8)], 1, 1)
    rom, tiles_offset, tilemap_offset = _make_rom_with_tilemap(tiles, [0, 0])
    tilemap_result = lz77_decompress(bytes(rom), tilemap_offset)
    assert tilemap_result is not None
    _, tilemap_compressed_len = tilemap_result
    pointer_offset = tilemap_offset + tilemap_compressed_len + 8
    rom[pointer_offset - 8:pointer_offset] = b"\xAA" * 8
    rom[pointer_offset:pointer_offset + 4] = (
        0x08000000 + tilemap_offset
    ).to_bytes(4, "little")
    rom[pointer_offset + 4:] = b"\xAA" * 16 + b"\xFF" * 512
    expected, _, _ = extract_mapped_block(
        bytes(rom), tiles_offset, tilemap_offset, tiles_wide=2, tiles_tall=1
    )
    expected[0][8] = 7

    insert_mapped_block(
        rom,
        tiles_offset,
        tilemap_offset,
        expected,
        tiles_wide=2,
        tiles_tall=1,
        tilemap_pointer_offsets=(pointer_offset,),
    )

    relocated_offset = (
        int.from_bytes(rom[pointer_offset:pointer_offset + 4], "little")
        - 0x08000000
    )
    actual, _, _ = extract_mapped_block(
        bytes(rom), tiles_offset, relocated_offset, tiles_wide=2, tiles_tall=1
    )
    assert relocated_offset > pointer_offset
    assert actual == expected


def test_insert_mapped_block_relocates_tiles_through_known_pointer():
    """Une planche trop grande est déplacée via son pointeur vérifié."""
    tiles = grid_to_tiles([[5] * 8 for _ in range(8)], 1, 1)
    rom, tiles_offset, tilemap_offset = _make_rom_with_tilemap(
        tiles,
        [0, 0],
        tiles_padding=0,
    )
    tilemap_result = lz77_decompress(bytes(rom), tilemap_offset)
    assert tilemap_result is not None
    _, tilemap_compressed_len = tilemap_result
    pointer_offset = tilemap_offset + tilemap_compressed_len + 8
    rom[pointer_offset - 8:pointer_offset] = b"\xAA" * 8
    rom[tilemap_offset + tilemap_compressed_len] = 0xFF
    rom[pointer_offset:pointer_offset + 4] = (
        0x08000000 + tiles_offset
    ).to_bytes(4, "little")
    rom[pointer_offset + 4:] = b"\xAA" * 16 + b"\xFF" * 512
    expected, _, _ = extract_mapped_block(
        bytes(rom), tiles_offset, tilemap_offset, tiles_wide=2, tiles_tall=1
    )
    expected[0][8] = 7

    insert_mapped_block(
        rom,
        tiles_offset,
        tilemap_offset,
        expected,
        tiles_wide=2,
        tiles_tall=1,
        tiles_pointer_offsets=(pointer_offset,),
    )

    relocated_offset = (
        int.from_bytes(rom[pointer_offset:pointer_offset + 4], "little")
        - 0x08000000
    )
    actual, _, _ = extract_mapped_block(
        bytes(rom), relocated_offset, tilemap_offset, tiles_wide=2, tiles_tall=1
    )
    assert relocated_offset > pointer_offset
    assert actual == expected


def test_insert_mapped_block_rejects_growth_into_adjacent_data():
    tiles = grid_to_tiles([[5] * 8 for _ in range(8)], 1, 1)
    rom, tiles_offset, tilemap_offset = _make_rom_with_tilemap(
        tiles,
        [0, 0],
        tiles_padding=0,
    )
    grid, _, _ = extract_mapped_block(
        bytes(rom), tiles_offset, tilemap_offset, tiles_wide=2, tiles_tall=1
    )
    grid[0][8] = 7
    original = bytes(rom)

    with pytest.raises(ValueError, match="tail is non-padding"):
        insert_mapped_block(
            rom,
            tiles_offset,
            tilemap_offset,
            grid,
            tiles_wide=2,
            tiles_tall=1,
        )

    assert bytes(rom) == original
