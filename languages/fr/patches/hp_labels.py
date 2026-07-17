#!/usr/bin/env python3
"""Patch every HP/PS label graphic to the official French « PV ».

Four label graphics show the hit-point abbreviation in-game; none of them is
text (they are 4bpp tiles inside LZ77 blocks), so the translation pipeline
never touches them:

1. Party-menu label (CFRU custom party screen) — LZ77 block 0x008001D0.
   The green « HP » is drawn across four tiles of an 8-tile-wide sheet:
   tiles 51/52 rows 5-7 + tiles 59/60 rows 0-2 (bold letters, bg=6,
   outline=0xE, fill=0xF). Columns 14-15 hold the HP-bar left cap and the
   surrounding tiles hold the box border — only the label area is redrawn.

2. Summary-screen bar label (sprite) — LZ77 block 0x00E9B4B8, tiles 9-10.
   The EN ROM has « HP », the ES ROM « PS »; ``repair_localized_lz77_blocks``
   copies the Spanish tiles into the FR build, so the FR summary shows « PS ».
   Redrawn as « PV » (bold 5-row letters, bg=0, outline=0xF, fill=0x4).

3. Summary-screen grey stat label — LZ77 block 0x00E9A460 (the word-image
   tileset also holding ATTACK/DEFENSE/…), tiles 100/101 + 116/117.
   Thin « HP » letters (color 1) inside a grey oval (color 7) — redrawn as
   thin « PV » letters, oval untouched.

4. In-battle healthbox label (sprite) — LZ77 blocks 0x00EEF0AC / 0x00EEF380 /
   0x00EEF688 (the three healthbox sheets). White « HP » (color 1) on a dark
   pill (color 7) left of the green HP bar; ES doesn't localize it. Two tiles
   per sheet (« H » then « P ») redrawn to « P » then « V » — pill borders,
   caps and bar tiles left byte-exact.

All four patches are strict: the current label tiles must byte-match a known
variant (EN « HP » / ES « PS ») or the already-patched « PV »; anything else
is reported and skipped rather than corrupted. Recompression is in-place with
the same padding-tail tolerance used by patch_status_badges_fr.

Runs in the ``build-fr`` chain AFTER repair_stable/repair_localized (so it
wins over both) — see Makefile.

Usage::

    python3 languages/fr/patches/hp_labels.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import lz77_compress, lz77_decompress  # noqa: E402

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
# Label definitions
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

# New « PV » (bold, 4 fill rows — same geometry as the EN « HP »)
PARTY_PV_FILL: set[tuple[int, int]] = (
    # P: cols 2-6
    {(1, c) for c in range(2, 7)} | {(2, 2), (2, 3), (2, 5), (2, 6)}
    | {(3, c) for c in range(2, 7)} | {(4, 2), (4, 3)}
    # V: cols 8-12, with a slightly more open right-hand stroke than the
    # first cap-preserving pass so the glyph reads closer to the original.
    | {(1, 8), (1, 9), (1, 11), (1, 12)}
    | {(2, 8), (2, 9), (2, 10), (2, 11), (2, 12)}
    | {(3, 9), (3, 10), (3, 11)} | {(4, 10)}
)

# Known-good current bytes of tiles 51/52/59/60 (EN « HP », identical in the
# FR build since the block is EN==ES stable).
PARTY_OLD_TILES: dict[int, str] = {
    51: "666666666666666666666666666666666666666666eee66ee6fffeefe6ffffef",
    52: "6666666666666666666666666666666666666666eeee6e66ffffefe6fffeefe6",
    59: "e6ffffefe6fffeef66eee66e6666666666666666666666666666666666666666",
    60: "ffffefe6ffee6e66ee6666666666666666666666666666666666666666666666",
}

# Previous FR « PV » art from the narrower cap-preserving variant. Accept it
# as an input state so already-built ROMs migrate to the restored geometry.
PARTY_CURRENT_PV_TILES: dict[int, str] = {
    51: "666666666666666666666666666666666666666666eeee6ee6ffffefe6fffeef",
    52: "6666666666666666666666666666666666666666eeee6666ffffeee6ffffeee6",
    59: "e6ffffefe6ffee6e66ee66666666666666666666666666666666666666666666",
    60: "feffeee6e6ef6666666e66666666666666666666666666666666666666666666",
}

# ── 2. Summary green bar label sprite (block 0x00E9B4B8) ────────────────────
GREEN_BLOCK = 0x00E9B4B8
GREEN_TILES = (9, 10)
GREEN_BG, GREEN_OUT, GREEN_FILL = 0x0, 0xF, 0x4

# New « PV » (bold, 5 fill rows — same geometry as the ES « PS »)
GREEN_PV_FILL: set[tuple[int, int]] = (
    # P: cols 3-7
    {(1, c) for c in range(3, 8)} | {(2, 3), (2, 4), (2, 6), (2, 7)}
    | {(3, c) for c in range(3, 8)} | {(4, 3), (4, 4)} | {(5, 3), (5, 4)}
    # V: cols 9-13
    | {(1, 9), (1, 10), (1, 12), (1, 13)} | {(2, 9), (2, 10), (2, 12), (2, 13)}
    | {(3, 9), (3, 10), (3, 12), (3, 13)} | {(4, 10), (4, 11), (4, 12)}
    | {(5, 11)}
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

# New thin « PV » (letters 7 rows tall, 1px strokes, no outline)
GREY_PV_FILL: set[tuple[int, int]] = (
    # P: vertical col 4 + bowl cols 5-7
    {(r, 4) for r in range(3, 10)}
    | {(3, 5), (3, 6), (4, 7), (5, 7), (6, 5), (6, 6)}
    # V: bars cols 9 & 12, converging tip cols 10-11
    | {(r, 9) for r in range(3, 8)} | {(r, 12) for r in range(3, 8)}
    | {(8, 10), (8, 11), (9, 10), (9, 11)}
)

GREY_OLD_TILES: dict[int, str] = {
    100: "99999999aaaaaaaaaa7a7777aa7a71177a777117777771177777111177777117",
    101: "99999999aaaaaaaa7777a7aa171177aa177771a7177771771711777717777777",
    116: "777771177a777117aa7a7777aaaaaaaa99999999aaaaaaaaaaaaaaaaaaaaaaaa",
    117: "17777777177777a777a7aaaaaaaaaaaa99999999aaaaaaaaaaaaaaaaaaaaaaaa",
}

# ── 4. Battle healthbox HP label (LZ77 0x00EEF0AC/0x00EEF380/0x00EEF688) ─────
# The in-battle healthbox draws a white « HP » on a dark pill just left of the
# green HP bar (GitHub issue #125). It is an OBJ (sprite) graphic — untouched by
# every translation pass and *not* localized in the Spanish ROM (ES keeps « HP »
# / has no matching LZ77 block), so the FR build still shows « HP ». Three
# healthbox variants carry it (0xEEF0AC = 128-tile doubles sheet, 0xEEF380 /
# 0xEEF688 = 64-tile singles sheets); in each the label is two 8×8 tiles — an
# « H » tile then a « P » tile — only their tile index shifts.
#   letter colour = 1 (white), pill interior = 7.
# Each ``(block, h_tile, p_tile)``:
BATTLE_BLOCKS: list[tuple[int, int, int]] = [
    (0x00EEF0AC, 20, 21),
    (0x00EEF380, 19, 20),
    (0x00EEF688, 19, 20),
]
BATTLE_LETTER, BATTLE_PILL = 0x1, 0x7

# New « P » in the first (H) letter tile — letter occupies cols 2-6, rows 3-6.
BATTLE_P_FILL: set[tuple[int, int]] = {
    (3, 2), (3, 3), (3, 4), (3, 5), (3, 6),
    (4, 2), (4, 3), (4, 6),
    (5, 2), (5, 3), (5, 4), (5, 5), (5, 6),
    (6, 2), (6, 3),
}
BATTLE_P_BOX = [(r, c) for r in range(3, 7) for c in range(2, 7)]

# New « V » in the second (P) letter tile — letter occupies cols 0-4, rows 3-6.
BATTLE_V_FILL: set[tuple[int, int]] = {
    (3, 0), (3, 1), (3, 3), (3, 4),
    (4, 0), (4, 1), (4, 3), (4, 4),
    (5, 1), (5, 2), (5, 3),
    (6, 2),
}
BATTLE_V_BOX = [(r, c) for r in range(3, 7) for c in range(0, 5)]

# Known EN letter tiles (strict validation input state). The « P » tile is
# byte-identical in all three blocks; the « H » tile only differs in its
# left-cap shading column (col 0), so 0xEEF0AC has its own variant.
BATTLE_P_TILE_HEX = (
    "2222222222222222777777771111711711177117111171171177771777777777"
)
BATTLE_H_TILE_HEX: dict[int, str] = {
    0x00EEF0AC: "2222222222222222777777777411177173111771731111717811177177777777",
    0x00EEF380: "2222222222222222727777777211177172111771721111717211177172777777",
    0x00EEF688: "2222222222222222727777777211177172111771721111717211177172777777",
}


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _draw_party_label(tiles: bytearray) -> None:
    fill = PARTY_PV_FILL
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
    fill = GREEN_PV_FILL
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
    for gr, gc in GREY_PV_FILL:
        tl, tr, row = GREY_ROWS[gr]
        tile = tl if gc < 8 else tr
        _px_set(tiles, tile, row, gc % 8, GREY_LETTER)


def _make_draw_battle_label(h_tile: int, p_tile: int):
    """Return a draw(tiles) that repaints « HP » → « PV » at *h_tile*/*p_tile*.

    Only the two letter cells are touched (pill borders, caps and green-bar
    tiles are left byte-exact): the « H » tile becomes « P », the « P » tile
    becomes « V ». Every cell inside a letter box is set to the letter colour
    or the pill interior, so the redraw is fully deterministic and idempotent.
    """

    def draw(tiles: bytearray) -> None:
        for r, c in BATTLE_P_BOX:
            val = BATTLE_LETTER if (r, c) in BATTLE_P_FILL else BATTLE_PILL
            _px_set(tiles, h_tile, r, c, val)
        for r, c in BATTLE_V_BOX:
            val = BATTLE_LETTER if (r, c) in BATTLE_V_FILL else BATTLE_PILL
            _px_set(tiles, p_tile, r, c, val)

    return draw


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
        # Already patched? Compare against « PV » generated from each variant.
        for name, variant in old_variants.items():
            if current == _expected_new(variant, draw):
                print(f"  {label}: already « PV » — no change")
                return False
        print(
            f"  WARN {label}: tiles at 0x{offset:08X} match neither a known "
            f"HP/PS variant nor « PV » — skip",
            file=sys.stderr,
        )
        return False

    draw(tiles)
    if not _recompress_in_place(rom, offset, tiles, comp_len, label):
        return False
    print(f"  {label}: {matched_variant[0]} → « PV »")
    return True


def apply_patches(rom_path: Path) -> int:
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")

    patched = 0
    patched += _patch_label(
        rom, PARTY_BLOCK, PARTY_OLD_TILES.keys(),
        {
            "EN « HP »": PARTY_OLD_TILES,
            "FR « PV » étroit": PARTY_CURRENT_PV_TILES,
        }, _draw_party_label,
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
    for off, h_tile, p_tile in BATTLE_BLOCKS:
        patched += _patch_label(
            rom, off, (h_tile, p_tile),
            {"EN « HP »": {h_tile: BATTLE_H_TILE_HEX[off],
                           p_tile: BATTLE_P_TILE_HEX}},
            _make_draw_battle_label(h_tile, p_tile),
            f"battle healthbox label (0x{off:08X})",
        )

    if patched:
        rom_path.write_bytes(rom)
    return patched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path,
                        default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    n = apply_patches(args.rom)
    print(f"patch_hp_labels_fr: {n} label block(s) patched")


if __name__ == "__main__":
    main()
