#!/usr/bin/env python3
"""Patch the FR ROM with the CI build number.

Two patches are applied:
1. GBA header byte 0xBC (software version field) is set to ``build_number & 0xFF``
   and the header complement checksum at 0xBD is recomputed.
2. The title screen version display (pre-rendered pixel art) is replaced with
   the string "FR.2.0.<build_number>" drawn in the same 4px-wide font style as
   the original "2.1.1.1" string.  The new tileset and tilemap are written into
   trailing free space and the BG data pointers are updated accordingly.

Usage:
    python3 scripts/patch_version_fr.py --rom output/roms/GenedRom-fr.gba \\
        --build-number 42
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# LZ77 (GBA BIOS format) — identical to the copies in patch_font_fr.py
# ---------------------------------------------------------------------------

_LZ77_MAGIC = 0x10


def _lz77_decompress(data: bytes | bytearray, offset: int) -> tuple[bytes, int] | None:
    if offset + 4 > len(data) or data[offset] != _LZ77_MAGIC:
        return None
    size = data[offset + 1] | (data[offset + 2] << 8) | (data[offset + 3] << 16)
    if size <= 0:
        return None
    out = bytearray()
    src = offset + 4
    while len(out) < size:
        if src >= len(data):
            return None
        flags = data[src]
        src += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                if src + 1 >= len(data):
                    return None
                b1 = data[src]
                b2 = data[src + 1]
                src += 2
                disp = ((b1 & 0x0F) << 8) | b2
                length = (b1 >> 4) + 3
                disp += 1
                if disp > len(out):
                    return None
                for _ in range(length):
                    out.append(out[-disp])
                    if len(out) >= size:
                        break
            else:
                if src >= len(data):
                    return None
                out.append(data[src])
                src += 1
    return bytes(out), src - offset


def _lz77_compress(data: bytes) -> bytes:
    size = len(data)
    out = bytearray()
    out.append(_LZ77_MAGIC)
    out.extend((size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF))
    pos = 0
    while pos < size:
        flags_pos = len(out)
        out.append(0)
        flags = 0
        for i in range(8):
            if pos >= size:
                break
            max_len = min(18, size - pos)
            window_start = max(0, pos - 0x1000)
            window = data[window_start:pos]
            best_len = 0
            best_disp = 0
            if window:
                for length in range(max_len, 2, -1):
                    idx = window.rfind(data[pos:pos + length])
                    if idx != -1:
                        best_len = length
                        best_disp = pos - (window_start + idx)
                        break
            if best_len >= 3:
                flags |= 1 << (7 - i)
                disp = best_disp - 1
                out.append(((best_len - 3) << 4) | ((disp >> 8) & 0x0F))
                out.append(disp & 0xFF)
                pos += best_len
            else:
                out.append(data[pos])
                pos += 1
        out[flags_pos] = flags
    return bytes(out)


# ---------------------------------------------------------------------------
# GBA ROM header patch
# ---------------------------------------------------------------------------

def _compute_checksum(data: bytes | bytearray) -> int:
    return (-(sum(data[0xA0:0xBD]) + 0x19)) & 0xFF


def patch_version(data: bytearray, build_number: int) -> bool:
    version_byte = build_number & 0xFF
    if data[0xBC] == version_byte:
        return False
    data[0xBC] = version_byte
    data[0xBD] = _compute_checksum(data)
    return True


# ---------------------------------------------------------------------------
# Title-screen version display patch
# ---------------------------------------------------------------------------

_GBA_BASE = 0x08000000
# ROM offsets of the two GBA pointers we need to update
_TILESET_PTR_OFF = 0x1413AC
_TILEMAP_PTR_OFF = 0x1413B8

# NOT FOR SALE intro screen: both background layers share the same 32×32 tilemap
# (1024 entries × 2 bytes each).  Row 18 (0-indexed) is the version-text row;
# columns 3, 5, 7, 9, 11, 13, 15 carry the version tile indices.  We replace
# those entries with the surrounding frame-decoration entries from row 16 so
# the version text disappears.  Both pointers must be updated.
_NFS_TILEMAP_PTR_A = 0x260218
_NFS_TILEMAP_PTR_B = 0x260220
_NFS_VER_ROW = 18
_NFS_VER_COLS = (3, 5, 7, 9, 11, 13, 15)

# Tilemap dimensions
_TM_COLS = 32
_TM_ROWS = 20

# Rows in the tilemap that show the version number
_VER_ROW2 = 2
_VER_ROW3 = 3
_VER_COL_START = 10
_VER_COL_COUNT = 10  # cols 10-19

# Neutral tiles for clearing the version area (taken from EN tilemap)
# Tile 84 is the blank spacer between the two version groups in row 2.
# Tile 76 is the floor tile used in row 3 around the version area.
_BLANK_ROW2 = 84
_BLANK_ROW3 = 76

# 4bpp palette indices — match the existing version tiles in the EN tileset
_FG = 3    # text foreground
_BG = 0xF  # background
_DC = 0xC  # decorative separator line at the bottom of each tile

# Character bitmaps: 4 px wide × 5 px tall, 1 = fg pixel, 0 = bg pixel.
# Two characters are packed side-by-side into each 8×8 tile.
_CHAR_PIXELS: dict[str, list[list[int]]] = {
    '0': [[0,1,1,0],[1,0,0,1],[1,0,0,1],[1,0,0,1],[0,1,1,0]],
    '1': [[0,0,1,0],[0,1,1,0],[0,0,1,0],[0,0,1,0],[0,1,1,1]],
    '2': [[0,1,1,0],[0,0,0,1],[0,1,1,0],[1,0,0,0],[1,1,1,0]],
    '3': [[0,1,1,0],[0,0,0,1],[0,1,1,0],[0,0,0,1],[0,1,1,0]],
    '4': [[1,0,0,1],[1,0,0,1],[1,1,1,1],[0,0,0,1],[0,0,0,1]],
    '5': [[1,1,1,0],[1,0,0,0],[1,1,1,0],[0,0,0,1],[1,1,1,0]],
    '6': [[0,1,1,0],[1,0,0,0],[1,1,1,0],[1,0,0,1],[0,1,1,0]],
    '7': [[1,1,1,0],[0,0,0,1],[0,0,1,0],[0,1,0,0],[0,1,0,0]],
    '8': [[0,1,1,0],[1,0,0,1],[0,1,1,0],[1,0,0,1],[0,1,1,0]],
    '9': [[0,1,1,0],[1,0,0,1],[0,1,1,1],[0,0,0,1],[0,1,1,0]],
    'F': [[1,1,1,0],[1,0,0,0],[1,1,0,0],[1,0,0,0],[1,0,0,0]],
    'R': [[1,1,0,0],[1,0,1,0],[1,1,0,0],[1,0,1,0],[1,0,0,1]],
    '.': [[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,1,0,0]],
    ' ': [[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]],
}


def _make_char_tile(left_ch: str, right_ch: str) -> bytes:
    """Return a 32-byte 4bpp 8×8 tile with two version-font characters."""
    lp = _CHAR_PIXELS.get(left_ch, _CHAR_PIXELS[' '])
    rp = _CHAR_PIXELS.get(right_ch, _CHAR_PIXELS[' '])
    tile = bytearray(32)
    # Row 0: blank
    for c in range(4):
        tile[c] = _BG | (_BG << 4)
    # Rows 1–5: character content (left char at cols 0-3, right at cols 4-7)
    for ri, (lr, rr) in enumerate(zip(lp, rp), 1):
        tile[ri * 4 + 0] = (_FG if lr[0] else _BG) | ((_FG if lr[1] else _BG) << 4)
        tile[ri * 4 + 1] = (_FG if lr[2] else _BG) | ((_FG if lr[3] else _BG) << 4)
        tile[ri * 4 + 2] = (_FG if rr[0] else _BG) | ((_FG if rr[1] else _BG) << 4)
        tile[ri * 4 + 3] = (_FG if rr[2] else _BG) | ((_FG if rr[3] else _BG) << 4)
    # Row 6: decorative separator
    for c in range(4):
        tile[6 * 4 + c] = _DC | (_DC << 4)
    # Row 7: blank
    for c in range(4):
        tile[7 * 4 + c] = _BG | (_BG << 4)
    return bytes(tile)


def _find_free_block(data: bytearray, size: int, min_offset: int = 0x100) -> int:
    """Find the first 4-byte-aligned run of 0xFF bytes of at least `size` bytes.

    Scans the whole ROM (after ``min_offset``) rather than only the trailing
    region, so it works even after other patches have consumed the tail.
    """
    i = min_offset
    rom_size = len(data)
    while i < rom_size:
        if data[i] != 0xFF:
            i += 1
            continue
        start = i
        while i < rom_size and data[i] == 0xFF:
            i += 1
        aligned = (start + 3) & ~3
        if i - aligned >= size:
            return aligned
    raise RuntimeError("Insufficient free space for title-screen version patch")


def _read_gba_ptr(data: bytearray, off: int) -> int:
    val = struct.unpack_from("<I", data, off)[0]
    if val < _GBA_BASE:
        raise ValueError(f"Not a valid GBA pointer at 0x{off:07X}: 0x{val:08X}")
    return val - _GBA_BASE


def _write_gba_ptr(data: bytearray, off: int, rom_addr: int) -> None:
    struct.pack_into("<I", data, off, rom_addr + _GBA_BASE)


def patch_title_screen_version(data: bytearray, build_number: int) -> bool:
    """Replace the title-screen version display with 'FR.2.0.<build_number>'.

    Returns True if the ROM was modified.
    """
    # Read current tileset and tilemap offsets from the pointer table
    ts_off = _read_gba_ptr(data, _TILESET_PTR_OFF)
    tm_off = _read_gba_ptr(data, _TILEMAP_PTR_OFF)

    # Decompress current tileset and tilemap
    result = _lz77_decompress(data, ts_off)
    if result is None:
        raise RuntimeError(f"Failed to decompress tileset at 0x{ts_off:07X}")
    tileset, _ = result
    num_tiles_orig = len(tileset) // 32

    result = _lz77_decompress(data, tm_off)
    if result is None:
        raise RuntimeError(f"Failed to decompress tilemap at 0x{tm_off:07X}")
    tilemap_bytes, _ = result
    tilemap = bytearray(tilemap_bytes)  # mutable copy

    # Build version string and split into pairs for tiles
    ver = f"FR.2.0.{build_number}"
    if len(ver) % 2:
        ver += " "
    pairs = [(ver[i], ver[i + 1]) for i in range(0, len(ver), 2)]

    # Create new tiles (appended after the existing tileset tiles)
    new_tile_data = b"".join(_make_char_tile(a, b) for a, b in pairs)
    new_tileset = tileset + new_tile_data

    # Tile indices for the new character tiles
    first_new_idx = num_tiles_orig
    tile_indices = list(range(first_new_idx, first_new_idx + len(pairs)))

    # Update tilemap: center the version string across cols 10-19
    num_ver_tiles = len(tile_indices)
    # Available: _VER_COL_COUNT slots.  Center the string.
    col_offset = (_VER_COL_COUNT - num_ver_tiles) // 2

    def _tm_entry_off(row: int, col: int) -> int:
        return (row * _TM_COLS + col) * 2

    for i in range(_VER_COL_COUNT):
        col = _VER_COL_START + i
        tile_i = i - col_offset
        entry_row2 = _tm_entry_off(_VER_ROW2, col)
        entry_row3 = _tm_entry_off(_VER_ROW3, col)

        if 0 <= tile_i < num_ver_tiles:
            # Character tile in row 2; blank floor in row 3
            struct.pack_into("<H", tilemap, entry_row2, tile_indices[tile_i] & 0x3FF)
            struct.pack_into("<H", tilemap, entry_row3, _BLANK_ROW3)
        else:
            # Blank in both rows
            struct.pack_into("<H", tilemap, entry_row2, _BLANK_ROW2)
            struct.pack_into("<H", tilemap, entry_row3, _BLANK_ROW3)

    # Compress both new datasets
    ts_compressed = _lz77_compress(new_tileset)
    tm_compressed = _lz77_compress(bytes(tilemap))

    # Align to 4-byte boundaries
    ts_padded = ts_compressed + b"\xFF" * ((-len(ts_compressed)) & 3)
    tm_padded = tm_compressed + b"\xFF" * ((-len(tm_compressed)) & 3)

    # Find a contiguous free block (0xFF) large enough for both datasets
    total = len(ts_padded) + len(tm_padded)
    cursor = _find_free_block(data, total)

    new_ts_off = cursor
    data[cursor:cursor + len(ts_padded)] = ts_padded
    cursor += len(ts_padded)

    new_tm_off = cursor
    data[cursor:cursor + len(tm_padded)] = tm_padded

    # Update the pointer table
    _write_gba_ptr(data, _TILESET_PTR_OFF, new_ts_off)
    _write_gba_ptr(data, _TILEMAP_PTR_OFF, new_tm_off)

    return True


# ---------------------------------------------------------------------------
# NOT FOR SALE intro screen patch
# ---------------------------------------------------------------------------


def patch_not_for_sale_version(data: bytearray) -> bool:
    """Remove 'v2.1.1.1' from the NOT FOR SALE intro screen.

    The NFS screen tilemap (shared by both background layers) has a version
    row (row 18) where seven specific tile entries render the version string.
    We copy the corresponding frame-decoration entries from row 16 into row 18
    so the version text vanishes into the surrounding box border.  Both tilemap
    pointers (0x260218 and 0x260220) are updated to the new location in free
    space.  Returns True if the ROM was modified.
    """
    tm_rom_off = _read_gba_ptr(data, _NFS_TILEMAP_PTR_A)
    result = _lz77_decompress(data, tm_rom_off)
    if result is None:
        raise RuntimeError(
            f"Failed to decompress NFS tilemap at 0x{tm_rom_off:07X}"
        )
    tilemap_bytes, _ = result
    tilemap = bytearray(tilemap_bytes)

    for col in _NFS_VER_COLS:
        frame_entry = struct.unpack_from("<H", tilemap, (16 * 32 + col) * 2)[0]
        struct.pack_into("<H", tilemap, (_NFS_VER_ROW * 32 + col) * 2, frame_entry)

    tm_compressed = _lz77_compress(bytes(tilemap))
    tm_padded = tm_compressed + b"\xFF" * ((-len(tm_compressed)) & 3)
    cursor = _find_free_block(data, len(tm_padded))
    data[cursor : cursor + len(tm_padded)] = tm_padded
    _write_gba_ptr(data, _NFS_TILEMAP_PTR_A, cursor)
    _write_gba_ptr(data, _NFS_TILEMAP_PTR_B, cursor)
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    parser.add_argument("--build-number", type=int, required=True,
                        help="CI build counter (e.g. GITHUB_RUN_NUMBER)")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"ROM not found: {args.rom}", file=sys.stderr)
        return 1

    data = bytearray(args.rom.read_bytes())

    if data[0xB2] != 0x96:
        print(f"Not a valid GBA ROM: {args.rom}", file=sys.stderr)
        return 1

    old_version = data[0xBC]
    header_changed = patch_version(data, args.build_number)

    try:
        screen_changed = patch_title_screen_version(data, args.build_number)
    except Exception as exc:
        print(f"Title-screen patch failed: {exc}", file=sys.stderr)
        return 1

    try:
        nfs_changed = patch_not_for_sale_version(data)
    except Exception as exc:
        print(f"NOT FOR SALE patch failed: {exc}", file=sys.stderr)
        return 1

    args.rom.write_bytes(data)

    if header_changed:
        print(
            f"Header patched: version 0x{old_version:02X} → 0x{args.build_number & 0xFF:02X} "
            f"(build #{args.build_number}), checksum 0xBD = 0x{_compute_checksum(data):02X}"
        )
    else:
        print(f"Header version already 0x{old_version:02X} — no change.")

    if screen_changed:
        print(f"Title screen: version display updated to 'FR.2.0.{args.build_number}'")

    if nfs_changed:
        print("NOT FOR SALE screen: version text erased (tilemap row 18 patched)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
