#!/usr/bin/env python3
"""Static ROM sprite locator — find/render 4bpp UI tile graphics WITHOUT mGBA.

Built for the "locate the CANCEL/ANNUL. button sprite" line of tickets
(F-108 → F-109 → F-110 → …). Those tickets kept stalling on the same wall:
blind mGBA navigation to the (wrongly assumed) screen. This tool sidesteps the
emulator entirely — it reads the built ROM and hunts for button-shaped tile
graphics by structure, so a human only has to eyeball a handful of rendered
candidates instead of walking a maze tile-by-tile.

It has three modes:

  render   Dump an arbitrary byte range as a grid of 4bpp 8x8 tiles to a BMP,
           for either raw (uncompressed) tiles or an LZ77-compressed block.
           Use this to inspect a region you already suspect.

  buttons  Scan (raw ROM and/or every LZ77 block in a region) for the
           "text button" structure the F-108 .bmp files have: a rectangular
           4bpp sprite with a uniform background margin around a centred text
           band. Emits a contact-sheet BMP + a list of offsets.

  text     Looser scan: any 4x2-tile window whose middle rows read like text
           (several ink groups separated by inter-letter gaps, over a
           dominant background). Noisier, but catches labels packed inside a
           bigger multi-label sheet (where there's no blank top margin).

Only depends on the stdlib + the LZ77 / tile helpers already in
``languages/fr/patches/font.py`` — no numpy, no Pillow (the project's sole
third-party dep is pyyaml). Convert the emitted .bmp to PNG with
``sips -s format png x.bmp --out x.png`` (macOS) or any image tool.

Examples
--------
    # look at the naming-keyboard "selection" sprite (raw, 5x13 tiles):
    python3 scripts/scan_sprite_region.py render 0x00E985D8 --tiles-wide 5 \
        --count 65 -o /tmp/selection.bmp

    # hunt for a text button in the UI OBJ graphics region:
    python3 scripts/scan_sprite_region.py buttons --start 0x00E00000 \
        --end 0x00F00000 -o /tmp/cands.bmp
"""

from __future__ import annotations

import argparse
import struct
import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from languages.fr.patches.font import (  # noqa: E402
    lz77_decompress,
    tile_to_pixels,
)

TILE_BYTES = 32
TILE_PX = 8
Grid = List[List[int]]

DEFAULT_ROM = ROOT / "output" / "roms" / "GenedRom-fr.gba"


# --------------------------------------------------------------------------- #
# tiny 4bpp indexed-BMP writer (self-contained; no dep on src/graphics)
# --------------------------------------------------------------------------- #
def write_bmp(path: Path, grid: Grid, palette: Optional[List[Tuple[int, int, int]]] = None) -> None:
    height = len(grid)
    width = len(grid[0]) if height else 0
    if palette is None:
        # index 0 -> black, then a light ramp so glyph shading stays visible
        palette = [(0, 0, 0)] + [(50 + i * 13,) * 3 for i in range(1, 16)]
    row_bytes = (width + 1) // 2
    stride = (row_bytes + 3) & ~3
    img_size = stride * height
    off_bits = 14 + 40 + 16 * 4
    file_header = struct.pack("<2sIHHI", b"BM", off_bits + img_size, 0, 0, off_bits)
    info_header = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 4, 0,
                              img_size, 2835, 2835, 16, 0)
    pal = b"".join(struct.pack("<BBBB", b, g, r, 0) for (r, g, b) in palette)
    body = bytearray(img_size)
    for y in range(height):
        src = grid[height - 1 - y]
        base = y * stride
        for x in range(width):
            v = src[x] & 0xF
            off = base + x // 2
            body[off] |= (v << 4) if x % 2 == 0 else v
    path.write_bytes(file_header + info_header + pal + bytes(body))


# --------------------------------------------------------------------------- #
# tile <-> grid
# --------------------------------------------------------------------------- #
def tiles_to_grid(data: bytes, start_tile: int, tiles_wide: int, tiles_tall: int) -> Grid:
    w, h = tiles_wide * TILE_PX, tiles_tall * TILE_PX
    grid: Grid = [[0] * w for _ in range(h)]
    for ty in range(tiles_tall):
        for tx in range(tiles_wide):
            i = start_tile + ty * tiles_wide + tx
            px = tile_to_pixels(data[i * TILE_BYTES:(i + 1) * TILE_BYTES])
            for r in range(TILE_PX):
                grid[ty * TILE_PX + r][tx * TILE_PX:tx * TILE_PX + TILE_PX] = px[r * TILE_PX:r * TILE_PX + TILE_PX]
    return grid


def window_4x2(data: bytes, tile_index: int) -> Grid:
    """The 32x16 grid of the 4-wide x 2-tall sprite starting at *tile_index*."""
    return tiles_to_grid(data, tile_index, 4, 2)


# --------------------------------------------------------------------------- #
# scans
# --------------------------------------------------------------------------- #
def is_margin_button(g: Grid) -> bool:
    """The F-108 .bmp layout: >=4 uniform bg rows on top, >=3 on bottom, a
    uniform left/right margin, and a text band spanning most of the width."""
    v = g[0][0]
    for r in range(5):
        if any(p != v for p in g[r]):
            return False
    for r in range(13, 16):
        if any(p != v for p in g[r]):
            return False
    if any(g[r][0] != v or g[r][31] != v for r in range(16)):
        return False
    band = [(r, c) for r in range(5, 13) for c in range(32) if g[r][c] != v]
    if not 40 <= len(band) <= 175:
        return False
    cols = {c for _, c in band}
    return (any(2 <= c < 10 for c in cols) and any(10 <= c < 18 for c in cols)
            and any(18 <= c < 26 for c in cols))


def looks_like_text(g: Grid) -> bool:
    """Looser: dominant background + a middle band with several ink groups
    separated by inter-letter gaps. Catches labels with no blank top margin."""
    cnt = Counter(p for row in g for p in row)
    v, vn = cnt.most_common(1)[0]
    if vn < 16 * 32 * 0.45:
        return False
    seg = [any(g[r][c] != v for r in range(2, 14)) for c in range(1, 31)]
    idxs = [k for k, x in enumerate(seg) if x]
    if not idxs:
        return False
    groups = sum(1 for k in range(len(seg)) if seg[k] and (k == 0 or not seg[k - 1]))
    ink = sum(seg)
    lo, hi = idxs[0], idxs[-1]
    interior_gaps = sum(1 for k in range(lo, hi + 1) if not seg[k])
    return groups >= 4 and 10 <= ink <= 27 and interior_gaps >= 3 and (hi - lo) >= 14


def iter_blocks(rom: bytes, start: int, end: int):
    """Yield ``(kind, header_off, data)`` for the raw slice and every plausible
    LZ77 block in ``[start, end)``. ``kind`` is 'raw' or 'lz'."""
    yield "raw", start, rom[start:end]
    for i in range(start, min(end, len(rom) - 4)):
        if rom[i] != 0x10:
            continue
        size = rom[i + 1] | (rom[i + 2] << 8) | (rom[i + 3] << 16)
        if not (256 <= size <= 16384 and size % 32 == 0):
            continue
        try:
            res = lz77_decompress(rom, i)
        except Exception:
            continue
        if res is not None:
            yield "lz", i, res[0]


def scan(rom: bytes, start: int, end: int, predicate) -> List[Tuple[str, int, int, Grid]]:
    hits: List[Tuple[str, int, int, Grid]] = []
    for kind, header, data in iter_blocks(rom, start, end):
        n = len(data) // TILE_BYTES
        for j in range(n - 7):
            g = window_4x2(data, j)
            if predicate(g):
                hits.append((kind, header, j * TILE_BYTES, g))
    return hits


def contact_sheet(hits, path: Path) -> None:
    if not hits:
        return
    gap, per, colw = 3, 16 + 3, 34
    half = (len(hits) + 1) // 2
    height = half * per
    sheet: Grid = [[0] * (colw * 2) for _ in range(height)]
    for i, (_, _, _, g) in enumerate(hits):
        col, row = i // half, i % half
        for r in range(16):
            sheet[row * per + r][col * colw:col * colw + 32] = g[r]
    write_bmp(path, sheet)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _int(s: str) -> int:
    return int(s, 0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="dump a byte range as a tile BMP")
    r.add_argument("offset", type=_int)
    r.add_argument("--tiles-wide", type=int, default=16)
    r.add_argument("--count", type=int, default=256, help="number of tiles")
    r.add_argument("--lz", action="store_true", help="offset is an LZ77 block")
    r.add_argument("-o", "--out", type=Path, required=True)

    for name, help_ in (("buttons", "scan for margin-framed text buttons"),
                        ("text", "scan for any text-like 4x2 window")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--start", type=_int, default=0x00800000)
        s.add_argument("--end", type=_int, default=0x00F00000)
        s.add_argument("-o", "--out", type=Path, default=Path("/tmp/sprite_cands.bmp"))

    a = ap.parse_args()
    rom = a.rom.read_bytes()

    if a.cmd == "render":
        if a.lz:
            res = lz77_decompress(rom, a.offset)
            if res is None:
                sys.exit(f"0x{a.offset:08X}: not an LZ77 block")
            data, base = res[0], 0
        else:
            # raw sprites are addressed by exact byte offset (not necessarily
            # ROM-tile-aligned, e.g. the naming "selection" sheet at 0xE985D8).
            data, base = rom[a.offset:], 0
        tall = (a.count + a.tiles_wide - 1) // a.tiles_wide
        grid = tiles_to_grid(data, base, a.tiles_wide, tall)
        write_bmp(a.out, grid)
        print(f"wrote {a.out} ({a.tiles_wide * 8}x{tall * 8})")
        return

    predicate = is_margin_button if a.cmd == "buttons" else looks_like_text
    hits = scan(rom, a.start, a.end, predicate)
    print(f"{a.cmd}: {len(hits)} candidate(s) in [0x{a.start:08X}, 0x{a.end:08X})")
    for kind, header, off, _ in hits[:200]:
        where = f"raw @0x{header + off:08X}" if kind == "raw" else f"lz block 0x{header:08X} +0x{off:X}"
        print(f"  {where}")
    contact_sheet(hits, a.out)
    if hits:
        print(f"contact sheet -> {a.out}")


if __name__ == "__main__":
    main()
