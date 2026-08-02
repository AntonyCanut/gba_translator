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

2. Summary-screen HP-bar sheet (sprite) — LZ77 block 0x00E9B4B8, 12 tiles.
   Tiles 0-8 are the bar body (one per fill level), tiles 9-10 the « HP »
   label *plus the bar's left cap* (tile 10 column 7, rows 2-4) and tile 11
   the bar's right cap (column 0, rows 2-4). ``repair_localized_lz77_blocks``
   copies the whole Spanish sheet into the FR build, and the Spanish sheet
   has a 7-row bar body with **no cap tiles at all** — which is why the FR
   « Capacités » page showed a bar truncated at both ends (GitHub issue #84).
   The patch therefore restores the *English* sheet wholesale and only
   redraws the label letters as « PV » (bg=0, outline=0xF, fill=0x4) inside
   the 6×14 box the EN « HP » occupies, leaving columns 14-15 — the left cap
   — byte-exact.

3. Summary-screen grey stat label — LZ77 block 0x00E9A460 (the word-image
   tileset also holding ATTACK/DEFENSE/…), tiles 100/101 + 116/117.
   Thin « HP » letters (color 1) inside a grey oval (color 7) — redrawn as
   thin « PV » letters, oval untouched.

4. In-battle healthbox label (sprite) — LZ77 blocks 0x00D1F604 / 0x00EEF0AC /
   0x00EEF380 / 0x00EEF688 (the player/ally + doubles healthbox sheets). White
   « HP » (color 1) on a dark pill (color 7) left of the green HP bar; ES doesn't
   localize it. Two tiles per sheet (« H » then « P ») redrawn to « P » then « V »
   — pill borders, caps and bar tiles left byte-exact. (0xD1F604 is a palette-slot
   variant the first #125 fix missed, hence the residual « HP » in 2.1.68.)

5. In-battle healthbox label — UNCOMPRESSED healthbox-element tiles (window
   0x00D11800-0x00D12800), two-tone letters (color 1/8) on a pill. The enemy
   singles box draws its « HP » from here, not from the four LZ77 sheets, so it
   stayed « HP » in a real battle even after fixes 1-4. The table stores the
   label FOUR times (0xD11BC4 « H » pill 3, 0xD11BE4 « H » pill 7, 0xD11C04
   « P », 0xD123E4 « P » copy): the box is drawn from one copy but the
   status-icon redraw re-copies another, so converting only the adjacent pair
   left « HP » showing as soon as the Pokémon was poisoned/burned. Every label
   tile is now found by letter shape and redrawn on its own — « H »→« P »,
   « P »→« V ». Verified in-engine via scripts/probe_battle_healthbox_fr.mts +
   scripts/verify_battle_healthbox_fr.py.

Patches 1-4 are strict: the current label tiles must byte-match a known
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

# ── 2. Summary HP-bar sheet (block 0x00E9B4B8) ──────────────────────────────
GREEN_BLOCK = 0x00E9B4B8
GREEN_TILES = (9, 10)              # the two label tiles inside the sheet
GREEN_TILE_COUNT = 12              # whole sheet: body 0-8, label 9-10, cap 11
GREEN_BG, GREEN_OUT, GREEN_FILL = 0x0, 0xF, 0x4

# The sheet lives in a 192-byte slot: 0x08E9B578 (= block + 192) is the next
# pointed-to address in the ROM, and nothing points inside the stream itself.
# The Spanish stream copied by repair_localized_lz77_blocks is 168 bytes, so
# the recompressed English sheet (~150) always fits even though it is longer
# than whatever stream currently sits there.
GREEN_SLOT_LEN = 192

# The label box: 6 rows × 14 columns, exactly what the EN « HP » occupies.
# Column 14 is the gap and column 15 the HP-bar left cap — never drawn on.
GREEN_NROWS, GREEN_NCOLS = 6, 14

# New « PV » (bold, 4 fill rows — same geometry as the EN « HP »)
GREEN_PV_FILL: set[tuple[int, int]] = (
    # P: cols 2-6
    {(1, c) for c in range(2, 7)} | {(2, 2), (2, 3), (2, 5), (2, 6)}
    | {(3, c) for c in range(2, 7)} | {(4, 2), (4, 3)}
    # V: cols 8-12
    | {(1, 8), (1, 9), (1, 11), (1, 12)} | {(2, 8), (2, 9), (2, 11), (2, 12)}
    | {(3, 9), (3, 10), (3, 11)} | {(4, 10)}
)

# The English sheet — the reference art the FR build must ship. Tiles 0-8 are
# the 5-row bar body, tile 10 column 7 the bar's left cap and tile 11 column 0
# its right cap.
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

# The Spanish sheet copied in by repair_localized_lz77_blocks: 7-row bar body
# (rows 0 and 6 filled) and an empty tile 11 — both bar caps are missing.
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

# State of every FR ROM built before issue #84 was fixed: the Spanish sheet
# with a « PV » drawn on the Spanish 7-row geometry. Accepted as an input
# variant so an already-built ROM migrates instead of being skipped.
GREEN_ES_PV_TILES: dict[int, str] = {
    **GREEN_ES_TILES,
    9: "00f0ffff004f4444004ff444004f4444004ff4ff004ff40000f00f0000000000",
    10: "f00fff004ff4440f4ff4440f4ff4440ff044f400004f0f0000f0000000000000",
}

GREEN_OLD_VARIANTS: dict[str, dict[int, str]] = {
    "EN « HP »": GREEN_EN_TILES,
    "ES « PS »": GREEN_ES_TILES,
    "FR « PV » sans caps": GREEN_ES_PV_TILES,
}

# ── 3. Summary grey stat label (block 0x00E9A460) ───────────────────────────
GREY_BLOCK = 0x00E9A460
# 16×16 px area: tiles 100/101 (grid rows 0-7) over 116/117 (grid rows 8-15)
GREY_ROWS: list[tuple[int, int, int]] = (
    [(100, 101, r) for r in range(8)] + [(116, 117, r) for r in range(8)]
)
GREY_LETTER, GREY_OVAL, GREY_PANEL = 0x1, 0x7, 0xA
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

# Like the stat capsules of languages/fr/patches/summary_stat_labels.py, the
# oval's top and bottom rows hug the word instead of being a fixed shape. « PV »
# is not « HP »: its V reaches one column further right on row 2 and its tip
# drops to rows 8-9, so the bottom edge moves out from under the P's bowl and
# out to under the V. Six pixels, taken from the hand-drawn reference sheet
# languages/fr/sprites/summary_stat_labels.png so both stay in step.
GREY_OVAL_RESHAPE: dict[tuple[int, int], int] = {
    (2, 13): GREY_OVAL,
    (10, 6): GREY_PANEL,
    (10, 7): GREY_PANEL,
    (10, 8): GREY_PANEL,
    (10, 11): GREY_OVAL,
    (10, 12): GREY_OVAL,
}

GREY_OLD_TILES: dict[int, str] = {
    100: "99999999aaaaaaaaaa7a7777aa7a71177a777117777771177777111177777117",
    101: "99999999aaaaaaaa7777a7aa171177aa177771a7177771771711777717777777",
    116: "777771177a777117aa7a7777aaaaaaaa99999999aaaaaaaaaaaaaaaaaaaaaaaa",
    117: "17777777177777a777a7aaaaaaaaaaaa99999999aaaaaaaaaaaaaaaaaaaaaaaa",
}

# ── 4. Battle healthbox HP label (LZ77 0xD1F604/0xEEF0AC/0xEEF380/0xEEF688) ───
# The in-battle healthbox draws a white « HP » on a dark pill just left of the
# green HP bar (GitHub issue #125). It is an OBJ (sprite) graphic — untouched by
# every translation pass and *not* localized in the Spanish ROM (ES keeps « HP »
# / has no matching LZ77 block), so the FR build still shows « HP ». Four
# healthbox variants carry it (0xEEF0AC = 128-tile doubles sheet, 0xD1F604 /
# 0xEEF380 / 0xEEF688 = 64-tile singles sheets); in each the label is two 8×8
# tiles — an « H » tile then a « P » tile — only their tile index shifts.
#   letter colour = 1 (white), pill interior = 7.
# 0xD1F604 is a palette-slot variant (top-border colour 3 instead of 2); the
# original #125 fix only shipped the three 0xEE… sheets, so this fourth sheet
# (used by one healthbox layout) kept showing « HP » in-game.
# Each ``(block, h_tile, p_tile)``:
BATTLE_BLOCKS: list[tuple[int, int, int]] = [
    (0x00D1F604, 19, 20),
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

# Known EN letter tiles (strict validation input state). The « P » tile body is
# identical across the sheets; only the top-border colour and the « H » tile's
# left-cap shading column differ per palette slot (0xEEF0AC and 0xD1F604 each
# have their own variant), so both tiles are keyed by block.
BATTLE_P_TILE_HEX: dict[int, str] = {
    0x00D1F604: "3333333333333333777777771111711711177117111171171177771777777777",
    0x00EEF0AC: "2222222222222222777777771111711711177117111171171177771777777777",
    0x00EEF380: "2222222222222222777777771111711711177117111171171177771777777777",
    0x00EEF688: "2222222222222222777777771111711711177117111171171177771777777777",
}
BATTLE_H_TILE_HEX: dict[int, str] = {
    0x00D1F604: "3333333333333333737777777311177173111771731111717311177173777777",
    0x00EEF0AC: "2222222222222222777777777411177173111771731111717811177177777777",
    0x00EEF380: "2222222222222222727777777211177172111771721111717211177172777777",
    0x00EEF688: "2222222222222222727777777211177172111771721111717211177172777777",
}


# ── 5. In-battle healthbox HP label (UNCOMPRESSED element tile table) ────────
# The four sheets above are the player/ally + doubles healthbox *frames*. The
# battle engine also owns a flat table of loose 8×8 healthbox elements stored
# RAW (uncompressed) in the ROM — ``sHealthboxElementsGfxTable``-style, base
# 0x00D11BC4, the only address the battle-interface code references. It is
# byte-identical in EN and FR, so no LZ77 repair or earlier pass ever touched
# it. That table holds FOUR « HP » label tiles:
#
#   0x00D11BC4  « H », pill colour 3   (table tile 0)
#   0x00D11BE4  « H », pill colour 7   (table tile 1)
#   0x00D11C04  « P », pill colour 7   (table tile 2)
#   0x00D123E4  « P », pill colour 7   (table tile 65 — byte-identical copy)
#
# The healthbox is drawn from tiles 1+2, which is why patching only that pair
# fixed the enemy box in a plain battle. But ``UpdateStatusIconInHealthbox``
# re-copies the label from the OTHER copies when a status condition (poison,
# burn…) is put on the battler — so the box flipped back to « HP » the moment
# the Pokémon was statused (GitHub issue #125, 3rd report). Spanish confirms
# the split: ES localizes 0xD11BE4/0xD11C04 to « PS » and leaves the other two
# alone, so the ES build has the same status-only bug.
#
# Letters are TWO-TONE (colour 1 on rows 3-4, colour 8 on rows 5-6) over a pill
# whose colour differs per palette slot (3 or 7), with a transparent margin.
# Tiles are located by LETTER SHAPE inside a bounded window (same "scan by
# shape, not exact bytes" lesson as 0xD1F604) and each one is redrawn on its
# own — every « H » becomes « P », every « P » becomes « V » — so whichever
# combination the engine loads reads « PV ».
HPEL_REGION = (0x00D11800, 0x00D12800)   # ROM window holding the element table
HPEL_UP, HPEL_LO, HPEL_PILL = 0x1, 0x8, 0x7   # letter upper/lower rows, pill fill
HPEL_MARGIN = 0x0                             # transparent rows above the pill

# Recognition masks — letter-coloured columns per row 3-6 of the CURRENT art.
HPEL_H_SHAPE = {3: {2, 3, 5, 6}, 4: {2, 3, 5, 6}, 5: {2, 3, 4, 5, 6}, 6: {2, 3, 5, 6}}
HPEL_P_SHAPE = {3: {0, 1, 2, 3, 4}, 4: {0, 1, 3, 4}, 5: {0, 1, 2, 3, 4}, 6: {0, 1}}
# Redraw masks — « P » in the H tile (cols 2-6) and « V » in the P tile (cols 0-4).
HPEL_P_FILL = {3: {2, 3, 4, 5, 6}, 4: {2, 3, 5, 6}, 5: {2, 3, 4, 5, 6}, 6: {2, 3}}
HPEL_V_FILL = {3: {0, 1, 3, 4}, 4: {0, 1, 3, 4}, 5: {1, 2, 3}, 6: {2}}
HPEL_H_COLS = range(2, 7)   # letter box of an « H »/« P » tile
HPEL_P_COLS = range(0, 5)   # letter box of a « P »/« V » tile

# The confirmed label tiles, byte-identical in EN and FR. Kept as fixed strings
# so the tests / in-engine verifier have a self-contained source of truth (no
# englishrom.gba dependency in CI).
HPEL_OLD_H_HEX = "0000000000000000707777777011177170111771708888787088877870777777"
HPEL_OLD_P_HEX = "0000000000000000777777771111711711177117888878178877771777777777"
# Palette-slot sibling of the « H » tile (pill colour 3) — the copy the status
# redraw uses. Never localized, in any language.
HPEL_OLD_H_ALT_HEX = "0000000000000000303333333011133130111331308888383088833830333333"

# Every « HP » label tile of the table, with the art it holds in the base ROM.
HPEL_LABEL_TILES: dict[int, str] = {
    0x00D11BC4: HPEL_OLD_H_ALT_HEX,
    0x00D11BE4: HPEL_OLD_H_HEX,
    0x00D11C04: HPEL_OLD_P_HEX,
    0x00D123E4: HPEL_OLD_P_HEX,
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
    """Rebuild the summary HP-bar sheet: English art + a French « PV » label.

    The sheet is restored from the English reference first, so the bar body
    and both end caps are byte-exact even when the Spanish sheet was copied
    in beforehand. Only the 6×14 label box is then repainted; columns 14-15
    of the box carry the bar's left cap and are never written.
    """
    for tile, hexdata in GREEN_EN_TILES.items():
        tiles[tile * TILE:(tile + 1) * TILE] = bytes.fromhex(hexdata)

    fill = GREEN_PV_FILL
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
    for gr, gc in GREY_PV_FILL:
        tl, tr, row = GREY_ROWS[gr]
        tile = tl if gc < 8 else tr
        _px_set(tiles, tile, row, gc % 8, GREY_LETTER)
    # then re-cut the oval's hugging rows around « PV »
    for (gr, gc), val in GREY_OVAL_RESHAPE.items():
        tl, tr, row = GREY_ROWS[gr]
        tile = tl if gc < 8 else tr
        _px_set(tiles, tile, row, gc % 8, val)


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


# --- Uncompressed opponent-healthbox « HP » element helpers ----------------

def _hpel_rows(tile: bytes) -> dict[int, set[int]]:
    """Letter-coloured columns (colour 1 or 8) per row 3-6 of a raw 8×8 tile."""
    buf = bytearray(tile)
    return {
        r: {c for c in range(8)
            if _px_get(buf, 0, r, c) in (HPEL_UP, HPEL_LO)}
        for r in (3, 4, 5, 6)
    }


def _hpel_is_h(tile: bytes) -> bool:
    return _hpel_rows(tile) == HPEL_H_SHAPE


def _hpel_is_p(tile: bytes) -> bool:
    # Ignore col 7 — the « P » tile carries a 1-pixel separator stem there.
    rows = {r: {c for c in cols if c <= 6} for r, cols in _hpel_rows(tile).items()}
    return rows == HPEL_P_SHAPE


def _hpel_plate(tile: bytes) -> int:
    """Pill/plate colour of a label tile (row 2 is a full pill row)."""
    return _px_get(bytearray(tile), 0, 2, 7)


def _hpel_is_label(tile: bytes) -> bool:
    """Structural gate: transparent top margin + a uniform pill border.

    Every healthbox label tile has two fully transparent rows above the pill
    and a pill border (rows 2 and 7) made only of the plate colour and the
    transparent margin. Requiring that shape before looking at letters keeps
    the 4-byte-stride scan from mistaking bar/status art for a label.
    """
    buf = bytearray(tile)
    if any(_px_get(buf, 0, r, c) != HPEL_MARGIN for r in (0, 1) for c in range(8)):
        return False
    plate = _hpel_plate(tile)
    return all(_px_get(buf, 0, r, c) in (plate, HPEL_MARGIN)
               for r in (2, 7) for c in range(8))


def _hpel_redraw(tile: bytes, fill: dict[int, set[int]], glyph_cols) -> bytes:
    """Repaint rows 3-6 of *tile* with a two-tone letter (upper=1, lower=8) on
    the pill, leaving the pill/margin/separator columns byte-exact.

    The pill colour is read from the tile itself, so a palette-slot sibling
    (pill colour 3 instead of 7) keeps its own colours.
    """
    buf = bytearray(tile)
    plate = _hpel_plate(tile)
    for r in (3, 4, 5, 6):
        letter = HPEL_UP if r in (3, 4) else HPEL_LO
        for c in glyph_cols:
            _px_set(buf, 0, r, c, letter if c in fill[r] else plate)
    return bytes(buf)


def hpel_convert_tile(tile: bytes) -> bytes | None:
    """« H » → « P », « P » → « V »; ``None`` if *tile* is not a label tile."""
    if not _hpel_is_label(tile):
        return None
    if _hpel_is_h(tile):
        return _hpel_redraw(tile, HPEL_P_FILL, HPEL_H_COLS)
    if _hpel_is_p(tile):
        return _hpel_redraw(tile, HPEL_V_FILL, HPEL_P_COLS)
    return None


def hpel_convert_pair(h_tile: bytes, p_tile: bytes) -> tuple[bytes, bytes]:
    """« H »,« P » → « P »,« V » (used by the patch and by the tests)."""
    return (
        _hpel_redraw(h_tile, HPEL_P_FILL, HPEL_H_COLS),
        _hpel_redraw(p_tile, HPEL_V_FILL, HPEL_P_COLS),
    )


def _patch_hp_element(rom: bytearray) -> int:
    """Redraw every uncompressed healthbox « HP » label tile to « PV ».

    Scans the element window by letter SHAPE and converts each label tile on
    its own — an « H » becomes « P », a « P » becomes « V » — instead of only
    converting adjacent « H »+« P » pairs. The table stores the label twice
    (tiles 0/1/2 and a copy at tile 65) and the status-icon redraw picks the
    copy the first fix left untouched, so pair-matching missed it and the box
    reverted to « HP » as soon as the Pokémon was poisoned/burned.

    Both the search and the redraw are idempotent: a converted tile draws
    « P »/« V » in different columns and no longer matches either shape.
    """
    lo, hi = HPEL_REGION
    patched = 0
    off = lo
    while off + TILE <= hi:
        converted = hpel_convert_tile(bytes(rom[off:off + TILE]))
        if converted is not None:
            letter = "« H » → « P »" if _hpel_is_h(bytes(rom[off:off + TILE])) \
                else "« P » → « V »"
            rom[off:off + TILE] = converted
            print(f"  healthbox HP element (0x{off:08X}) {letter}")
            patched += 1
            off += TILE
            continue
        off += 4  # tiles in this table are 4-byte (not 32-byte) aligned
    return patched


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
        # The block owns a known slot (nothing is pointed to inside it), so a
        # stream longer than the current one is safe as long as it still fits.
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
    if not _recompress_in_place(rom, offset, tiles, comp_len, label, slot_len):
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
    for off, h_tile, p_tile in BATTLE_BLOCKS:
        patched += _patch_label(
            rom, off, (h_tile, p_tile),
            {"EN « HP »": {h_tile: BATTLE_H_TILE_HEX[off],
                           p_tile: BATTLE_P_TILE_HEX[off]}},
            _make_draw_battle_label(h_tile, p_tile),
            f"battle healthbox label (0x{off:08X})",
        )
    patched += _patch_hp_element(rom)

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
