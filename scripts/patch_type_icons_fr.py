#!/usr/bin/env python3
"""Redraw the move-type icon names in French inside the type-icon graphic.

The Pokémon summary screen (Infos / Capacités pages) and the battle move menu
display each move's type as a small graphical badge — a coloured pill with the
type name baked into the pixels (e.g. « ROCK », « DARK »).  These are NOT text
read from any string table (patching gTypeNames / the « a TYPE move » template
has no effect on them — verified in-game): the type name lives in a 4bpp tile
graphic indexed by the CFRU ``typeicon`` table.

There are TWO identical copies of this 16-tile-wide sheet in the ROM:
  * 0xB1EC64 — used by the summary screen (Infos / Capacités type badges)
  * 0x961A00 — used by the battle move menu
Both are patched so every type display is French.

Layout (per CFRU type_tables.s, confirmed by rendering the EN sheet):
  Each icon is 32x12 px = 4 tiles wide.  Row 8-9 of the 2-tile-tall cell is the
  solid pill colour; rows 10-15 hold the type name (fill = palette 15, drop
  shadow = palette 14) on the pill colour.  We clear rows 10-15 to the pill
  colour and re-stamp the French name centred, using a compact 5px bitmap font.

Only types whose French name differs from the English art are redrawn; NORMAL,
POISON, DRAGON, ELECTR and the ??? icon already read correctly in French and are
left untouched.  Idempotent: re-running renders the same French name again.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The two byte-identical copies of the type-icon sheet (tile 0 of each).
BASES = [0xB1EC64, 0x961A00]

# type name -> first tile index of its 4x2-tile icon within a sheet
TILEOFF = {
    "Fight": 0x64, "Flying": 0x60, "Ground": 0x48, "Rock": 0x44, "Bug": 0x6C,
    "Ghost": 0x68, "Steel": 0x88, "Fire": 0x24, "Water": 0x28, "Grass": 0x2C,
    "Psychic": 0x84, "Ice": 0x4C, "Dark": 0x8C, "Fairy": 0xA8,
}

# French type names (uppercase, no accents — the icon font has none).
# « ACIER » per the project owner's request (Steel); « TENEBR » abbreviates
# Ténèbres to fit the 32-px pill.
FR_NAME = {
    "Fight": "COMBAT", "Flying": "VOL", "Ground": "SOL", "Rock": "ROCHE",
    "Bug": "INSECT", "Ghost": "SPECTR", "Steel": "ACIER", "Fire": "FEU",
    "Water": "EAU", "Grass": "PLANTE", "Psychic": "PSY", "Ice": "GLACE",
    "Dark": "TENEBR", "Fairy": "FEE",
}

_FILL = 15      # white letter fill (palette index)
_SHADOW = 14    # drop-shadow (palette index)
# Each icon is 4x3 tiles (32x24 px). The coloured pill spans rows 8-19; the
# English type name is 8 px tall and occupies rows 10-17 — i.e. it spills into
# the THIRD tile row. The whole 10-17 band MUST be cleared, or the bottom two
# rows of the old English word survive below the (shorter) French name.
_TEXT_TOP = 10  # first pixel row of the name within the cell
_TEXT_ROWS = range(10, 18)

# Compact 5-row uppercase bitmap font (only the glyphs the names above need).
_FONT = {
    "A": ["0110", "1001", "1111", "1001", "1001"],
    "B": ["1110", "1001", "1110", "1001", "1110"],
    "C": ["0111", "1000", "1000", "1000", "0111"],
    "E": ["1111", "1000", "1110", "1000", "1111"],
    "F": ["1111", "1000", "1110", "1000", "1000"],
    "G": ["0111", "1000", "1011", "1001", "0111"],
    "H": ["1001", "1001", "1111", "1001", "1001"],
    "I": ["111", "010", "010", "010", "111"],
    "L": ["1000", "1000", "1000", "1000", "1111"],
    "M": ["10001", "11011", "10101", "10001", "10001"],
    "N": ["1001", "1101", "1011", "1001", "1001"],
    "O": ["0110", "1001", "1001", "1001", "0110"],
    "P": ["1110", "1001", "1110", "1000", "1000"],
    "R": ["1110", "1001", "1110", "1010", "1001"],
    "S": ["0111", "1000", "0110", "0001", "1110"],
    "T": ["111", "010", "010", "010", "010"],
    "U": ["1001", "1001", "1001", "1001", "0110"],
    "V": ["1001", "1001", "1001", "0110", "0110"],
    "Y": ["1001", "0110", "0100", "0100", "0100"],
}


def _glyph_w(ch: str) -> int:
    return len(_FONT[ch][0])


def _name_width(name: str) -> int:
    return sum(_glyph_w(c) for c in name) + (len(name) - 1)


def _read_icon(rom: bytearray, base: int, tileoff: int) -> list[list[int]]:
    g = [[0] * 32 for _ in range(24)]
    for tr in range(3):
        for tc in range(4):
            off = base + (tileoff + tr * 16 + tc) * 32
            for r in range(8):
                for cp in range(4):
                    b = rom[off + r * 4 + cp]
                    g[tr * 8 + r][tc * 8 + cp * 2] = b & 0xF
                    g[tr * 8 + r][tc * 8 + cp * 2 + 1] = (b >> 4) & 0xF
    return g


def _write_icon(rom: bytearray, base: int, tileoff: int, g: list[list[int]]) -> None:
    for tr in range(3):
        for tc in range(4):
            off = base + (tileoff + tr * 16 + tc) * 32
            for r in range(8):
                for cp in range(4):
                    lo = g[tr * 8 + r][tc * 8 + cp * 2]
                    hi = g[tr * 8 + r][tc * 8 + cp * 2 + 1]
                    rom[off + r * 4 + cp] = (lo & 0xF) | ((hi & 0xF) << 4)


def _stamp_name(g: list[list[int]], name: str, pill: int) -> None:
    # clear the text band to the pill colour
    for r in _TEXT_ROWS:
        for c in range(32):
            g[r][c] = pill
    x = max(0, (32 - _name_width(name)) // 2)
    for ch in name:
        rows = _FONT[ch]
        w = len(rows[0])
        for gy in range(5):
            for gx in range(w):
                if rows[gy][gx] == "1":
                    px, py = x + gx, _TEXT_TOP + gy
                    if 0 <= px < 32 and py < 24:
                        g[py][px] = _FILL
        x += w + 1
    # drop shadow: pill pixel just below/right of a fill becomes the shadow colour
    for r in _TEXT_ROWS:
        for c in range(32):
            if g[r][c] != pill:
                continue
            above = r - 1 >= _TEXT_TOP and g[r - 1][c] == _FILL
            left = c - 1 >= 0 and g[r][c - 1] == _FILL
            if above or left:
                g[r][c] = _SHADOW


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    rom = bytearray(rom_path.read_bytes())
    patched = 0
    for base in BASES:
        if base + 0xD0 * 32 > len(rom):
            print(f"  SKIP base 0x{base:07X}: beyond ROM end", file=sys.stderr)
            continue
        for icon, fr in FR_NAME.items():
            missing = [c for c in fr if c not in _FONT]
            if missing:
                print(f"  ERROR {icon}: no glyph for {missing} — skip", file=sys.stderr)
                continue
            tileoff = TILEOFF[icon]
            g = _read_icon(rom, base, tileoff)
            pill = g[8][0]  # rows 8-9 are the solid pill colour
            if not dry_run:
                _stamp_name(g, fr, pill)
                _write_icon(rom, base, tileoff, g)
            patched += 1
        print(f"  base 0x{base:07X}: {len(FR_NAME)} type icon(s) → French")
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
    print(f"patch_type_icons_fr: {n} icon(s) patched across {len(BASES)} copies{suffix}")


if __name__ == "__main__":
    main()
