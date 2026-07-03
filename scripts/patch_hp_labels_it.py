#!/usr/bin/env python3
"""Patch every HP/PS label graphic to the official Italian « PS » (Punti Salute).

Sibling of ``patch_hp_labels_fr.py`` / ``patch_hp_labels_de.py`` — identical
LZ77 block layout and verification machinery, different letters. The P glyph
is reused verbatim from the in-game-verified French « PV » art (P is the
first letter of both « PV » and « PS »); only the S is new. Three label
graphics show the hit-point abbreviation in-game; none of them is text (they
are 4bpp tiles inside LZ77 blocks), so the translation pipeline never touches
them:

1. Party-menu label (CFRU custom party screen) — LZ77 block 0x008001D0.
   The green « HP » is drawn across four tiles of an 8-tile-wide sheet:
   tiles 51/52 rows 5-7 + tiles 59/60 rows 0-2 (bold letters, bg=6,
   outline=0xE, fill=0xF). Columns 14-15 hold the HP-bar left cap and the
   surrounding tiles hold the box border — only the label area is redrawn.

2. Summary-screen bar label (sprite) — LZ77 block 0x00E9B4B8, tiles 9-10.
   The EN ROM has « HP », the ES ROM « PS »; ``repair_localized_lz77_blocks``
   copies the Spanish tiles into the generic (IT) build, so before this patch
   the summary already shows the Spanish « PS » art. Redrawn with a matching
   Italian « PS » (bold 5-row letters, bg=0, outline=0xF, fill=0x4) so all
   three blocks share one consistent font instead of mixing the ES sprite
   with the EN party/grey labels.

3. Summary-screen grey stat label — LZ77 block 0x00E9A460 (the word-image
   tileset also holding ATTACK/DEFENSE/…), tiles 100/101 + 116/117.
   Thin « HP » letters (color 1) inside a grey oval (color 7) — redrawn as
   thin « PS » letters, oval untouched.

All three patches are strict: the current label tiles must byte-match a known
variant (EN « HP » / ES « PS ») or the already-patched « PS »; anything else
is reported and skipped rather than corrupted. Recompression is in-place with
the same padding-tail tolerance used by patch_status_badges_de.

Runs in the generic ``build_language.py it`` chain AFTER repair_lz77/
repair_localized_lz77 (so it wins over both) — see languages/it/lang.yaml.

Usage::

    python3 scripts/patch_hp_labels_it.py --rom output/roms/GenedRom-it.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.patch_font_fr import lz77_compress, lz77_decompress  # noqa: E402

TILE = 32  # bytes per 4bpp 8×8 tile


# ---------------------------------------------------------------------------
# 4bpp pixel helpers (leftmost pixel = low nibble)
# ---------------------------------------------------------------------------

def _px_get(tiles: bytearray, tile: int, row: int, col: int) -> int:
    b = tiles[tile * TILE + row * 4 + col // 2]
    return b & 0xF if col % 2 == 0 else b >> 4


def _px_set(tiles: bytearray, tile: int, row: int, col: int, val: int) -> None:
    off = tile * TILE + row * 4 + col // 2
    b = tiles[off]
    if col % 2 == 0:
        tiles[off] = (b & 0xF0) | val
    else:
        tiles[off] = (b & 0x0F) | (val << 4)


def _outline(fill: set[tuple[int, int]], nrows: int, ncols: int) -> set[tuple[int, int]]:
    """Cells orthogonally adjacent to a fill cell (the 1px letter outline)."""
    out = set()
    for r, c in fill:
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < nrows and 0 <= cc < ncols and (rr, cc) not in fill:
                out.add((rr, cc))
    return out


# ---------------------------------------------------------------------------
# Label definitions — Italian « PS »
# ---------------------------------------------------------------------------

# ── 1. Party menu (block 0x008001D0) ────────────────────────────────────────
PARTY_BLOCK = 0x008001D0
# The 16×6 px label area, as (left_tile, right_tile, row_within_tile) per line.
PARTY_ROWS: list[tuple[int, int, int]] = [
    (51, 52, 5), (51, 52, 6), (51, 52, 7),
    (59, 60, 0), (59, 60, 1), (59, 60, 2),
]
PARTY_NCOLS = 14           # cols 14-15 = HP-bar left cap, must stay untouched
PARTY_BG, PARTY_OUT, PARTY_FILL = 0x6, 0xE, 0xF

# New « PS » (bold, 4 fill rows — same geometry/height as the EN « HP »).
# P reused verbatim from the FR « PV » art (cols 2-6); S is new (cols 8-12,
# same slot the DE « KP » K and FR « PV » V occupy): full top/bottom bars,
# upper-left then lower-right stem — the classic compact-S "opposite
# corners" stroke pattern (a Z instead uses upper-right/lower-left).
PARTY_PS_FILL: set[tuple[int, int]] = (
    # P: cols 2-6
    {(1, c) for c in range(2, 7)} | {(2, 2), (2, 3), (2, 5), (2, 6)}
    | {(3, c) for c in range(2, 7)} | {(4, 2), (4, 3)}
    # S: cols 8-12
    | {(1, c) for c in range(8, 13)} | {(2, 8)}
    | {(3, 12)} | {(4, c) for c in range(8, 13)}
)

# Known-good current bytes of tiles 51/52/59/60 (EN « HP », identical in the
# generic build since the block is EN==ES stable and restored by repair_lz77).
PARTY_OLD_TILES: dict[int, str] = {
    51: "666666666666666666666666666666666666666666eee66ee6fffeefe6ffffef",
    52: "6666666666666666666666666666666666666666eeee6e66ffffefe6fffeefe6",
    59: "e6ffffefe6fffeef66eee66e6666666666666666666666666666666666666666",
    60: "ffffefe6ffee6e66ee6666666666666666666666666666666666666666666666",
}

# ── 2. Summary green bar label sprite (block 0x00E9B4B8) ────────────────────
GREEN_BLOCK = 0x00E9B4B8
GREEN_TILES = (9, 10)
GREEN_BG, GREEN_OUT, GREEN_FILL = 0x0, 0xF, 0x4

# New « PS » (bold, 5 fill rows — same geometry/height as the ES « PS »).
# P reused verbatim from the FR « PV » art (cols 3-7); S is new (cols 9-13):
# full top/middle/bottom bars with a left stem under the top and a right stem
# above the bottom — the standard 5-row bold S skeleton.
GREEN_PS_FILL: set[tuple[int, int]] = (
    # P: cols 3-7
    {(1, c) for c in range(3, 8)} | {(2, 3), (2, 4), (2, 6), (2, 7)}
    | {(3, c) for c in range(3, 8)} | {(4, 3), (4, 4)} | {(5, 3), (5, 4)}
    # S: cols 9-13
    | {(1, c) for c in range(9, 14)} | {(2, 9)}
    | {(3, c) for c in range(9, 14)} | {(4, 13)}
    | {(5, c) for c in range(9, 14)}
)

GREEN_OLD_VARIANTS: dict[str, dict[int, str]] = {
    "ES « PS »": {
        9: "00fffffff04f4444f04ff444f04f4444f04ff4fff04ff4ff00ffffff00000000",
        10: "ffffff0f4f4444ff4ff4ffff4f4444ffffff44ff4f4444ffffffff0f00000000",
    },
    "EN « HP »": {
        9: "00fff00ff0444ff4f04444f4f04444f4f0444ff400fff00f0000000000000000",
        10: "ffff0f004444f400444ff4f04444f4f044ff0ff0ff0000000000000000000000",
    },
}

# ── 3. Summary grey stat label (block 0x00E9A460) ───────────────────────────
GREY_BLOCK = 0x00E9A460
# 16×16 px area: tiles 100/101 (grid rows 0-7) over 116/117 (grid rows 8-15)
GREY_ROWS: list[tuple[int, int, int]] = (
    [(100, 101, r) for r in range(8)] + [(116, 117, r) for r in range(8)]
)
GREY_LETTER, GREY_OVAL = 0x1, 0x7
GREY_ERASE_ROWS = range(3, 10)      # letter rows inside the oval
GREY_ERASE_COLS = range(3, 14)

# New thin « PS » (letters 7 rows tall, 1px strokes, no outline). P reused
# verbatim from the FR « PV » art (stem col 4 + bowl cols 5-7); S is new
# (cols 9-12): a thin zig-zag stroke tracing top → left → middle → right →
# bottom, mirroring the same "opposite corners" S skeleton used above.
GREY_PS_FILL: set[tuple[int, int]] = (
    # P: vertical col 4 + bowl cols 5-7
    {(r, 4) for r in range(3, 10)}
    | {(3, 5), (3, 6), (4, 7), (5, 7), (6, 5), (6, 6)}
    # S: cols 9-12
    | {(3, 10), (3, 11), (3, 12)}
    | {(4, 9)}
    | {(5, 9)}
    | {(6, 9), (6, 10), (6, 11)}
    | {(7, 12)}
    | {(8, 12)}
    | {(9, 9), (9, 10), (9, 11)}
)

GREY_OLD_TILES: dict[int, str] = {
    100: "99999999aaaaaaaaaa7a7777aa7a71177a777117777771177777111177777117",
    101: "99999999aaaaaaaa7777a7aa171177aa177771a7177771771711777717777777",
    116: "777771177a777117aa7a7777aaaaaaaa99999999aaaaaaaaaaaaaaaaaaaaaaaa",
    117: "17777777177777a777a7aaaaaaaaaaaa99999999aaaaaaaaaaaaaaaaaaaaaaaa",
}


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _draw_party_label(tiles: bytearray) -> None:
    fill = PARTY_PS_FILL
    outline = _outline(fill, len(PARTY_ROWS), PARTY_NCOLS)
    for gr, (tl, tr, row) in enumerate(PARTY_ROWS):
        for gc in range(PARTY_NCOLS):
            tile = tl if gc < 8 else tr
            col = gc % 8
            cur = _px_get(tiles, tile, row, col)
            if (gr, gc) in fill:
                val = PARTY_FILL
            elif (gr, gc) in outline:
                val = PARTY_OUT
            elif cur in (PARTY_OUT, PARTY_FILL):
                val = PARTY_BG            # erase leftover old letter pixel
            else:
                continue                  # box border / background: keep
            _px_set(tiles, tile, row, col, val)


def _draw_green_label(tiles: bytearray) -> None:
    fill = GREEN_PS_FILL
    outline = _outline(fill, 8, 16)
    for tile in GREEN_TILES:
        start = tile * TILE
        tiles[start:start + TILE] = b"\x00" * TILE
    for gr in range(8):
        for gc in range(16):
            if (gr, gc) in fill:
                val = GREEN_FILL
            elif (gr, gc) in outline:
                val = GREEN_OUT
            else:
                continue
            tile = GREEN_TILES[0] if gc < 8 else GREEN_TILES[1]
            _px_set(tiles, tile, gr, gc % 8, val)


def _draw_grey_label(tiles: bytearray) -> None:
    # erase the old thin letters inside the oval
    for gr in GREY_ERASE_ROWS:
        tl, tr, row = GREY_ROWS[gr]
        for gc in GREY_ERASE_COLS:
            tile = tl if gc < 8 else tr
            if _px_get(tiles, tile, row, gc % 8) == GREY_LETTER:
                _px_set(tiles, tile, row, gc % 8, GREY_OVAL)
    # draw the new ones
    for gr, gc in GREY_PS_FILL:
        tl, tr, row = GREY_ROWS[gr]
        tile = tl if gc < 8 else tr
        _px_set(tiles, tile, row, gc % 8, GREY_LETTER)


# ---------------------------------------------------------------------------
# Patch driver
# ---------------------------------------------------------------------------

def _tiles_hex(tiles: bytearray, indices) -> dict[int, str]:
    return {t: bytes(tiles[t * TILE:(t + 1) * TILE]).hex() for t in indices}


def _expected_new(old_tiles: dict[int, str], draw) -> dict[int, str]:
    """Apply *draw* to a buffer holding the known old tiles, return new hex."""
    max_tile = max(old_tiles)
    buf = bytearray((max_tile + 1) * TILE)
    for t, h in old_tiles.items():
        buf[t * TILE:(t + 1) * TILE] = bytes.fromhex(h)
    draw(buf)
    return _tiles_hex(buf, old_tiles.keys())


def _recompress_in_place(rom: bytearray, offset: int, tiles: bytearray,
                         orig_comp_len: int, label: str) -> bool:
    compressed = lz77_compress(bytes(tiles))
    if offset + len(compressed) > len(rom):
        print(f"  WARN {label}: recompressed block overflows ROM — skip", file=sys.stderr)
        return False
    if len(compressed) > orig_comp_len:
        extra = rom[offset + orig_comp_len:offset + len(compressed)]
        if any(b not in (0x00, 0xFF) for b in extra):
            print(
                f"  WARN {label}: recompressed ({len(compressed)}) > original "
                f"({orig_comp_len}) and tail is non-padding — skip",
                file=sys.stderr,
            )
            return False
    rom[offset:offset + len(compressed)] = compressed
    return True


def _patch_label(rom: bytearray, offset: int, tile_indices, old_variants,
                 draw, label: str) -> bool:
    result = lz77_decompress(rom, offset)
    if result is None:
        print(f"  WARN {label}: cannot decompress block 0x{offset:08X} — skip",
              file=sys.stderr)
        return False
    tiles = bytearray(result[0])
    comp_len = result[1]

    current = _tiles_hex(tiles, tile_indices)

    matched_variant = None
    for name, variant in old_variants.items():
        if current == variant:
            matched_variant = (name, variant)
            break

    if matched_variant is None:
        # Already patched? Compare against « PS » generated from each variant.
        for name, variant in old_variants.items():
            if current == _expected_new(variant, draw):
                print(f"  {label}: already « PS » — no change")
                return False
        print(
            f"  WARN {label}: tiles at 0x{offset:08X} match neither a known "
            f"HP/PS variant nor « PS » — skip",
            file=sys.stderr,
        )
        return False

    draw(tiles)
    if not _recompress_in_place(rom, offset, tiles, comp_len, label):
        return False
    print(f"  {label}: {matched_variant[0]} → « PS »")
    return True


def apply_patches(rom_path: Path) -> int:
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")

    patched = 0
    patched += _patch_label(
        rom, PARTY_BLOCK, PARTY_OLD_TILES.keys(),
        {"EN « HP »": PARTY_OLD_TILES}, _draw_party_label,
        "party-menu label (0x008001D0)",
    )
    patched += _patch_label(
        rom, GREEN_BLOCK, GREEN_OLD_VARIANTS["ES « PS »"].keys(),
        GREEN_OLD_VARIANTS, _draw_green_label,
        "summary bar label (0x00E9B4B8)",
    )
    patched += _patch_label(
        rom, GREY_BLOCK, GREY_OLD_TILES.keys(),
        {"EN « HP »": GREY_OLD_TILES}, _draw_grey_label,
        "summary grey label (0x00E9A460)",
    )

    if patched:
        rom_path.write_bytes(rom)
    return patched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path,
                        default=Path("output/roms/GenedRom-it.gba"))
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    n = apply_patches(args.rom)
    print(f"patch_hp_labels_it: {n} label block(s) patched")


if __name__ == "__main__":
    main()
