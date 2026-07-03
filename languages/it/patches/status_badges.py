#!/usr/bin/env python3
"""Patch all status-condition badge graphics to Italian abbreviations.

Sibling of ``patch_status_badges_fr.py`` / ``patch_status_badges_de.py`` —
same LZ77 tile layout, different letter glyphs and slot mapping. The
in-battle status badges (PSN, SLP, BRN, FRZ, PAR, FNT …) are stored as
LZ77-compressed 4bpp tile sets. Each 32-tile block encodes 8 badge slots of 4
tiles each:
  [left_border_tile][content_tile1][content_tile2][right_border_tile]

Slot layout (verified by decoding block 0x0B1E11C of englishrom.gba — this is
the fixed engine order, identical to the one the FR/DE patches rely on):
  slot 0 (pal4,  purple) : PSN  → PSN  (unchanged — Italian keeps « PSN »)
  slot 1 (pal6,  yellow) : PAR  → PAR  (unchanged — Italian keeps « PAR »)
  slot 2 (pal8,  blue)   : SLP  → SON  (Sonno)
  slot 3 (pal10, cyan)   : FRZ  → CON  (Congelato)
  slot 4 (pal12, red)    : BRN  → SCT  (Scottatura)
  slot 5 (pal4)          : TOX? → unchanged (garbled / unused)
  slot 6 (pal14, gray)   : FNT  → KO   (fainted, 2-letter badge, K.O.)
  slot 7                 : empty

These 3-letter IT abbreviations (SON/CON/SCT) match the official Italian
localisation and the text ``status_abbrev`` block in ``languages/it/lang.yaml``.
The KO badge is shared verbatim with the FR/DE patches (« K.O. » is the same
in all three languages).

Badge tile anatomy (8×8 px each, border color = palette idx 9):
  - Row 0 / Row 7: all palette-9 border pixels
  - Rows 1–6: letter pixels (color 2 = white) on bg color (varies by slot)

3-letter badge layout in the 16-px letter area (tiles 1+2 side by side):
  col  : 0   1  2  3  4   5   6  7  8  9  10  11  12  13  14  15
  role : m  L1 L1 L1 L1  sep L2 L2 L2 L2  sep L3  L3  L3  L3   m
where m = margin, sep = separator, L1/L2/L3 = letter pixels (4px wide each).

This script MUST run AFTER repair_stable_lz77_blocks.py and
repair_localized_lz77_blocks.py so that block 0x0B1E11C is restored to the
English FNT tiles (stable block) and block 0x0B1E280 to the Spanish DEB tiles
(localized block) before we overwrite with Italian badges.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import lz77_compress, lz77_decompress  # noqa: E402

# LZ77 blocks that contain the 8-slot status badge tile set (language-agnostic
# offsets — same blocks the FR/DE patches touch).
BADGE_BLOCKS: list[int] = [
    0x0B1E11C,   # stable EN block (restored by repair_stable_lz77_blocks.py)
    0x0B1E280,   # localized block (set to ES « DEB » by repair_localized_lz77_blocks.py)
    0x00E82EA0,  # secondary badge set
    0x00E9BF48,  # secondary badge set
]

_TILE_BYTES = 32          # bytes per 4bpp 8×8 tile
_TILES_PER_BADGE = 4      # left_border + content1 + content2 + right_border
_CONTENT1_IDX = 1         # offset within badge: content tile 1
_CONTENT2_IDX = 2         # offset within badge: content tile 2

_LET = 0x2   # white letter   (palette 2)
_BRD = 0x9   # border color   (palette 9)

# ── Letter pixel art (6 rows × 4 columns, True = letter pixel) ──────────────
_L = True
_B = False

# S/O are shared pixel-for-pixel with the FR/DE badge fonts (identical
# shapes); C is shared with the DE font. N and T are new — Italian is the
# first badge port that needs them.
_LETTERS: dict[str, list[list[bool]]] = {
    # S extracted pixel-for-pixel from the English SLP badge (curved, not blocky)
    "S": [[_B,_L,_L,_B],[_L,_B,_B,_L],[_L,_L,_B,_B],[_B,_B,_L,_L],[_L,_B,_B,_L],[_B,_L,_L,_B]],
    "O": [[_B,_L,_L,_B],[_L,_B,_B,_L],[_L,_B,_B,_L],[_L,_B,_B,_L],[_L,_B,_B,_L],[_B,_L,_L,_B]],
    "C": [[_B,_L,_L,_L],[_L,_B,_B,_B],[_L,_B,_B,_B],[_L,_B,_B,_B],[_L,_B,_B,_B],[_B,_L,_L,_L]],
    # New Italian letters designed for 4px-wide, 6-row-tall badge cells
    "N": [[_L,_B,_B,_L],[_L,_L,_B,_L],[_L,_B,_L,_L],[_L,_B,_L,_L],[_L,_B,_B,_L],[_L,_B,_B,_L]],
    "T": [[_L,_L,_L,_L],[_B,_L,_L,_B],[_B,_L,_L,_B],[_B,_L,_L,_B],[_B,_L,_L,_B],[_B,_L,_L,_B]],
}

# ── Status slot patches ───────────────────────────────────────────────────────
# (slot_index, it_letter1, it_letter2, it_letter3)
# Slot 0 (PSN→PSN), slot 1 (PAR→PAR) and slot 5 (garbled) are intentionally
# excluded — the English art already reads correctly in Italian for PSN/PAR.
_STATUS_PATCHES: list[tuple[int, str, str, str]] = [
    (2, "S", "O", "N"),   # SLP → SON  (Sonno)
    (3, "C", "O", "N"),   # FRZ → CON  (Congelato)
    (4, "S", "C", "T"),   # BRN → SCT  (Scottatura)
]

# FNT→KO badge (2-letter, slot 6, bg=pal14). Identical to the FR/DE « K.O. » badge.
_FNT_SLOT = 6
_FNT_BG = 0xE   # gray background

_K: list[list[bool]] = [
    [_L,_B,_B,_L],
    [_L,_B,_L,_B],
    [_L,_L,_B,_B],
    [_L,_B,_L,_B],
    [_L,_B,_B,_L],
    [_L,_B,_B,_L],
]


def _encode_row(pixels: list[int]) -> bytes:
    """Pack 8 palette-index values into 4 bytes (4bpp little-endian nibbles)."""
    assert len(pixels) == 8
    return bytes([pixels[i] | (pixels[i + 1] << 4) for i in range(0, 8, 2)])


def _border_row() -> bytes:
    return _encode_row([_BRD] * 8)


def _make_3letter_tiles(
    l1: list[list[bool]],
    l2: list[list[bool]],
    l3: list[list[bool]],
    bg: int,
) -> tuple[bytes, bytes]:
    """Build (content1, content2) tiles for a 3-letter status badge.

    Layout: col0=margin, cols1-4=L1, col5=sep, cols6-9=L2, col10=sep,
            cols11-14=L3, col15=margin
    """
    def p(is_letter: bool) -> int:
        return _LET if is_letter else bg

    t1 = bytearray()
    t2 = bytearray()
    t1.extend(_border_row())
    t2.extend(_border_row())

    for r in range(6):
        row1 = [
            bg,
            p(l1[r][0]), p(l1[r][1]), p(l1[r][2]), p(l1[r][3]),
            bg,
            p(l2[r][0]), p(l2[r][1]),
        ]
        t1.extend(_encode_row(row1))

        row2 = [
            p(l2[r][2]), p(l2[r][3]),
            bg,
            p(l3[r][0]), p(l3[r][1]), p(l3[r][2]), p(l3[r][3]),
            bg,
        ]
        t2.extend(_encode_row(row2))

    t1.extend(_border_row())
    t2.extend(_border_row())
    assert len(t1) == _TILE_BYTES
    assert len(t2) == _TILE_BYTES
    return bytes(t1), bytes(t2)


def _make_ko_tiles() -> tuple[bytes, bytes]:
    """Return (content_tile1, content_tile2) bytes for the KO badge (2-letter)."""
    t1 = bytearray()
    t2 = bytearray()
    t1.extend(_border_row())
    t2.extend(_border_row())

    bg = _FNT_BG
    o = _LETTERS["O"]
    for r in range(6):
        k = _K[r]

        # Tile 1: col0=margin, cols1-4=K, col5=sep, cols6-7=O[0:2]
        row1 = [bg, _LET if k[0] else bg, _LET if k[1] else bg,
                _LET if k[2] else bg, _LET if k[3] else bg,
                bg, _LET if o[r][0] else bg, _LET if o[r][1] else bg]
        t1.extend(_encode_row(row1))

        # Tile 2: cols0-1=O[2:4], cols2-7=right margin
        row2 = [_LET if o[r][2] else bg, _LET if o[r][3] else bg,
                bg, bg, bg, bg, bg, bg]
        t2.extend(_encode_row(row2))

    t1.extend(_border_row())
    t2.extend(_border_row())
    assert len(t1) == _TILE_BYTES
    assert len(t2) == _TILE_BYTES
    return bytes(t1), bytes(t2)


def _read_slot_bg(tiles: bytearray, slot: int) -> int:
    """Read background palette index from slot's content tile margin pixel."""
    c1_off = slot * _TILES_PER_BADGE * _TILE_BYTES + _CONTENT1_IDX * _TILE_BYTES
    # Row 1 starts at byte 4 (after 4-byte border row). Byte 4 low nibble = col0 = margin = bg.
    return tiles[c1_off + 4] & 0xF


def _patch_block(rom: bytearray, offset: int) -> bool:
    """Decompress block at `offset`, apply all IT status patches, recompress."""
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
    changes: list[str] = []

    # ── 1. 3-letter status badges (SLP→SON, FRZ→CON, BRN→SCT) ────────────────
    for slot, a, b_ltr, c in _STATUS_PATCHES:
        bg = _read_slot_bg(tiles, slot)
        t1, t2 = _make_3letter_tiles(
            _LETTERS[a], _LETTERS[b_ltr], _LETTERS[c], bg
        )
        base = slot * _TILES_PER_BADGE * _TILE_BYTES
        c1_off = base + _CONTENT1_IDX * _TILE_BYTES
        c2_off = base + _CONTENT2_IDX * _TILE_BYTES
        tiles[c1_off : c1_off + _TILE_BYTES] = t1
        tiles[c2_off : c2_off + _TILE_BYTES] = t2
        changes.append(f"slot{slot}→{a}{b_ltr}{c}")

    # ── 2. Fainted badge FNT/DEB → KO (2-letter, slot 6) ─────────────────────
    ko_t1, ko_t2 = _make_ko_tiles()
    base6 = _FNT_SLOT * _TILES_PER_BADGE * _TILE_BYTES
    c1_off6 = base6 + _CONTENT1_IDX * _TILE_BYTES
    c2_off6 = base6 + _CONTENT2_IDX * _TILE_BYTES
    tiles[c1_off6 : c1_off6 + _TILE_BYTES] = ko_t1
    tiles[c2_off6 : c2_off6 + _TILE_BYTES] = ko_t2
    changes.append("slot6→KO")

    compressed = lz77_compress(bytes(tiles))
    if offset + len(compressed) > len(rom):
        print(
            f"  WARN 0x{offset:08X}: recompressed size {len(compressed)} overflows ROM — skip",
            file=sys.stderr,
        )
        return False

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
    print(f"  0x{offset:08X}  {', '.join(changes)}")
    return True


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
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
        ok = _patch_block(rom, block_off)
        if ok:
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
    print(f"patch_status_badges_it: {n} block(s) patched{suffix}")


if __name__ == "__main__":
    main()
