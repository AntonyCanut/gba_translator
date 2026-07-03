#!/usr/bin/env python3
"""Translate the 4 DexNav column-header graphics to German.

Sibling of ``patch_dexnav_headers_fr.py`` — identical LZ77 block layout,
palette reuse and recompression machinery; only the baked header text differs
(French draws "NIVEAU RECH / METHODE / TALENT CACHE / OBJETS", German draws
"SUCHLEVEL / METHODE / VERST. FAEH. / ITEMS").

The German header text is deliberately abbreviated ("Verst. Fäh." for
"Versteckte Fähigkeit", "Items" for the held-item column): the recompressed
tileset must stay within the original 1176-byte compressed length (see below),
and the denser German letters cost more compressed bytes than the shorter
French words, so the labels are trimmed to keep the block under budget.

The DexNav screen (route encounter tracker) shows four column headers —
"SEARCH LEVEL", "METHOD", "HIDDEN ABILITY", "HELD ITEMS" — that are NOT text
read from any string table: Pokémon Unbound draws its own custom DexNav
background (``DexNavBGUnboundTiles`` / ``DexNavBGUnboundMap`` /
``DexNavBGUnboundPal`` in ``src/dexnav.c``, an Unbound-specific asset that is
not part of the public Complete-Fire-Red-Upgrade repo) with these labels
baked into 4bpp tile pixels, inside an LZ77-compressed block.

Layout in the ROM (byte-identical between the EN source and every generic
build — the block is EN==ES stable and left untouched by the text pipeline
and the LZ77 repair passes, so the German build still holds the English art
here until this patch runs):

  * 0x00B14FA0 — LZ77 tileset (134 tiles / 4288 bytes decompressed)
  * 0x00B15438 — LZ77 tilemap (32x20 screen entries / 1280 bytes) — NOT
    modified; the header text tiles are redrawn in place at their existing
    map indices instead of remapping cells, so byte-for-byte identical map
    data still renders correctly.
  * 0x00B1560A — raw (uncompressed) 16-colour palette — NOT modified; the
    German replacement text reuses the two colours already used by the
    English text (index 9 = light grey fill, index 7 = purple banner bg).

Each header occupies a single tile-row (8px tall) within a fixed run of
dedicated tile indices (not shared with any other header). Only rows 2-7 of
each tile hold letter pixels; rows 0-1 are a decorative top divider/highlight
that differs per tile and MUST be preserved untouched.

Because the tileset is immediately followed by the tilemap with zero gap
(0x00B14FA0 + compressed 1176 bytes == 0x00B15438 exactly), there is no
padding tolerance: the recompressed tileset must not exceed its original
1176-byte compressed length, or it will overwrite the tilemap's own LZ77
header. ``apply_patches`` refuses to write if that happens.

German uses "AE" for the ä of "Fähigkeit" because the 6-pixel letter band
(tile rows 2-7) leaves no room above a glyph for the umlaut dots — rows 0-1
are the reserved decorative divider — so the standard umlaut-free digraph is
drawn instead.

Usage::

    python3 scripts/patch_dexnav_headers_de.py --rom output/roms/GenedRom-de.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.patch_font_fr import lz77_compress, lz77_decompress  # noqa: E402

TILE = 32  # bytes per 4bpp 8x8 tile

TILESET_OFFSET = 0x00B14FA0
TILESET_DECOMP_LEN = 4288

FILL = 9   # light-grey letter fill (palette index), matches the English text
BG = 7     # dark-purple banner background (palette index)

# A compact 6-row uppercase font sized for the header's letter band (tile
# rows 2-7). Rows 0-1 of every tile are a decorative divider preserved as-is.
_FONT: dict[str, list[str]] = {
    "A": ["0110", "1001", "1001", "1111", "1001", "1001"],
    "B": ["1110", "1001", "1110", "1001", "1001", "1110"],
    "C": ["0111", "1000", "1000", "1000", "1000", "0111"],
    "D": ["1110", "1001", "1001", "1001", "1001", "1110"],
    "E": ["1111", "1000", "1110", "1000", "1000", "1111"],
    "F": ["1111", "1000", "1110", "1000", "1000", "1000"],
    "G": ["0111", "1000", "1000", "1011", "1001", "0111"],
    "H": ["1001", "1001", "1111", "1001", "1001", "1001"],
    "I": ["1", "1", "1", "1", "1", "1"],
    "J": ["001", "001", "001", "001", "101", "010"],
    "K": ["1001", "1010", "1100", "1100", "1010", "1001"],
    "L": ["100", "100", "100", "100", "100", "111"],
    "M": ["10001", "11011", "10101", "10001", "10001", "10001"],
    "N": ["1001", "1101", "1011", "1001", "1001", "1001"],
    "O": ["0110", "1001", "1001", "1001", "1001", "0110"],
    "R": ["1110", "1001", "1110", "1010", "1001", "1001"],
    "S": ["0111", "1000", "0110", "0001", "0001", "1110"],
    "T": ["111", "010", "010", "010", "010", "010"],
    "U": ["1001", "1001", "1001", "1001", "1001", "0110"],
    "V": ["101", "101", "101", "101", "010", "010"],
    ".": ["0", "0", "0", "0", "0", "1"],
}

TEXT_ROWS = range(2, 8)  # the 6 letter-bearing pixel rows within each tile


def _glyph_w(ch: str) -> int:
    return len(_FONT[" "] if ch == " " else _FONT[ch][0])


_FONT[" "] = ["000"]  # 3px blank — width only, never drawn


def _text_width(text: str) -> int:
    return sum(_glyph_w(c) for c in text) + (len(text) - 1)


# (map-row, first tile index, number of dedicated tiles, German text,
#  known-good English tile hex — for the "already patched?" / "unexpected
#  content" strict guard, same convention as patch_dexnav_headers_fr.py). The
#  known-good hex is the English source art, byte-identical in the German
#  build (verified: the block is EN==ES stable and untouched by the pipeline).
HEADERS = [
    (
        6, 32, 10, "SUCHLEVEL",
        "9999aaaa99999999797777777997999779797797797977977997799779779797"
        "aaaaaaaa99999999777777779979977977777997777779979977999977777997",
    ),
    (
        9, 53, 5, "METHODE",
        "c9ccccccc9cccccc797777777979777979797779799997797979797979797779"
        "cccccccccccccccc777777779999979979777797797777979979779779777797",
    ),
    (
        12, 92, 9, "VERST. FAEH.",
        "c9ccccccc9cccccc797777777979979779799777797997777999997779799777"
        "cccccccccccccccc777777779997997779977779799777797997777979977779",
    ),
    (
        15, 112, 7, "ITEMS",
        "c9ccccccc9cccccc797777777979979779799797797997977999999779799797"
        "cccccccccccccccc777777779979797777777977777779779977797777777977",
    ),
]


def _stamp_text(tiles: bytearray, first_tile: int, ntiles: int, text: str) -> None:
    """Clear the letter band (rows 2-7) of ``ntiles`` dedicated tiles to the
    banner background colour, then draw ``text`` left-aligned in it."""
    width_avail = ntiles * 8
    width_needed = _text_width(text)
    if width_needed > width_avail:
        raise ValueError(
            f"{text!r} needs {width_needed}px but only {width_avail}px available"
        )

    def px_set(col: int, row: int, val: int) -> None:
        tile = first_tile + col // 8
        off = tile * TILE + row * 4 + (col % 8) // 2
        b = tiles[off]
        if (col % 8) % 2 == 0:
            tiles[off] = (b & 0xF0) | val
        else:
            tiles[off] = (b & 0x0F) | (val << 4)

    for row in TEXT_ROWS:
        for col in range(width_avail):
            px_set(col, row, BG)

    x = 0
    for ch in text:
        rows = _FONT[ch]
        w = len(rows[0])
        if ch != " ":
            for gy, bits in enumerate(rows):
                row = 2 + gy
                for gx, bit in enumerate(bits):
                    if bit == "1":
                        px_set(x + gx, row, FILL)
        x += w + 1


def _tiles_hex(tiles: bytearray, first_tile: int, ntiles: int) -> str:
    start = first_tile * TILE
    return bytes(tiles[start:start + 2 * TILE]).hex()  # first 2 tiles is enough to fingerprint


def _recompress_in_place(rom: bytearray, offset: int, tiles: bytes, orig_comp_len: int) -> bool:
    compressed = lz77_compress(tiles)
    if len(compressed) > orig_comp_len:
        print(
            f"  WARN dexnav headers: recompressed ({len(compressed)}) > original "
            f"({orig_comp_len}) and the tilemap follows with zero padding — skip",
            file=sys.stderr,
        )
        return False
    rom[offset:offset + len(compressed)] = compressed
    return True


def apply_patches(rom_path: Path) -> int:
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")

    result = lz77_decompress(rom, TILESET_OFFSET)
    if result is None:
        print("  WARN dexnav headers: cannot decompress tileset block — skip", file=sys.stderr)
        return 0
    tiles_data, orig_comp_len = result
    if len(tiles_data) != TILESET_DECOMP_LEN:
        print(
            f"  WARN dexnav headers: tileset decompressed to {len(tiles_data)} bytes, "
            f"expected {TILESET_DECOMP_LEN} — skip",
            file=sys.stderr,
        )
        return 0

    tiles = bytearray(tiles_data)
    patched = 0
    for _row, first_tile, ntiles, german, known_good in HEADERS:
        current = _tiles_hex(tiles, first_tile, ntiles)
        if current != known_good:
            # Already patched (idempotent re-run) or unexpected content.
            print(f"  dexnav header @tile {first_tile}: not the known English art — skip")
            continue
        _stamp_text(tiles, first_tile, ntiles, german)
        patched += 1
        print(f"  dexnav header @tile {first_tile}: -> {german!r}")

    if patched and _recompress_in_place(rom, TILESET_OFFSET, bytes(tiles), orig_comp_len):
        rom_path.write_bytes(rom)
        return patched
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-de.gba"))
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    n = apply_patches(args.rom)
    print(f"patch_dexnav_headers_de: {n} header(s) patched")


if __name__ == "__main__":
    main()
