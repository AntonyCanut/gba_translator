#!/usr/bin/env python3
"""Patch all status-condition badge graphics to French abbreviations.

The status badges (PSN, SLP, BRN, FRZ, PAR, FNT …) are stored as
LZ77-compressed 4bpp tile sets.  Each 32-tile block encodes 8 badge slots
of 4 tiles each:
  [left_border_tile][content_tile1][content_tile2][right_border_tile]

Slot layout (verified by decoding block 0x0B1E11C of englishrom.gba, then
replaced pixel-for-pixel from languages/fr/sprites/status_badges.bmp, the
editable reference art supplied in the follow-up to GitHub issue #143):
  slot 0 (pal4,  purple) : PSN  → POI  (Poison)
  slot 1 (pal6,  yellow) : PAR  → PAR  (unchanged)
  slot 2 (pal8,  blue)   : SLP  → SOM  (Sommeil)
  slot 3 (pal10, cyan)   : FRZ  → GEL  (Gelé)
  slot 4 (pal12, red)    : BRN  → BRU  (Brûlure)
  slot 5 (pal4)          : PKRS (Pokérus)
  slot 6 (pal14, gray)   : FNT  → KO   (fainted, 2-letter badge)
  slot 7                 : empty

The BMP uses border palette index 9. Two target blocks use index 1 instead;
only those border pixels are remapped so every screen keeps its own palette.

This script MUST run AFTER repair_stable_lz77_blocks.py and
repair_localized_lz77_blocks.py so that block 0x0B1E11C is restored to the
English FNT tiles (stable block) and block 0x0B1E280 to the Spanish DEB tiles
(localized block) before we overwrite with French badges.
"""

from __future__ import annotations

import argparse
import sys
from functools import lru_cache
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import lz77_compress, lz77_decompress  # noqa: E402
from src.graphics.sprite_image import read_indexed_image  # noqa: E402
from src.graphics.sprite_rom import grid_to_tiles  # noqa: E402

# LZ77 blocks that contain the 8-slot status badge tile set.
BADGE_BLOCKS: list[int] = [
    0x0B1E11C,   # stable EN block (restored by repair_stable_lz77_blocks.py)
    0x0B1E280,   # localized block (set to ES « DEB » by repair_localized_lz77_blocks.py)
    0x00E82EA0,  # secondary badge set
    0x00E9BF48,  # secondary badge set
]

BADGE_ASSET = ROOT_DIR / "languages/fr/sprites/status_badges.bmp"
_BADGE_WIDTH = 32
_BADGE_HEIGHT = 64
_CANONICAL_BORDER = 0x9
_SOURCE_ROM = ROOT_DIR / "input/roms/englishrom.gba"

_TILE_BYTES = 32          # bytes per 4bpp 8×8 tile
_TILES_PER_BADGE = 4      # left_border + content1 + content2 + right_border
def _read_slot_border(tiles: bytearray, slot: int) -> int:
    """Read the palette index from the unmodified right-cap border tile."""
    right_cap = (
        slot * _TILES_PER_BADGE * _TILE_BYTES
        + 3 * _TILE_BYTES
    )
    return tiles[right_cap] & 0xF


def _load_badge_grid() -> list[list[int]]:
    """Charge et valide la planche BMP canonique fournie pour l’issue #143."""
    width, height, grid = read_indexed_image(BADGE_ASSET)
    if (width, height) != (_BADGE_WIDTH, _BADGE_HEIGHT):
        raise ValueError(
            f"{BADGE_ASSET}: expected {_BADGE_WIDTH}x{_BADGE_HEIGHT}, "
            f"got {width}x{height}"
        )
    return grid


def _adapt_border_indices(
    grid: list[list[int]],
    target_tiles: bytearray,
) -> list[list[int]]:
    """Adapte la bordure canonique aux indices propres au bloc cible."""
    adapted = [row.copy() for row in grid]
    for slot in range(7):
        target_border = _read_slot_border(target_tiles, slot)
        if target_border == _CANONICAL_BORDER:
            continue
        first_row = slot * 8
        for y in range(first_row, first_row + 8):
            adapted[y] = [
                target_border if pixel == _CANONICAL_BORDER else pixel
                for pixel in adapted[y]
            ]
    return adapted


@lru_cache(maxsize=len(BADGE_BLOCKS))
def _reference_capacity(offset: int) -> int:
    """Retourne la longueur du flux source qui définit l’emplacement réservé."""
    if not _SOURCE_ROM.exists():
        return 0
    result = lz77_decompress(_source_rom_bytes(), offset)
    return result[1] if result is not None else 0


@lru_cache(maxsize=1)
def _source_rom_bytes() -> bytes:
    """Charge une seule fois la ROM source utilisée comme référence de capacité."""
    return _SOURCE_ROM.read_bytes()


def _patch_block(
    rom: bytearray,
    offset: int,
    badge_grid: list[list[int]],
) -> bool:
    """Decompress block at `offset`, apply all FR status patches, recompress."""
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
    adapted_grid = _adapt_border_indices(badge_grid, tiles)
    tiles[: 32 * _TILE_BYTES] = grid_to_tiles(adapted_grid, 4, 8)

    compressed = lz77_compress(bytes(tiles))
    if offset + len(compressed) > len(rom):
        print(
            f"  WARN 0x{offset:08X}: recompressed size {len(compressed)} overflows ROM — skip",
            file=sys.stderr,
        )
        return False

    capacity = max(comp_len, _reference_capacity(offset))
    if len(compressed) > capacity:
        extra = rom[offset + capacity : offset + len(compressed)]
        if any(b not in (0x00, 0xFF) for b in extra):
            print(
                f"  WARN 0x{offset:08X}: recompressed ({len(compressed)}) > original "
                f"capacity ({capacity}) and tail is non-padding — skip",
                file=sys.stderr,
            )
            return False

    rom[offset : offset + len(compressed)] = compressed
    print(f"  0x{offset:08X}  planche BMP injectée")
    return True


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    rom = bytearray(rom_path.read_bytes())
    badge_grid = _load_badge_grid()
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
        ok = _patch_block(rom, block_off, badge_grid)
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
    print(f"patch_status_badges_fr: {n} block(s) patched{suffix}")


if __name__ == "__main__":
    main()
