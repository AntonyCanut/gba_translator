#!/usr/bin/env python3
"""Redraw the move-type icon names in Italian inside the type-icon graphic.

Italian port of ``patch_type_icons_fr.py`` / ``patch_type_icons_de.py`` — see
those files for the full geometry notes. The Pokémon summary screen (Infos /
move menu) shows each move's type as a small graphical badge with the type
name baked into 4bpp pixels (« ROCK », « DARK »). These are NOT text read from
any string table, so patching gTypeNames has no effect — the name lives in a
tile graphic indexed by the CFRU ``typeicon`` table.

There are TWO byte-identical copies of the 16-tile-wide sheet in the ROM:
  * 0xB1EC64 — summary screen (Infos type badges)
  * 0x961A00 — battle move menu
Both are patched so every type display is Italian.

Italian needs only ONE glyph absent from the shared FR/DE badge font: **Q**
(for ACQUA / Water). Every other Italian type name reuses letters already
drawn for French or German. Two names overflow the 32px pill and are
truncated the same way the FR/DE ports abbreviate overlong words:
  * Ghiaccio (Ice)  -> GHIACC
  * Folletto (Fairy) -> FOLLETT

NORMAL is identical enough to the English art (only trailing E differs) and,
like the FR/DE ports, is left untouched. Idempotent: re-running renders the
same Italian name again.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The two byte-identical copies of the type-icon sheet (tile 0 of each).
BASES = [0xB1EC64, 0x961A00]

# type name -> first tile index of its 4x3-tile icon within a sheet.
# Identical across FR/DE/IT — verified by decoding both English sheets.
TILEOFF = {
    "Fight": 0x64, "Flying": 0x60, "Poison": 0x80, "Ground": 0x48,
    "Rock": 0x44, "Bug": 0x6C, "Ghost": 0x68, "Steel": 0x88,
    "Fire": 0x24, "Water": 0x28, "Grass": 0x2C, "Electric": 0x40,
    "Psychic": 0x84, "Ice": 0x4C, "Dragon": 0xA0, "Dark": 0x8C,
    "Fairy": 0xA8,
}

# Fairy is a CFRU-ADDED type; unlike the vanilla badges (same offset in both
# sheets) its badge lives at a DIFFERENT tile offset in each copy — see the
# FR/DE ports for the full explanation.
TILEOFF_OVERRIDE = {
    0xB1EC64: {"Fairy": 0x100},
}


def _tileoff(base: int, icon: str) -> int:
    """Tile offset of ``icon`` within the sheet at ``base`` (per-copy override)."""
    return TILEOFF_OVERRIDE.get(base, {}).get(icon, TILEOFF[icon])


# Italian type names (uppercase, no accents — the icon font has none).
# GHIACC abbreviates Ghiaccio (Ice) and FOLLETT abbreviates Folletto (Fairy) to
# fit the 32px pill; every other name fits at full length (several — VOLANTE,
# SPETTRO, ACCIAIO, ELETTRO — land exactly on 32px).
IT_NAME = {
    "Fight": "LOTTA", "Flying": "VOLANTE", "Poison": "VELENO", "Ground": "TERRA",
    "Rock": "ROCCIA", "Bug": "INSETTO", "Ghost": "SPETTRO", "Steel": "ACCIAIO",
    "Fire": "FUOCO", "Water": "ACQUA", "Grass": "ERBA", "Electric": "ELETTRO",
    "Psychic": "PSICO", "Ice": "GHIACC", "Dragon": "DRAGO", "Dark": "BUIO",
    "Fairy": "FOLLETT",
}

_FILL = 15      # white letter fill (palette index)
_SHADOW = 14    # drop-shadow (palette index)
# Each icon is 4x3 tiles (32x24 px). The coloured pill spans rows 8-19; the
# type name is 8 px tall and occupies rows 10-17 (spilling into the third tile
# row). The whole 10-17 band MUST be cleared, or the bottom rows of the old
# English word survive below the (shorter) Italian name.
_TEXT_TOP = 10  # first pixel row of the name within the cell
_TEXT_ROWS = range(10, 18)

# The game's OWN 7-row uppercase badge font, extracted pixel-for-pixel from the
# English type sheet (shared with the FR/DE ports). Q is hand-drawn in the
# same style as O, with a short diagonal tail — needed only by ACQUA.
_FONT = {
    "A": ["0110", "1001", "1001", "1111", "1001", "1001", "1001"],
    "B": ["1110", "1001", "1001", "1110", "1001", "1001", "1110"],
    "C": ["0110", "1001", "1000", "1000", "1001", "1001", "0110"],
    "D": ["1110", "1001", "1001", "1001", "1001", "1001", "1110"],
    "E": ["1111", "1000", "1000", "1110", "1000", "1000", "1111"],
    "F": ["1111", "1000", "1000", "1110", "1000", "1000", "1000"],
    "G": ["0110", "1001", "1000", "1011", "1001", "1001", "0110"],
    "H": ["1001", "1001", "1001", "1111", "1001", "1001", "1001"],
    "I": ["111", "010", "010", "010", "010", "010", "111"],
    "L": ["1000", "1000", "1000", "1000", "1000", "1000", "1111"],
    "N": ["1001", "1101", "1101", "1011", "1011", "1001", "1001"],
    "O": ["0110", "1001", "1001", "1001", "1001", "1001", "0110"],
    "P": ["1110", "1001", "1001", "1110", "1000", "1000", "1000"],
    "Q": ["0110", "1001", "1001", "1001", "1001", "1011", "0111"],
    "R": ["1110", "1001", "1001", "1110", "1001", "1001", "1001"],
    "S": ["0110", "1001", "1000", "0110", "0001", "1001", "0110"],
    "T": ["111", "010", "010", "010", "010", "010", "010"],
    "U": ["1001", "1001", "1001", "1001", "1001", "1001", "0110"],
    "V": ["101", "101", "101", "101", "101", "101", "010"],
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
        for gy in range(len(rows)):
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
        for icon, it in IT_NAME.items():
            missing = [c for c in it if c not in _FONT]
            if missing:
                print(f"  ERROR {icon}: no glyph for {missing} — skip", file=sys.stderr)
                continue
            if _name_width(it) > 32:
                print(f"  ERROR {icon}: '{it}' too wide ({_name_width(it)}px) — skip",
                      file=sys.stderr)
                continue
            tileoff = _tileoff(base, icon)
            g = _read_icon(rom, base, tileoff)
            pill = g[8][0]  # rows 8-9 are the solid pill colour
            if not dry_run:
                _stamp_name(g, it, pill)
                _write_icon(rom, base, tileoff, g)
            patched += 1
        print(f"  base 0x{base:07X}: {len(IT_NAME)} type icon(s) → Italian")
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
    print(f"patch_type_icons_it: {n} icon(s) patched across {len(BASES)} copies{suffix}")


if __name__ == "__main__":
    main()
