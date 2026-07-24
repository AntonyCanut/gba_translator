#!/usr/bin/env python3
"""Patch every HP/PS label graphic to the official German « KP » (Kraftpunkte).

Sibling of ``patch_hp_labels_fr.py`` — identical LZ77 block layout and
verification machinery, different letters (French draws « PV », German draws
« KP »). Three label graphics show the hit-point abbreviation in-game; none of
them is text (they are 4bpp tiles inside LZ77 blocks), so the translation
pipeline never touches them:

1. Party-menu label (CFRU custom party screen) — LZ77 block 0x008001D0.
   The green « HP » is drawn across four tiles of an 8-tile-wide sheet:
   tiles 51/52 rows 5-7 + tiles 59/60 rows 0-2 (bold letters, bg=6,
   outline=0xE, fill=0xF). Columns 14-15 hold the HP-bar left cap and the
   surrounding tiles hold the box border — only the label area is redrawn.

2. Summary-screen HP-bar sheet (sprite) — LZ77 block 0x00E9B4B8, 12 tiles.
   Tiles 0-8 are the bar body, tiles 9-10 the label plus its left cap, and
   tile 11 its right cap. ``repair_localized_lz77_blocks`` copies the Spanish
   sheet into the generic (DE) build; that sheet has a 7-row body and no caps.
   The patch restores the English sheet wholesale, then redraws only « KP »
   inside the 6×14 letter box, leaving the cap columns untouched.

3. Summary-screen grey stat label — LZ77 block 0x00E9A460 (the word-image
   tileset also holding ATTACK/DEFENSE/…), tiles 100/101 + 116/117.
   Thin « HP » letters (color 1) inside a grey oval (color 7) — redrawn as
   thin « KP » letters, oval untouched.

All three patches are strict: the current label tiles must byte-match a known
variant (EN « HP » / ES « PS ») or the already-patched « KP »; anything else
is reported and skipped rather than corrupted. Recompression is in-place with
the same padding-tail tolerance used by patch_status_badges_de.

Runs in the generic ``build_language.py de`` chain AFTER repair_lz77/
repair_localized_lz77 (so it wins over both) — see languages/de/lang.yaml.

Usage::

    python3 languages/de/patches/hp_labels.py --rom output/roms/GenedRom-de.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import lz77_compress, lz77_decompress

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
# Label definitions — German « KP »
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

# New « KP » (bold, 4 fill rows — same geometry/height as the EN « HP »)
PARTY_KP_FILL: set[tuple[int, int]] = (
    # K: stem cols 2-3, arm cols 4-6
    {(1, 2), (1, 3), (1, 5), (1, 6)}
    | {(2, 2), (2, 3), (2, 4), (2, 5)}
    | {(3, 2), (3, 3), (3, 4), (3, 5)}
    | {(4, 2), (4, 3), (4, 5), (4, 6)}
    # P: cols 8-12
    | {(1, c) for c in range(8, 13)} | {(2, 8), (2, 9), (2, 11), (2, 12)}
    | {(3, c) for c in range(8, 13)} | {(4, 8), (4, 9)}
)

# Known-good current bytes of tiles 51/52/59/60 (EN « HP », identical in the
# generic build since the block is EN==ES stable and restored by repair_lz77).
PARTY_OLD_TILES: dict[int, str] = {
    51: "666666666666666666666666666666666666666666eee66ee6fffeefe6ffffef",
    52: "6666666666666666666666666666666666666666eeee6e66ffffefe6fffeefe6",
    59: "e6ffffefe6fffeef66eee66e6666666666666666666666666666666666666666",
    60: "ffffefe6ffee6e66ee6666666666666666666666666666666666666666666666",
}

# ── 2. Summary HP-bar sheet (block 0x00E9B4B8) ──────────────────────────────
GREEN_BLOCK = 0x00E9B4B8
GREEN_TILES = (9, 10)
GREEN_TILE_COUNT = 12
GREEN_BG, GREEN_OUT, GREEN_FILL = 0x0, 0xF, 0x4
GREEN_SLOT_LEN = 192
GREEN_NROWS, GREEN_NCOLS = 6, 14

# New « KP » (bold, 4 fill rows — same geometry/height as the EN « HP »).
GREEN_KP_FILL: set[tuple[int, int]] = (
    # K: stem cols 2-3, arm cols 4-6
    {(1, 2), (1, 3), (1, 5), (1, 6)}
    | {(2, 2), (2, 3), (2, 4), (2, 5)}
    | {(3, 2), (3, 3), (3, 4), (3, 5)}
    | {(4, 2), (4, 3), (4, 5), (4, 6)}
    # P: cols 8-12
    | {(1, c) for c in range(8, 13)} | {(2, 8), (2, 9), (2, 11), (2, 12)}
    | {(3, c) for c in range(8, 13)} | {(4, 8), (4, 9)}
)

GREEN_EN_TILES: dict[int, str] = {
    0: "00000000ffffffff333333333333333333333333ffffffff0000000000000000",
    1: "00000000ffffffff323333333133333331333333ffffffff0000000000000000",
    2: "00000000ffffffff223333331133333311333333ffffffff0000000000000000",
    3: "00000000ffffffff223233331131333311313333ffffffff0000000000000000",
    4: "00000000ffffffff222233331111333311113333ffffffff0000000000000000",
    5: "00000000ffffffff222232331111313311113133ffffffff0000000000000000",
    6: "00000000ffffffff222222331111113311111133ffffffff0000000000000000",
    7: "00000000ffffffff222222321111113111111131ffffffff0000000000000000",
    8: "00000000ffffffff222222221111111111111111ffffffff0000000000000000",
    9: "00fff00ff0444ff4f04444f4f04444f4f0444ff400fff00f0000000000000000",
    10: "ffff0f004444f400444ff4f04444f4f044ff0ff0ff0000000000000000000000",
    11: "00000000000000000f0000000f0000000f000000000000000000000000000000",
}

GREEN_ES_TILES: dict[int, str] = {
    0: "ffffffffffffffff333333333333333333333333ffffffffffffffff00000000",
    1: "ffffffffffffffff323333333133333331333333ffffffffffffffff00000000",
    2: "ffffffffffffffff223333331133333311333333ffffffffffffffff00000000",
    3: "ffffffffffffffff223233331131333311313333ffffffffffffffff00000000",
    4: "ffffffffffffffff222233331111333311113333ffffffffffffffff00000000",
    5: "ffffffffffffffff222232331111313311113133ffffffffffffffff00000000",
    6: "ffffffffffffffff222222331111113311111133ffffffffffffffff00000000",
    7: "ffffffffffffffff222222321111113111111131ffffffffffffffff00000000",
    8: "ffffffffffffffff222222221111111111111111ffffffffffffffff00000000",
    9: "00fffffff04f4444f04ff444f04f4444f04ff4fff04ff4ff00ffffff00000000",
    10: "ffffff0f4f4444ff4ff4ffff4f4444ffffff44ff4f4444ffffffff0f00000000",
    11: "0000000000000000000000000000000000000000000000000000000000000000",
}

GREEN_ES_KP_TILES: dict[int, str] = {
    **GREEN_ES_TILES,
    9: "00f00fff004ff444004f44f4004f440f004f44f4004ff44400f00fff00000000",
    10: "f0ffff004f44440f4ff4440f4f44440f4ff4ff004ff40000f00f000000000000",
}

GREEN_OLD_VARIANTS: dict[str, dict[int, str]] = {
    "EN « HP »": GREEN_EN_TILES,
    "ES « PS »": GREEN_ES_TILES,
    "DE « KP » sans caps": GREEN_ES_KP_TILES,
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

# New thin « KP » (letters 7 rows tall, 1px strokes, no outline)
GREY_KP_FILL: set[tuple[int, int]] = (
    # K: stem col 4 + diagonal arms meeting at row 6
    {(r, 4) for r in range(3, 10)}
    | {(5, 5), (4, 6), (3, 7)}          # upper arm
    | {(6, 5)}                          # vertex
    | {(7, 5), (8, 6), (9, 7)}          # lower arm
    # P: stem col 9 + bowl cols 10-12
    | {(r, 9) for r in range(3, 10)}
    | {(3, 10), (3, 11), (4, 12), (5, 12), (6, 10), (6, 11)}
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
    fill = PARTY_KP_FILL
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
    for tile, hexdata in GREEN_EN_TILES.items():
        tiles[tile * TILE:(tile + 1) * TILE] = bytes.fromhex(hexdata)

    fill = GREEN_KP_FILL
    outline = _outline(fill, GREEN_NROWS, GREEN_NCOLS)
    for gr in range(GREEN_NROWS):
        for gc in range(GREEN_NCOLS):
            if (gr, gc) in fill:
                val = GREEN_FILL
            elif (gr, gc) in outline:
                val = GREEN_OUT
            else:
                val = GREEN_BG
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
    for gr, gc in GREY_KP_FILL:
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
                         orig_comp_len: int, label: str,
                         slot_len: int | None = None) -> bool:
    compressed = lz77_compress(bytes(tiles))
    if offset + len(compressed) > len(rom):
        print(f"  WARN {label}: recompressed block overflows ROM — skip", file=sys.stderr)
        return False
    if slot_len is not None:
        if len(compressed) > slot_len:
            print(
                f"  WARN {label}: recompressed ({len(compressed)}) exceeds the "
                f"{slot_len}-byte slot — skip",
                file=sys.stderr,
            )
            return False
        rom[offset:offset + len(compressed)] = compressed
        return True
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
                 draw, label: str, slot_len: int | None = None) -> bool:
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
        # Already patched? Compare against « KP » generated from each variant.
        for name, variant in old_variants.items():
            if current == _expected_new(variant, draw):
                print(f"  {label}: already « KP » — no change")
                return False
        print(
            f"  WARN {label}: tiles at 0x{offset:08X} match neither a known "
            f"HP/PS variant nor « KP » — skip",
            file=sys.stderr,
        )
        return False

    draw(tiles)
    if not _recompress_in_place(rom, offset, tiles, comp_len, label, slot_len):
        return False
    print(f"  {label}: {matched_variant[0]} → « KP »")
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
        rom, GREEN_BLOCK, range(GREEN_TILE_COUNT),
        GREEN_OLD_VARIANTS, _draw_green_label,
        "summary HP-bar sheet (0x00E9B4B8)",
        slot_len=GREEN_SLOT_LEN,
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
                        default=Path("output/roms/GenedRom-de.gba"))
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    n = apply_patches(args.rom)
    print(f"patch_hp_labels_de: {n} label block(s) patched")


if __name__ == "__main__":
    main()
