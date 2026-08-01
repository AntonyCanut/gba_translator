#!/usr/bin/env python3
"""Extract/insert a rectangular tile sprite from/into an LZ77-compressed ROM
block (ticket F-108).

This is the ROM-facing half of the sprite pipeline: it converts between a
flat run of 4/8bpp 8x8 tiles (as stored inside an LZ77 block) and the pixel
grid consumed by ``sprite_image``. Recompression follows the same
padding-tolerant overflow rule already used by ``status_badges.py`` /
``hp_labels.py``: a recompressed block may grow past the original compressed
length as long as the extra bytes it would overwrite are 0x00/0xFF padding.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import (  # noqa: E402
    lz77_compress,
    lz77_decompress,
    pixels_to_tile,
    tile_to_pixels,
)

TILE_BYTES = 32  # bytes per 4bpp 8x8 tile
TILE_BYTES_8BPP = 64
TILE_PX = 8
TILEMAP_INDEX_MASK = 0x03FF
TILEMAP_HFLIP = 0x0400
TILEMAP_VFLIP = 0x0800
TILEMAP_FLIP_MASK = TILEMAP_HFLIP | TILEMAP_VFLIP

Grid = list[list[int]]
Palette = list[tuple[int, int, int]]

PALETTE_COLOURS = 16


def _tile_bytes(bits_per_pixel: int) -> int:
    """Retourne la taille d’une tuile GBA pour la profondeur demandée."""
    if bits_per_pixel == 4:
        return TILE_BYTES
    if bits_per_pixel == 8:
        return TILE_BYTES_8BPP
    raise ValueError("bits_per_pixel must be 4 or 8")


def _tile_to_pixels(tile: bytes, bits_per_pixel: int) -> list[int]:
    """Décode une tuile GBA 4 ou 8 bpp en 64 indices de palette."""
    if bits_per_pixel == 4:
        return tile_to_pixels(tile)
    _tile_bytes(bits_per_pixel)
    return list(tile)


def _pixels_to_tile(pixels: list[int], bits_per_pixel: int) -> bytes:
    """Encode 64 indices de palette en tuile GBA 4 ou 8 bpp."""
    max_index = (1 << bits_per_pixel) - 1
    if any(not 0 <= pixel <= max_index for pixel in pixels):
        raise ValueError(f"pixel indices must be in the 0..{max_index} range")
    if bits_per_pixel == 4:
        return pixels_to_tile(pixels)
    _tile_bytes(bits_per_pixel)
    return bytes(pixels)


def read_gba_palette(
    rom: bytes,
    offset: int,
    colours: int = PALETTE_COLOURS,
) -> Palette:
    """Lit une palette GBA BGR555 et la rend en RGB 8 bits.

    Sert d'aperçu fidèle dans les images indexées extraites : sans elle, un
    éditeur ouvre la planche avec la palette de debug et les images-mots sont
    illisibles. Seuls les *indices* comptent pour la réinjection.
    """
    if colours not in (16, 256):
        raise ValueError("palette colours must be 16 or 256")
    if offset + 2 * colours > len(rom):
        raise ValueError(f"palette 0x{offset:08X} hors de la ROM")
    palette: Palette = []
    for index in range(colours):
        raw = rom[offset + 2 * index] | (rom[offset + 2 * index + 1] << 8)
        palette.append((
            (raw & 0x1F) * 255 // 31,
            ((raw >> 5) & 0x1F) * 255 // 31,
            ((raw >> 10) & 0x1F) * 255 // 31,
        ))
    return palette


def tiles_to_grid(
    tiles: bytes,
    tiles_wide: int,
    tiles_tall: int,
    bits_per_pixel: int = 4,
) -> Grid:
    """Arrange a flat run of tiles (row-major, ``tiles_wide`` per row) into a
    single pixel grid of size ``tiles_tall*8`` rows x ``tiles_wide*8`` cols."""
    width = tiles_wide * TILE_PX
    height = tiles_tall * TILE_PX
    tile_bytes = _tile_bytes(bits_per_pixel)
    grid: Grid = [[0] * width for _ in range(height)]
    for ty in range(tiles_tall):
        for tx in range(tiles_wide):
            idx = ty * tiles_wide + tx
            tile = tiles[idx * tile_bytes:(idx + 1) * tile_bytes]
            pixels = _tile_to_pixels(tile, bits_per_pixel)
            for r in range(TILE_PX):
                row = grid[ty * TILE_PX + r]
                base = r * TILE_PX
                row[tx * TILE_PX:tx * TILE_PX + TILE_PX] = pixels[base:base + TILE_PX]
    return grid


def grid_to_tiles(
    grid: Grid,
    tiles_wide: int,
    tiles_tall: int,
    bits_per_pixel: int = 4,
) -> bytes:
    """Inverse of ``tiles_to_grid``."""
    out = bytearray()
    for ty in range(tiles_tall):
        for tx in range(tiles_wide):
            pixels: list[int] = []
            for r in range(TILE_PX):
                row = grid[ty * TILE_PX + r]
                pixels.extend(row[tx * TILE_PX:tx * TILE_PX + TILE_PX])
            out.extend(_pixels_to_tile(pixels, bits_per_pixel))
    return bytes(out)


def _decompress_tilemap(
    rom: bytes,
    offset: int,
    tiles_wide: int,
    tiles_tall: int,
) -> bytes:
    """Décompresse et valide une tilemap GBA rectangulaire."""
    result = lz77_decompress(rom, offset)
    if result is None:
        raise ValueError(f"0x{offset:08X}: failed to decompress LZ77 tilemap")
    tilemap, _ = result
    needed = tiles_wide * tiles_tall * 2
    if len(tilemap) < needed:
        raise ValueError(
            f"0x{offset:08X}: tilemap size {len(tilemap)} < needed {needed}"
        )
    return tilemap[:needed]


def _tilemap_entries(tilemap: bytes) -> list[int]:
    """Retourne les entrées 16 bits little-endian d'une tilemap GBA."""
    return [
        int.from_bytes(tilemap[offset:offset + 2], "little")
        for offset in range(0, len(tilemap), 2)
    ]


def _flip_tile_pixels(
    pixels: list[int],
    horizontal: bool,
    vertical: bool,
) -> list[int]:
    """Applique les flips d'une entrée de tilemap à une tuile 8 × 8."""
    return [
        pixels[
            (TILE_PX - 1 - y if vertical else y) * TILE_PX
            + (TILE_PX - 1 - x if horizontal else x)
        ]
        for y in range(TILE_PX)
        for x in range(TILE_PX)
    ]


def _write_block_payload(
    rom: bytearray,
    offset: int,
    payload: bytes,
    original_len: int,
    compressed: bool,
    vram_safe: bool,
    max_compressed_size: int | None = None,
) -> None:
    """Écrit un payload de planche en protégeant les données ROM voisines."""
    if not compressed:
        rom[offset:offset + len(payload)] = payload
        return

    compressed_out = lz77_compress(payload, vram_safe=vram_safe)
    if offset + len(compressed_out) > len(rom):
        raise ValueError(f"0x{offset:08X}: recompressed block overflows ROM")
    if max_compressed_size is not None:
        if max_compressed_size < original_len:
            raise ValueError(
                f"0x{offset:08X}: configured slot ({max_compressed_size}) < "
                f"stored block ({original_len})"
            )
        if len(compressed_out) > max_compressed_size:
            raise ValueError(
                f"0x{offset:08X}: recompressed ({len(compressed_out)}) > slot "
                f"capacity ({max_compressed_size})"
            )
    elif len(compressed_out) > original_len:
        extra = rom[offset + original_len:offset + len(compressed_out)]
        if any(byte not in (0x00, 0xFF) for byte in extra):
            raise ValueError(
                f"0x{offset:08X}: recompressed ({len(compressed_out)}) > original "
                f"({original_len}) and tail is non-padding"
            )
    rom[offset:offset + len(compressed_out)] = compressed_out


def extract_block(
    rom: bytes,
    offset: int,
    tiles_wide: int,
    tiles_tall: int,
    compressed: bool = True,
    bits_per_pixel: int = 4,
    start_tile: int = 0,
) -> tuple[Grid, int, int]:
    """Return the pixel grid for the sprite block at *offset*.

    When *compressed* is true (the default) the block is an LZ77-compressed
    blob (see ``insert_block``). Some small OBJ tilesets — e.g. the naming
    keyboard's help panel — are instead stored as a flat run of raw 4bpp
    tiles with no compression; pass ``compressed=False`` for those.

    ``start_tile`` sélectionne une fenêtre contiguë à l’intérieur du bloc sans
    exposer ni réécrire les tuiles qui la précèdent.

    Returns ``(grid, decompressed_len, compressed_len)``. Raises ``ValueError``
    if the block can't be decompressed or is smaller than the sprite needs.
    """
    if start_tile < 0:
        raise ValueError("start_tile must be non-negative")
    tile_bytes = _tile_bytes(bits_per_pixel)
    needed = tiles_wide * tiles_tall * tile_bytes
    start = start_tile * tile_bytes
    end = start + needed
    if not compressed:
        if offset + end > len(rom):
            raise ValueError(f"0x{offset:08X}: raw block overflows ROM")
        raw = rom[offset + start:offset + end]
        grid = tiles_to_grid(raw, tiles_wide, tiles_tall, bits_per_pixel)
        return grid, end, end

    result = lz77_decompress(rom, offset)
    if result is None:
        raise ValueError(f"0x{offset:08X}: failed to decompress LZ77 block")
    decompressed, comp_len = result
    if len(decompressed) < end:
        raise ValueError(
            f"0x{offset:08X}: decompressed size {len(decompressed)} < needed {end}"
        )
    grid = tiles_to_grid(
        decompressed[start:end], tiles_wide, tiles_tall, bits_per_pixel
    )
    return grid, len(decompressed), comp_len


def extract_mapped_block(
    rom: bytes,
    tiles_offset: int,
    tilemap_offset: int,
    tiles_wide: int,
    tiles_tall: int,
    *,
    compressed: bool = True,
    bits_per_pixel: int = 4,
) -> tuple[Grid, int, int]:
    """Reconstruit un écran de tuiles depuis une planche et sa tilemap.

    Args:
        rom: Octets complets de la ROM.
        tiles_offset: Offset de la planche 4 bpp.
        tilemap_offset: Offset de la tilemap LZ77.
        tiles_wide: Largeur de l'écran en tuiles.
        tiles_tall: Hauteur de l'écran en tuiles.
        compressed: Indique si la planche est compressée en LZ77.

    Returns:
        La grille reconstruite, la taille décompressée de la planche et la
        longueur occupée par son bloc compressé.
    """
    tilemap = _decompress_tilemap(rom, tilemap_offset, tiles_wide, tiles_tall)
    entries = _tilemap_entries(tilemap)
    tile_bytes = _tile_bytes(bits_per_pixel)
    needed = (
        max(entry & TILEMAP_INDEX_MASK for entry in entries) + 1
    ) * tile_bytes
    if compressed:
        result = lz77_decompress(rom, tiles_offset)
        if result is None:
            raise ValueError(f"0x{tiles_offset:08X}: failed to decompress LZ77 block")
        tiles, comp_len = result
        if len(tiles) < needed:
            raise ValueError(
                f"0x{tiles_offset:08X}: decompressed size {len(tiles)} < needed {needed}"
            )
    else:
        if tiles_offset + needed > len(rom):
            raise ValueError(f"0x{tiles_offset:08X}: raw block overflows ROM")
        tiles = rom[tiles_offset:tiles_offset + needed]
        comp_len = needed

    grid: Grid = [
        [0] * (tiles_wide * TILE_PX)
        for _ in range(tiles_tall * TILE_PX)
    ]
    for cell, entry in enumerate(entries):
        tile_index = entry & TILEMAP_INDEX_MASK
        tile = tiles[tile_index * tile_bytes:(tile_index + 1) * tile_bytes]
        pixels = _flip_tile_pixels(
            _tile_to_pixels(tile, bits_per_pixel),
            bool(entry & TILEMAP_HFLIP),
            bool(entry & TILEMAP_VFLIP),
        )
        tile_y, tile_x = divmod(cell, tiles_wide)
        for row in range(TILE_PX):
            start = row * TILE_PX
            grid[tile_y * TILE_PX + row][
                tile_x * TILE_PX:(tile_x + 1) * TILE_PX
            ] = pixels[start:start + TILE_PX]
    return grid, len(tiles), comp_len


def insert_block(
    rom: bytearray,
    offset: int,
    grid: Grid,
    tiles_wide: int,
    tiles_tall: int,
    compressed: bool = True,
    vram_safe: bool = True,
    bits_per_pixel: int = 4,
    start_tile: int = 0,
    max_compressed_size: int | None = None,
) -> None:
    """Re-encode *grid* into tiles and write it back at *offset*.

    When *compressed* is true (the default), recompress with LZ77; raises
    ``ValueError`` if the block can't be decompressed, is too small, or the
    recompressed result would overwrite non-padding bytes. ``vram_safe`` keeps
    the conservative direct-to-VRAM stream by default; fixed slots known to
    accept normal LZ77 can disable it for a smaller stream. When *compressed*
    is false, the tiles are written back raw — see ``extract_block``.
    ``start_tile`` limite l’écriture à une fenêtre contiguë du bloc.
    ``max_compressed_size`` conserve la capacité physique connue d’un slot
    entre plusieurs éditions, même après une première compression plus courte.
    """
    if start_tile < 0:
        raise ValueError("start_tile must be non-negative")
    tile_bytes = _tile_bytes(bits_per_pixel)
    needed = tiles_wide * tiles_tall * tile_bytes
    start = start_tile * tile_bytes
    end = start + needed
    if not compressed:
        if offset + end > len(rom):
            raise ValueError(f"0x{offset:08X}: raw block overflows ROM")
        rom[offset + start:offset + end] = grid_to_tiles(
            grid, tiles_wide, tiles_tall, bits_per_pixel
        )
        return

    result = lz77_decompress(rom, offset)
    if result is None:
        raise ValueError(f"0x{offset:08X}: failed to decompress LZ77 block")
    decompressed, comp_len = result
    if len(decompressed) < end:
        raise ValueError(
            f"0x{offset:08X}: decompressed size {len(decompressed)} < needed {end}"
        )

    tiles = bytearray(decompressed)
    tiles[start:end] = grid_to_tiles(
        grid, tiles_wide, tiles_tall, bits_per_pixel
    )
    _write_block_payload(
        rom,
        offset,
        bytes(tiles),
        comp_len,
        compressed=True,
        vram_safe=vram_safe,
        max_compressed_size=max_compressed_size,
    )


def insert_mapped_block(
    rom: bytearray,
    tiles_offset: int,
    tilemap_offset: int,
    grid: Grid,
    tiles_wide: int,
    tiles_tall: int,
    *,
    compressed: bool = True,
    vram_safe: bool = True,
    bits_per_pixel: int = 4,
) -> None:
    """Réinjecte un écran mappé dans sa planche de tuiles.

    Les tuiles visuellement équivalentes sont dédupliquées en utilisant les
    flips de la tilemap. Une édition qui exige plus de tuiles distinctes que
    la planche existante est rejetée avant toute écriture.

    Args:
        rom: Tampon ROM modifiable.
        tiles_offset: Offset de la planche 4 bpp.
        tilemap_offset: Offset de la tilemap LZ77.
        grid: Écran édité sous forme de grille d'indices palette.
        tiles_wide: Largeur de l'écran en tuiles.
        tiles_tall: Hauteur de l'écran en tuiles.
        compressed: Indique si la planche est compressée en LZ77.
        vram_safe: Utilise le compresseur compatible VRAM.
    """
    expected_width = tiles_wide * TILE_PX
    expected_height = tiles_tall * TILE_PX
    if len(grid) != expected_height or any(
        len(row) != expected_width for row in grid
    ):
        raise ValueError(
            f"invalid mapped grid size: expected {expected_width}x{expected_height}"
        )

    tilemap = _decompress_tilemap(rom, tilemap_offset, tiles_wide, tiles_tall)
    entries = _tilemap_entries(tilemap)
    tile_bytes = _tile_bytes(bits_per_pixel)
    needed = (
        max(entry & TILEMAP_INDEX_MASK for entry in entries) + 1
    ) * tile_bytes
    if compressed:
        result = lz77_decompress(rom, tiles_offset)
        if result is None:
            raise ValueError(f"0x{tiles_offset:08X}: failed to decompress LZ77 block")
        decompressed, comp_len = result
        if len(decompressed) < needed:
            raise ValueError(
                f"0x{tiles_offset:08X}: decompressed size "
                f"{len(decompressed)} < needed {needed}"
            )
        tiles = bytearray(decompressed)
    else:
        if tiles_offset + needed > len(rom):
            raise ValueError(f"0x{tiles_offset:08X}: raw block overflows ROM")
        tiles = bytearray(rom[tiles_offset:tiles_offset + needed])
        comp_len = needed

    desired_tiles: dict[bytes, list[int]] = {}
    variants_by_cell: list[tuple[bytes, bytes, bytes, bytes]] = []
    for cell, entry in enumerate(entries):
        tile_y, tile_x = divmod(cell, tiles_wide)
        rendered = [
            grid[tile_y * TILE_PX + row][tile_x * TILE_PX + column]
            for row in range(TILE_PX)
            for column in range(TILE_PX)
        ]
        variants = tuple(
            _pixels_to_tile(
                _flip_tile_pixels(rendered, horizontal, vertical),
                bits_per_pixel,
            )
            for horizontal, vertical in (
                (False, False),
                (True, False),
                (False, True),
                (True, True),
            )
        )
        canonical = min(variants)
        variants_by_cell.append(variants)
        desired_tiles.setdefault(canonical, []).append(cell)

    tile_count = len(tiles) // tile_bytes
    if len(desired_tiles) > tile_count:
        conflicting_index = next(
            (
                tile_index
                for tile_index in {
                    entry & TILEMAP_INDEX_MASK for entry in entries
                }
                if len(
                    {
                        min(variants_by_cell[cell])
                        for cell, entry in enumerate(entries)
                        if (entry & TILEMAP_INDEX_MASK) == tile_index
                    }
                )
                > 1
            ),
            entries[0] & TILEMAP_INDEX_MASK,
        )
        raise ValueError(
            f"shared tile {conflicting_index} has conflicting mapped edits "
            f"and no spare tile"
        )

    candidates = {
        canonical: sorted(
            {
                entries[cell] & TILEMAP_INDEX_MASK
                for cell in cells
            }
        )
        for canonical, cells in desired_tiles.items()
    }
    assignments: dict[bytes, int] = {}
    assigned_groups: dict[int, bytes] = {}

    def assign_existing_index(canonical: bytes, seen: set[int]) -> bool:
        """Associe un groupe à un de ses indices actuels si possible."""
        for tile_index in candidates[canonical]:
            if tile_index in seen:
                continue
            seen.add(tile_index)
            previous = assigned_groups.get(tile_index)
            if previous is None or assign_existing_index(previous, seen):
                assigned_groups[tile_index] = canonical
                assignments[canonical] = tile_index
                return True
        return False

    ordered_groups = sorted(
        desired_tiles,
        key=lambda canonical: (
            len(candidates[canonical]),
            desired_tiles[canonical][0],
        ),
    )
    for canonical in ordered_groups:
        assign_existing_index(canonical, set())

    used_indices = set(assigned_groups)
    free_indices = iter(
        index for index in range(tile_count) if index not in used_indices
    )
    for canonical in ordered_groups:
        if canonical not in assignments:
            assignments[canonical] = next(free_indices)

    remapped_entries = entries[:]
    for canonical, cells in desired_tiles.items():
        tile_index = assignments[canonical]
        preferred_cell = next(
            (
                cell
                for cell in cells
                if (entries[cell] & TILEMAP_INDEX_MASK) == tile_index
            ),
            cells[0],
        )
        preferred_flip = (
            (1 if entries[preferred_cell] & TILEMAP_HFLIP else 0)
            | (2 if entries[preferred_cell] & TILEMAP_VFLIP else 0)
        )
        stored_tile = variants_by_cell[preferred_cell][preferred_flip]
        start = tile_index * tile_bytes
        tiles[start:start + tile_bytes] = stored_tile
        for cell in cells:
            flip_index = (
                preferred_flip
                if cell == preferred_cell
                else variants_by_cell[cell].index(stored_tile)
            )
            horizontal = bool(flip_index & 0x01)
            vertical = bool(flip_index & 0x02)
            preserved = entries[cell] & ~(TILEMAP_INDEX_MASK | TILEMAP_FLIP_MASK)
            remapped_entries[cell] = (
                preserved
                | tile_index
                | (TILEMAP_HFLIP if horizontal else 0)
                | (TILEMAP_VFLIP if vertical else 0)
            )

    tilemap_result = lz77_decompress(rom, tilemap_offset)
    if tilemap_result is None:
        raise ValueError(f"0x{tilemap_offset:08X}: failed to decompress LZ77 tilemap")
    tilemap_payload, tilemap_comp_len = tilemap_result
    remapped_tilemap = bytearray(tilemap_payload)
    for cell, entry in enumerate(remapped_entries):
        start = cell * 2
        remapped_tilemap[start:start + 2] = entry.to_bytes(2, "little")

    staged = bytearray(rom)
    _write_block_payload(
        staged,
        tiles_offset,
        bytes(tiles),
        comp_len,
        compressed=compressed,
        vram_safe=vram_safe,
    )
    _write_block_payload(
        staged,
        tilemap_offset,
        bytes(remapped_tilemap),
        tilemap_comp_len,
        compressed=True,
        vram_safe=vram_safe,
    )
    rom[:] = staged
