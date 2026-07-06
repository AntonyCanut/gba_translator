#!/usr/bin/env python3
"""Translate the START-menu reorder hint « Move » → « Dépl. » (GitHub #43).

Pressing START in Pokemon Unbound opens a custom icon-bar menu.  A hint bar at
the bottom shows the SELECT-button keycap followed by the word « Move » (press
SELECT to *move* / reorder the icons).  That word is NOT text read from any
string table — it is baked, pixel-for-pixel, into an LZ77-compressed 4bpp tile
graphic (the same class as the type-icon badges and HP/PS labels).  So no
`combined_fr.txt` entry can touch it; it must be redrawn in the graphic.

The hint graphic lives at ROM offset 0x0B1BBE0 (LZ77, 15 tiles), referenced by
a pointer at 0x0A0C210 in the start-menu code.  Its tile layout:

    tiles 0-7   : window/frame border pieces
    tiles 8-11  : the « SELECT » keycap  (left untouched)
    tiles 12-14 : the word « Move »       (24 px, redrawn to « Dépl. »)

The letters use a bold beveled font: a light fill (palette index 0x0F) with a
dark bottom-right bevel/outline (0x0E), sitting on the bar's vertical gradient
background (indices 1,2,3,4 top→bottom, 2 rows per step — copied verbatim from
the untouched background tile 8 so « Dépl. » blends in exactly like « Move »).

« Dépl. » (5 glyphs) is drawn in the same 24-px space « Move » occupied.  The
glyphs are hand-built to match the font's weight/height; the « é » reuses the
« e » body with the game's compact acute accent.  Idempotent: re-running redraws
the same French pixels.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import lz77_compress, lz77_decompress  # noqa: E402

GFX_OFFSET = 0x0B1BBE0        # LZ77 hint-bar graphic
POINTER_OFFSET = 0x0A0C210    # 32-bit pointer (0x08B1BBE0) into the graphic
_TILE_BYTES = 32
_FIRST_MOVE_TILE = 12         # « Move » occupies tiles 12,13,14
_N_MOVE_TILES = 3
_WIDTH = _N_MOVE_TILES * 8    # 24 px canvas

_FILL = 0x0F                  # light letter body
_BEVEL = 0x0E                 # dark bottom-right bevel/outline

# ── Glyph fill masks (True = light-fill pixel).  Rows are 7 tall (the font body
# sits on rows 1-7 of the 8-row tile, matching « Move »). ────────────────────
_F, _o = True, False

# Thin 1-px-stroke fill masks (7 rows).  Capitals span all 7 rows; lowercase
# letters keep their top rows empty so they sit at x-height like « ove ».  The
# dark bevel is added programmatically to the right/below of each fill pixel.
_GLYPHS: dict[str, list[list[bool]]] = {
    # D — capital, 4 px, full height
    "D": [
        [_F, _F, _F, _o],
        [_F, _o, _o, _F],
        [_F, _o, _o, _F],
        [_F, _o, _o, _F],
        [_F, _o, _o, _F],
        [_F, _o, _o, _F],
        [_F, _F, _F, _o],
    ],
    # e — lowercase, 4 px, x-height (rows 1-6); body reused for « é »
    "e": [
        [_o, _o, _o, _o],
        [_o, _F, _F, _o],
        [_F, _o, _o, _F],
        [_F, _F, _F, _F],
        [_F, _o, _o, _o],
        [_F, _o, _o, _F],
        [_o, _F, _F, _o],
    ],
    # p — lowercase, 4 px, bowl at x-height + short stem
    "p": [
        [_o, _o, _o, _o],
        [_F, _F, _F, _o],
        [_F, _o, _o, _F],
        [_F, _o, _o, _F],
        [_F, _F, _F, _o],
        [_F, _o, _o, _o],
        [_F, _o, _o, _o],
    ],
    # l — lowercase, 1 px stem, full height
    "l": [
        [_F],
        [_F],
        [_F],
        [_F],
        [_F],
        [_F],
        [_F],
    ],
    # . — full stop, 1 px, bottom only
    ".": [
        [_o],
        [_o],
        [_o],
        [_o],
        [_o],
        [_F],
        [_o],
    ],
}

# Compact acute accent for « é » (row 0, above the e body).
_ACUTE = [(2, 0), (1, 1)]  # (x, y) fill pixels relative to the glyph's left edge


def _bevel(mask: list[list[int]]) -> None:
    """Add a dark bevel (0x0E) to the right and below every fill pixel that is
    currently empty — gives the letters the font's bold 3-D edge."""
    h = len(mask)
    w = len(mask[0])
    fills = [(y, x) for y in range(h) for x in range(w) if mask[y][x] == _FILL]
    for (y, x) in fills:
        for dy, dx in ((0, 1), (1, 0), (1, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and mask[ny][nx] == 0:
                mask[ny][nx] = _BEVEL


def _render_deplacer() -> list[list[int]]:
    """Compose « Dépl. » onto a 24x8 canvas of palette indices.

    Returns an 8-row x 24-col grid where 0 = keep background gradient, else the
    letter fill/bevel index."""
    canvas = [[0] * _WIDTH for _ in range(8)]

    # (glyph, is_accented) laid out left-to-right with 1px gaps.
    layout = [("D", False), ("e", True), ("p", False), ("l", False), (".", False)]
    x = 0
    for name, accent in layout:
        g = _GLYPHS[name]
        gh, gw = len(g), len(g[0])
        for gy in range(gh):
            for gx in range(gw):
                if g[gy][gx]:
                    cx = x + gx
                    if cx < _WIDTH:
                        canvas[gy + 1][cx] = _FILL   # body sits on rows 1-7
        if accent:
            for (ax, ay) in _ACUTE:
                cx = x + ax
                if cx < _WIDTH:
                    canvas[ay][cx] = _FILL
        x += gw + 1

    # Bevel the whole composed word (right + below).
    for y in range(8):
        for xx in range(_WIDTH):
            if canvas[y][xx] == _FILL:
                for dy, dx in ((0, 1), (1, 0), (1, 1)):
                    ny, nx = y + dy, xx + dx
                    if 0 <= ny < 8 and 0 <= nx < _WIDTH and canvas[ny][nx] == 0:
                        canvas[ny][nx] = _BEVEL
    return canvas


def _bg_gradient_row(y: int) -> int:
    """Background gradient index for row y (2 rows per step: 1,1,2,2,3,3,4,4)."""
    return 1 + y // 2


def _compose_tiles(bg_tile8: bytes) -> list[bytes]:
    """Return the 3 redrawn « Dépl. » tiles (12,13,14)."""
    canvas = _render_deplacer()
    tiles: list[bytes] = []
    for t in range(_N_MOVE_TILES):
        pixels = [0] * 64
        for y in range(8):
            for x in range(8):
                v = canvas[y][t * 8 + x]
                pixels[y * 8 + x] = v if v else _bg_gradient_row(y)
        out = bytearray()
        for i in range(0, 64, 2):
            out.append((pixels[i] & 0xF) | ((pixels[i + 1] & 0xF) << 4))
        tiles.append(bytes(out))
    return tiles


def apply_patch(rom: bytearray, dry_run: bool = False) -> bool:
    result = lz77_decompress(rom, GFX_OFFSET)
    if result is None:
        print(f"  WARN 0x{GFX_OFFSET:08X}: not LZ77 — skip", file=sys.stderr)
        return False
    dec, comp_len = result
    if len(dec) < 15 * _TILE_BYTES:
        print(f"  WARN 0x{GFX_OFFSET:08X}: only {len(dec)} bytes — skip", file=sys.stderr)
        return False

    tiles = bytearray(dec)
    bg8 = bytes(tiles[8 * _TILE_BYTES: 9 * _TILE_BYTES])
    new_tiles = _compose_tiles(bg8)
    for i, tile in enumerate(new_tiles):
        off = (_FIRST_MOVE_TILE + i) * _TILE_BYTES
        tiles[off: off + _TILE_BYTES] = tile

    if dry_run:
        print(f"  OK 0x{GFX_OFFSET:08X}: « Move » → « Dépl. » (dry-run)")
        return True

    compressed = lz77_compress(bytes(tiles))
    if len(compressed) <= comp_len:
        # fits in the original slot: overwrite in place, pad tail with 0x00
        rom[GFX_OFFSET: GFX_OFFSET + len(compressed)] = compressed
        for i in range(GFX_OFFSET + len(compressed), GFX_OFFSET + comp_len):
            rom[i] = 0x00
        print(f"  0x{GFX_OFFSET:08X}: « Move » → « Dépl. » (in place, "
              f"{len(compressed)}/{comp_len} bytes)")
        return True

    # recompressed larger — relocate and repoint (rare)
    from languages.fr.patches.font import FreeSpaceAllocator  # local import
    alloc = FreeSpaceAllocator(rom)
    new_off = alloc.allocate(len(compressed))
    rom[new_off: new_off + len(compressed)] = compressed
    ptr = (0x08000000 + new_off).to_bytes(4, "little")
    rom[POINTER_OFFSET: POINTER_OFFSET + 4] = ptr
    print(f"  0x{GFX_OFFSET:08X}: « Move » → « Dépl. » (relocated to "
          f"0x{new_off:08X}, {len(compressed)} bytes, repointed 0x{POINTER_OFFSET:08X})")
    return True


def render_preview(rom_path: Path, out_png: Path) -> None:
    """Render the new « Dépl. » tiles next to the SELECT keycap for visual check."""
    import struct
    from PIL import Image  # type: ignore
    rom = bytearray(rom_path.read_bytes())
    dec, _ = lz77_decompress(rom, GFX_OFFSET)
    tiles = bytearray(dec)
    for i, tile in enumerate(_compose_tiles(bytes(tiles[8 * 32: 9 * 32]))):
        off = (_FIRST_MOVE_TILE + i) * _TILE_BYTES
        tiles[off: off + _TILE_BYTES] = tile
    pal = Path("output/proofs/startmenu-vram/pal.bin").read_bytes()
    palrow = 13
    def rgb(hw: int) -> tuple[int, int, int]:
        return ((hw & 0x1f) << 3, ((hw >> 5) & 0x1f) << 3, ((hw >> 10) & 0x1f) << 3)
    palr = [rgb(struct.unpack('<H', pal[(palrow * 16 + i) * 2:(palrow * 16 + i) * 2 + 2])[0]) for i in range(16)]
    img = Image.new('RGB', (7 * 8, 8), (255, 0, 255))
    for ti, t in enumerate(range(8, 15)):
        for y in range(8):
            for x in range(0, 8, 2):
                b = tiles[t * 32 + y * 4 + x // 2]
                for k, c in enumerate((b & 0xf, (b >> 4) & 0xf)):
                    img.putpixel((ti * 8 + x + k, y), palr[c])
    img.resize((7 * 8 * 16, 8 * 16), Image.NEAREST).save(out_png)
    print(f"preview -> {out_png}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--preview", type=Path, help="render preview PNG (no ROM write)")
    args = ap.parse_args()

    if args.preview:
        render_preview(args.rom, args.preview)
        return

    rom = bytearray(args.rom.read_bytes())
    ok = apply_patch(rom, dry_run=args.dry_run)
    if ok and not args.dry_run:
        args.rom.write_bytes(rom)
    print(f"patch_start_menu_move_hint_fr: {'1' if ok else '0'} block patched"
          f"{' (dry-run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
