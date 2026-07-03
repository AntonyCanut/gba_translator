#!/usr/bin/env python3
"""Translate the 4 DexNav column-header graphics to Italian.

Sibling of ``patch_dexnav_headers_fr.py`` / ``patch_dexnav_headers_de.py`` —
identical LZ77 block layout, palette reuse and recompression machinery; only
the baked header text differs (Italian draws "LIVELLO RIC / METODO / AB.
NASCOSTA / OGGETTI").

Unlike the German port, Italian needs NO new glyphs: every letter in the four
Italian labels is already present in the shared 6-row header font (drawn for
the French/German ports).

The DexNav screen (route encounter tracker) shows four column headers —
"SEARCH LEVEL", "METHOD", "HIDDEN ABILITY", "HELD ITEMS" — that are NOT text
read from any string table: Pokémon Unbound draws its own custom DexNav
background (``DexNavBGUnboundTiles`` / ``DexNavBGUnboundMap`` /
``DexNavBGUnboundPal`` in ``src/dexnav.c``, an Unbound-specific asset that is
not part of the public Complete-Fire-Red-Upgrade repo) with these labels
baked into 4bpp tile pixels, inside an LZ77-compressed block.

Layout in the ROM (byte-identical between the EN source and every generic
build — the block is EN==ES stable and left untouched by the text pipeline
and the LZ77 repair passes, so the Italian build still holds the English art
here until this patch runs). See ``patch_dexnav_headers_de.py`` for the full
geometry notes (tileset/tilemap/palette offsets, the zero-padding compression
budget constraint, and why only rows 2-7 of each tile hold letter pixels).

"Abilità Nascosta" (Hidden Ability) does not fit the 9 dedicated tiles (72px)
at full length, so it is abbreviated to "AB. NASCOSTA" — the same abbreviation
strategy the German port uses for "Versteckte Fähigkeit" -> "Verst. Fäh.".

Usage::

    python3 languages/it/patches/dexnav_headers.py --rom output/roms/GenedRom-it.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import lz77_compress, lz77_decompress  # noqa: E402
from languages.de.patches.dexnav_headers import (  # noqa: E402
    _FONT,
    _glyph_w,
    _stamp_text,
    _text_width,
    _tiles_hex,
    TILE,
    TILESET_OFFSET,
    TILESET_DECOMP_LEN,
    TEXT_ROWS,
    FILL,
    BG,
)

# (map-row, first tile index, number of dedicated tiles, Italian text,
#  known-good English tile hex). Row/tile geometry and known-good fingerprints
#  are identical to the FR/DE ports — same untouched English source art.
HEADERS = [
    (
        6, 32, 10, "LIVELLO RIC",
        "9999aaaa99999999797777777997999779797797797977977997799779779797"
        "aaaaaaaa99999999777777779979977977777997777779979977999977777997",
    ),
    (
        9, 53, 5, "METODO",
        "c9ccccccc9cccccc797777777979777979797779799997797979797979797779"
        "cccccccccccccccc777777779999979979777797797777979979779779777797",
    ),
    (
        12, 92, 9, "AB. NASCOSTA",
        "c9ccccccc9cccccc797777777979979779799777797997777999997779799777"
        "cccccccccccccccc777777779997997779977779799777797997777979977779",
    ),
    (
        15, 112, 7, "OGGETTI",
        "c9ccccccc9cccccc797777777979979779799797797997977999999779799797"
        "cccccccccccccccc777777779979797777777977777779779977797777777977",
    ),
]


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
    for _row, first_tile, ntiles, italian, known_good in HEADERS:
        current = _tiles_hex(tiles, first_tile, ntiles)
        if current != known_good:
            # Already patched (idempotent re-run) or unexpected content.
            print(f"  dexnav header @tile {first_tile}: not the known English art — skip")
            continue
        _stamp_text(tiles, first_tile, ntiles, italian)
        patched += 1
        print(f"  dexnav header @tile {first_tile}: -> {italian!r}")

    if patched and _recompress_in_place(rom, TILESET_OFFSET, bytes(tiles), orig_comp_len):
        rom_path.write_bytes(rom)
        return patched
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-it.gba"))
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    n = apply_patches(args.rom)
    print(f"patch_dexnav_headers_it: {n} header(s) patched")


if __name__ == "__main__":
    main()
