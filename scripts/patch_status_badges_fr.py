#!/usr/bin/env python3
"""Patch the fainted-status badge graphic from « FNT » / « DEB » to « KO ».

The status badges (PSN, SLP, BRN, FNT …) are stored as LZ77-compressed 4bpp
tile sets.  Each 32-tile block encodes 8 badge slots of 4 tiles each:
  [left_border_tile][content_tile1][content_tile2][right_border_tile]

The fainted badge lives at slot index 6 (tiles 24–27 inside the block).
Badge tile anatomy (8×8 px each, border color = palette idx 9):
  - Row 0 / Row 7: all palette-9 border pixels
  - Rows 1–6: letter pixels (color 2 = white) on bg color (color 14 = gray for FNT)

« KO » layout in the 16-px letter area (tiles 1+2 side by side):
  col  : 0  1  2  3  4  5  6  7 | 8  9  10 11 12 13 14 15
  role : m  K  K  K  K  .  O  O | O  O  m  m  m  m  m  m
where m = margin, . = separator, K/O = letter pixels.

K-letter pixel grid (4 wide × 6 tall):
  #..#   #.#.   ##..   #.#.   #..#   #..#

O-letter pixel grid (4 wide × 6 tall):
  .##.   #..#   #..#   #..#   #..#   .##.

This script MUST run AFTER repair_stable_lz77_blocks.py and
repair_localized_lz77_blocks.py so that block 0x0B1E11C is restored to the
English FNT tiles (stable block) and block 0x0B1E280 to the Spanish DEB tiles
(localized block) before we overwrite the fainted slot with « KO ».
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.patch_font_fr import lz77_compress, lz77_decompress  # noqa: E402

# LZ77 blocks that contain the 8-slot status badge tile set.
# All of these must have the fainted badge at slot 6 (tiles 24–27).
BADGE_BLOCKS: list[int] = [
    0x0B1E11C,   # stable EN block (restored by repair_stable_lz77_blocks.py)
    0x0B1E280,   # localized block (set to ES « DEB » by repair_localized_lz77_blocks.py)
    0x00E82EA0,  # secondary badge set (unchanged, holds EN FNT)
    0x00E9BF48,  # secondary badge set (unchanged, holds EN FNT)
]

# Tile indices of the fainted badge within the 32-tile block
_FNT_SLOT = 6
_TILE_BYTES = 32          # bytes per 4bpp 8×8 tile
_TILES_PER_BADGE = 4      # left_border + content1 + content2 + right_border
_CONTENT1_IDX = 1         # offset within badge: content tile 1
_CONTENT2_IDX = 2         # offset within badge: content tile 2

# Palette indices for the fainted badge
_BG  = 0xE   # gray background (palette 14)
_LET = 0x2   # white letter   (palette 2)
_BRD = 0x9   # border color   (palette 9)


def _encode_row(pixels: list[int]) -> bytes:
    """Pack 8 palette-index values into 4 bytes (4bpp little-endian nibbles)."""
    assert len(pixels) == 8
    return bytes([pixels[i] | (pixels[i + 1] << 4) for i in range(0, 8, 2)])


def _border_row() -> bytes:
    return _encode_row([_BRD] * 8)


def _bg_row_prefix() -> list[int]:
    """First 8 pixels of a badge row: margin + K + separator + O[:2]."""
    return []  # computed per row


# K-letter and O-letter column pixel grids (6 rows, 4 columns each)
# 2 = white (letter on), _BG = background (off)
_K: list[list[int]] = [
    [_LET, _BG,  _BG,  _LET],   # row 1: #..#
    [_LET, _BG,  _LET, _BG],    # row 2: #.#.
    [_LET, _LET, _BG,  _BG],    # row 3: ##..
    [_LET, _BG,  _LET, _BG],    # row 4: #.#.
    [_LET, _BG,  _BG,  _LET],   # row 5: #..#
    [_LET, _BG,  _BG,  _LET],   # row 6: #..#
]

_O: list[list[int]] = [
    [_BG,  _LET, _LET, _BG],    # row 1: .##.
    [_LET, _BG,  _BG,  _LET],   # row 2: #..#
    [_LET, _BG,  _BG,  _LET],   # row 3: #..#
    [_LET, _BG,  _BG,  _LET],   # row 4: #..#
    [_LET, _BG,  _BG,  _LET],   # row 5: #..#
    [_BG,  _LET, _LET, _BG],    # row 6: .##.
]


def _make_ko_tiles() -> tuple[bytes, bytes]:
    """Return (content_tile1, content_tile2) bytes for the KO badge."""
    t1 = bytearray()
    t2 = bytearray()

    t1.extend(_border_row())
    t2.extend(_border_row())

    for r in range(6):
        k = _K[r]   # 4 pixels
        o = _O[r]   # 4 pixels

        # Tile 1 (cols 0-7):
        # col0=margin, cols1-4=K, col5=sep, cols6-7=O[0:2]
        row1 = [_BG, k[0], k[1], k[2], k[3], _BG, o[0], o[1]]
        t1.extend(_encode_row(row1))

        # Tile 2 (cols 8-15):
        # cols8-9=O[2:4], cols10-15=right margin
        row2 = [o[2], o[3], _BG, _BG, _BG, _BG, _BG, _BG]
        t2.extend(_encode_row(row2))

    t1.extend(_border_row())
    t2.extend(_border_row())

    assert len(t1) == _TILE_BYTES
    assert len(t2) == _TILE_BYTES
    return bytes(t1), bytes(t2)


def _patch_block(rom: bytearray, offset: int, ko_t1: bytes, ko_t2: bytes) -> bool:
    """Decompress block at `offset`, replace fainted-slot content tiles, recompress."""
    result = lz77_decompress(rom, offset)
    if result is None:
        print(f"  WARN 0x{offset:08X}: failed to decompress — skip", file=sys.stderr)
        return False

    decompressed, comp_len = result
    if len(decompressed) < 32 * _TILE_BYTES:
        print(
            f"  WARN 0x{offset:08X}: decompressed size {len(decompressed)} < 1024 — skip",
            file=sys.stderr,
        )
        return False

    tiles = bytearray(decompressed)
    slot_base = _FNT_SLOT * _TILES_PER_BADGE * _TILE_BYTES
    c1_off = slot_base + _CONTENT1_IDX * _TILE_BYTES
    c2_off = slot_base + _CONTENT2_IDX * _TILE_BYTES

    # Verify the badge has the expected background and border colours
    bg_sample = tiles[c1_off + 4]   # first byte of row 1 (should be bg nibble)
    brd_sample = tiles[c1_off]       # first byte of row 0 (should be all-border)
    actual_bg = bg_sample & 0xF
    actual_brd = brd_sample & 0xF
    if actual_brd != _BRD or actual_bg not in (_BG, _LET):
        print(
            f"  WARN 0x{offset:08X}: unexpected palette at slot {_FNT_SLOT} "
            f"(border={actual_brd:#x}, bg={actual_bg:#x}) — patching anyway",
            file=sys.stderr,
        )

    tiles[c1_off : c1_off + _TILE_BYTES] = ko_t1
    tiles[c2_off : c2_off + _TILE_BYTES] = ko_t2

    compressed = lz77_compress(bytes(tiles))
    if offset + len(compressed) > len(rom):
        print(
            f"  WARN 0x{offset:08X}: recompressed size {len(compressed)} overflows ROM — skip",
            file=sys.stderr,
        )
        return False

    # Only write if the compressed block fits within the original compressed area
    if len(compressed) > comp_len:
        extra = rom[offset + comp_len : offset + len(compressed)]
        if any(b not in (0x00, 0xFF) for b in extra):
            print(
                f"  WARN 0x{offset:08X}: recompressed ({len(compressed)}) > original "
                f"({comp_len}) and tail is non-padding — skip",
                file=sys.stderr,
            )
            return False

    rom[offset : offset + len(compressed)] = compressed
    return True


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    ko_t1, ko_t2 = _make_ko_tiles()
    rom = bytearray(rom_path.read_bytes())
    patched = 0

    for block_off in BADGE_BLOCKS:
        if block_off >= len(rom):
            print(f"  SKIP 0x{block_off:08X}: beyond ROM end", file=sys.stderr)
            continue
        if dry_run:
            result = lz77_decompress(rom, block_off)
            ok = result is not None and len(result[0]) >= 32 * _TILE_BYTES
            print(f"  {'OK' if ok else 'FAIL'} 0x{block_off:08X} (dry-run)")
            if ok:
                patched += 1
            continue
        ok = _patch_block(rom, block_off, ko_t1, ko_t2)
        if ok:
            print(f"  0x{block_off:08X}  FNT/DEB → KO")
            patched += 1

    if not dry_run and patched:
        rom_path.write_bytes(rom)
    return patched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = apply_patches(args.rom, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_status_badges_fr: {n} block(s) patched{suffix}")


if __name__ == "__main__":
    main()
