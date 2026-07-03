#!/usr/bin/env python3
"""Patch DE font glyphs for German umlauts (ä ö ü Ä Ö Ü) in a GBA ROM.

ß is already present in the charmap at 0x15 and has a glyph in the ROM's
international font block; this script only handles the six umlaut characters
assigned to free slots 0x60-0x65:

    0x60 = Ä   0x61 = Ö   0x62 = Ü
    0x63 = ä   0x64 = ö   0x65 = ü

Each umlaut glyph is built by combining the base letter's pixels with the
diaeresis dots extracted from the matching ë/Ë reference pair in the ROM.
"""

from __future__ import annotations

import argparse
import bisect
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

LZ77_MAGIC = 0x10
FONT_SIZE = 0x2000
GLYPH_SIZE = 32

# Charmap codepoints used as building blocks
CP_A_UC = 0xBB   # 'A'
CP_O_UC = 0xC9   # 'O'
CP_U_UC = 0xCF   # 'U'
CP_E_UC = 0xBF   # 'E'
CP_E_UC_DIAR = 0x08  # 'Ë'  — source of uppercase diaeresis dots

CP_A_LC = 0xD5   # 'a'
CP_O_LC = 0xE3   # 'o'
CP_U_LC = 0xE9   # 'u'
CP_E_LC = 0xD9   # 'e'
CP_E_LC_DIAR = 0x1D  # 'ë'  — source of lowercase diaeresis dots

# Target codepoints for German umlauts (assigned in charmap_data.py)
CP_A_UMLAUT_UC = 0x60  # 'Ä'
CP_O_UMLAUT_UC = 0x61  # 'Ö'
CP_U_UMLAUT_UC = 0x62  # 'Ü'
CP_A_UMLAUT_LC = 0x63  # 'ä'
CP_O_UMLAUT_LC = 0x64  # 'ö'
CP_U_UMLAUT_LC = 0x65  # 'ü'

WIDTH_TABLE_OFFSETS = [
    0x1FB100,
    0x207300,
    0x217618,
    0x227930,
]


class Lz77Block:
    def __init__(self, offset: int, compressed_len: int, decompressed: bytes) -> None:
        self.offset = offset
        self.compressed_len = compressed_len
        self.decompressed = decompressed


class FreeSpaceAllocator:
    """Allocate from ROM free regions: 0xFF runs with no live GBA pointer targets.

    Unlike the old trailing-only allocator, this scans the whole ROM so it works
    on generic-built ROMs (DE, IT) where the reinserter's relocations have eaten
    the large trailing 0xFF region (the pre-existing "Not enough free space to
    relocate font data" DE build failure). The scan is lazy — it only runs if
    ``allocate()`` is actually called, so there is no overhead for ROMs where all
    font blocks fit in-place. Mirrors languages/fr/patches/font.py.
    """

    MIN_FREE_BLOCK = 256

    def __init__(self, rom: bytearray) -> None:
        self.rom = rom
        self._free: Optional[List[List[int]]] = None  # [[cursor, end], …]

    def _build_free(self) -> List[List[int]]:
        data = bytes(self.rom)
        n = len(data)
        ROM_BASE = 0x08000000

        # Collect every 4-byte-aligned GBA pointer target.
        targets: List[int] = []
        for i in range(0, n - 3, 4):
            v = int.from_bytes(data[i : i + 4], "little")
            if ROM_BASE <= v < ROM_BASE + n:
                targets.append(v - ROM_BASE)
        targets.sort()

        # Find 0xFF runs of at least MIN_FREE_BLOCK bytes that contain no
        # pointer target → guaranteed free space safe to overwrite.
        regions: List[List[int]] = []
        i = 0
        while i < n:
            if data[i] == 0xFF:
                j = i
                while j < n and data[j] == 0xFF:
                    j += 1
                if j - i >= self.MIN_FREE_BLOCK:
                    idx = bisect.bisect_left(targets, i)
                    if idx >= len(targets) or targets[idx] >= j:
                        cursor = (i + 3) & ~3
                        if cursor < j:
                            regions.append([cursor, j])
                i = j
            else:
                i += 1

        # Largest regions first so the most common case (one allocation) is O(1).
        regions.sort(key=lambda r: -(r[1] - r[0]))
        return regions

    def allocate(self, size: int) -> int:
        if self._free is None:
            self._free = self._build_free()
        aligned = (size + 3) & ~3
        for region in self._free:
            cursor, end = region
            if cursor + aligned <= end:
                region[0] = cursor + aligned
                return cursor
        raise RuntimeError("Not enough free space to relocate font data.")


def lz77_decompress(data: bytes, offset: int) -> Optional[Tuple[bytes, int]]:
    if offset + 4 > len(data) or data[offset] != LZ77_MAGIC:
        return None
    size = data[offset + 1] | (data[offset + 2] << 8) | (data[offset + 3] << 16)
    if size <= 0:
        return None
    out = bytearray()
    src = offset + 4
    while len(out) < size:
        if src >= len(data):
            return None
        flags = data[src]
        src += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                if src + 1 >= len(data):
                    return None
                b1 = data[src]
                b2 = data[src + 1]
                src += 2
                disp = ((b1 & 0x0F) << 8) | b2
                length = (b1 >> 4) + 3
                disp += 1
                if disp > len(out):
                    return None
                for _ in range(length):
                    out.append(out[-disp])
                    if len(out) >= size:
                        break
            else:
                if src >= len(data):
                    return None
                out.append(data[src])
                src += 1
    return bytes(out), src - offset


def _lz77_best_match(data: bytes, pos: int, size: int) -> tuple:
    max_len = min(18, size - pos)
    window_start = max(0, pos - 0x1000)
    best_len = 0
    best_disp = 0
    for w in range(pos - 1, window_start - 1, -1):
        length = 0
        while length < max_len and data[w + length] == data[pos + length]:
            length += 1
        if length > best_len:
            best_len = length
            best_disp = pos - w
            if best_len == max_len:
                break
    return best_len, best_disp


def lz77_compress(data: bytes) -> bytes:
    size = len(data)
    out = bytearray()
    out.append(LZ77_MAGIC)
    out.extend((size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF))
    pos = 0
    while pos < size:
        flags_pos = len(out)
        out.append(0)
        flags = 0
        bit_i = 0
        while bit_i < 8 and pos < size:
            len0, disp0 = _lz77_best_match(data, pos, size)
            if len0 >= 3:
                len1 = 0
                if pos + 1 < size:
                    len1, _ = _lz77_best_match(data, pos + 1, size)
                if len1 > len0:
                    out.append(data[pos])
                    pos += 1
                else:
                    flags |= 1 << (7 - bit_i)
                    d = disp0 - 1
                    out.append(((len0 - 3) << 4) | ((d >> 8) & 0x0F))
                    out.append(d & 0xFF)
                    pos += len0
            else:
                out.append(data[pos])
                pos += 1
            bit_i += 1
        out[flags_pos] = flags
    return bytes(out)


def tile_to_pixels(tile: bytes) -> List[int]:
    pixels: List[int] = []
    for b in tile:
        pixels.append(b & 0x0F)
        pixels.append((b >> 4) & 0x0F)
    return pixels


def pixels_to_tile(pixels: Iterable[int]) -> bytes:
    pix_list = list(pixels)
    out = bytearray()
    for i in range(0, 64, 2):
        out.append((pix_list[i] & 0x0F) | ((pix_list[i + 1] & 0x0F) << 4))
    return bytes(out)


def glyph_pixels(font: bytes, codepoint: int) -> List[int]:
    start = codepoint * GLYPH_SIZE
    return tile_to_pixels(font[start:start + GLYPH_SIZE])


def glyph_density(font: bytes, codepoint: int) -> int:
    return sum(1 for p in glyph_pixels(font, codepoint) if p)


def is_font_block(font: bytes) -> bool:
    sample = [0xA1, 0xA2, 0xA3, 0xBB, 0xBC, 0xD5, 0xD7]
    in_range = [cp for cp in sample if 5 < glyph_density(font, cp) < 60]
    if len(in_range) < 4:
        return False
    # A real text font has visually distinct glyph shapes. Some non-font
    # LZ77 blocks are uniform placeholders where every "glyph" is the same
    # tile (e.g. a repeating 00 10 pattern of density 16) — these slip past
    # the density heuristic but must be rejected: their identical A/O/U base
    # letters would make Ä/Ö/Ü (and ä/ö/ü) collapse to a single glyph, and
    # they carry no Ë/ë diaeresis source to build real umlauts from anyway.
    distinct = {bytes(font[cp * GLYPH_SIZE:(cp + 1) * GLYPH_SIZE]) for cp in in_range}
    return len(distinct) >= 4


def find_font_blocks(rom: bytes) -> List[Lz77Block]:
    blocks: List[Lz77Block] = []
    header = bytes((LZ77_MAGIC, 0x00, 0x20, 0x00))
    start = 0
    while True:
        offset = rom.find(header, start)
        if offset == -1:
            break
        start = offset + 1
        ptr = (0x08000000 + offset).to_bytes(4, "little")
        if rom.find(ptr) == -1:
            continue
        result = lz77_decompress(rom, offset)
        if result is None:
            continue
        decompressed, compressed_len = result
        if len(decompressed) != FONT_SIZE:
            continue
        if is_font_block(decompressed):
            blocks.append(Lz77Block(offset, compressed_len, decompressed))
    return blocks


def dominant_color(pixels: Iterable[int]) -> int:
    counts = Counter([p for p in pixels if p])
    if not counts:
        return 1
    return counts.most_common(1)[0][0]


def extract_diaeresis_dots(font: bytes, with_diar_cp: int, base_cp: int) -> List[Tuple[int, int, int]]:
    """Return list of (x, y, color) pixels that form the diaeresis in `with_diar_cp` vs `base_cp`."""
    with_pix = glyph_pixels(font, with_diar_cp)
    base_pix = glyph_pixels(font, base_cp)
    dots = []
    for y in range(8):
        for x in range(8):
            idx = y * 8 + x
            if with_pix[idx] != 0 and base_pix[idx] == 0:
                dots.append((x, y, with_pix[idx]))
    return dots


def build_umlaut(font: bytes, base_cp: int, diar_dots: List[Tuple[int, int, int]]) -> bytes:
    """Build an umlaut glyph: shift base letter down if needed, then place diaeresis dots.

    Strategy:
      1. Find the topmost row occupied by diaeresis dots.
      2. Find the topmost row occupied by the base letter.
      3. If the dots would collide with the letter top, shift the letter down by the
         number of dot rows (at most 2), losing bottom pixels of the letter.
         This is unavoidable in an 8×8 grid — the result is still legible.
      4. Write dots at the computed positions.
    """
    if not diar_dots:
        return pixels_to_tile(glyph_pixels(font, base_cp))

    base_pix = glyph_pixels(font, base_cp)
    color = dominant_color(base_pix)

    # Normalise dots to start at row 0
    min_dot_y = min(y for _, y, _ in diar_dots)
    dots_normalised = [(x, y - min_dot_y, v) for x, y, v in diar_dots]
    dot_rows_needed = max(y for _, y, _ in dots_normalised) + 1  # typically 1 or 2

    # Find topmost row in base letter
    base_top = next(
        (y for y in range(8) if any(base_pix[y * 8 + x] for x in range(8))), 8
    )

    # Decide shift: shift only when the letter top would collide with dot rows
    shift = max(0, dot_rows_needed - base_top)
    shift = min(shift, 2)  # cap at 2 rows to avoid destroying the letter

    # Build shifted base
    out = [0] * 64
    for y in range(8 - shift):
        for x in range(8):
            out[(y + shift) * 8 + x] = base_pix[y * 8 + x]

    # Place diaeresis dots
    for x, y, val in dots_normalised:
        if y < 8:
            out[y * 8 + x] = val if val else color

    return pixels_to_tile(out)


def patch_width_tables(rom: bytearray, umlauts: List[Tuple[int, int]]) -> int:
    """Set umlaut glyph widths equal to their base letter widths in every width table."""
    patched = 0
    for offset in WIDTH_TABLE_OFFSETS:
        if offset + 0x100 > len(rom):
            continue
        for umlaut_cp, base_cp in umlauts:
            base_width = rom[offset + base_cp]
            if base_width == 0:
                continue
            if rom[offset + umlaut_cp] != base_width:
                rom[offset + umlaut_cp] = base_width
                patched += 1
    return patched


def repoint_pointers(rom: bytearray, old_offset: int, new_offset: int) -> int:
    old_ptr = (0x08000000 + old_offset).to_bytes(4, "little")
    new_ptr = (0x08000000 + new_offset).to_bytes(4, "little")
    count = 0
    start = 0
    while True:
        idx = rom.find(old_ptr, start)
        if idx == -1:
            break
        rom[idx:idx + 4] = new_ptr
        count += 1
        start = idx + 4
    return count


def apply_patches(rom: bytearray) -> Tuple[int, int, int]:
    blocks = find_font_blocks(rom)
    if not blocks:
        raise RuntimeError("No font blocks found to patch.")

    # Width-table pairs: (umlaut_cp, base_cp)
    width_pairs = [
        (CP_A_UMLAUT_UC, CP_A_UC),
        (CP_O_UMLAUT_UC, CP_O_UC),
        (CP_U_UMLAUT_UC, CP_U_UC),
        (CP_A_UMLAUT_LC, CP_A_LC),
        (CP_O_UMLAUT_LC, CP_O_LC),
        (CP_U_UMLAUT_LC, CP_U_LC),
    ]

    patched_fonts = 0
    relocated_fonts = 0
    allocator = FreeSpaceAllocator(rom)

    for block in blocks:
        font = bytearray(block.decompressed)
        original = bytes(font)

        # Extract diaeresis dots from Ë vs E (uppercase) and ë vs e (lowercase)
        uc_dots = extract_diaeresis_dots(original, CP_E_UC_DIAR, CP_E_UC)
        lc_dots = extract_diaeresis_dots(original, CP_E_LC_DIAR, CP_E_LC)

        umlaut_targets = [
            (CP_A_UMLAUT_UC, CP_A_UC, uc_dots),
            (CP_O_UMLAUT_UC, CP_O_UC, uc_dots),
            (CP_U_UMLAUT_UC, CP_U_UC, uc_dots),
            (CP_A_UMLAUT_LC, CP_A_LC, lc_dots),
            (CP_O_UMLAUT_LC, CP_O_LC, lc_dots),
            (CP_U_UMLAUT_LC, CP_U_LC, lc_dots),
        ]

        for target_cp, base_cp, dots in umlaut_targets:
            tile = build_umlaut(original, base_cp, dots)
            slot = slice(target_cp * GLYPH_SIZE, (target_cp + 1) * GLYPH_SIZE)
            if bytes(font[slot]) != tile:
                font[slot] = tile

        if bytes(font) == original:
            continue

        compressed = lz77_compress(bytes(font))
        if len(compressed) <= block.compressed_len:
            rom[block.offset:block.offset + len(compressed)] = compressed
            if len(compressed) < block.compressed_len:
                pad = block.offset + len(compressed)
                rom[pad:pad + block.compressed_len - len(compressed)] = b"\x00" * (block.compressed_len - len(compressed))
            patched_fonts += 1
            continue

        new_offset = allocator.allocate(len(compressed))
        rom[new_offset:new_offset + len(compressed)] = compressed
        repointed = repoint_pointers(rom, block.offset, new_offset)
        if repointed == 0:
            raise RuntimeError(
                f"No pointers found for relocated font at 0x{block.offset:06X}."
            )
        relocated_fonts += 1
        patched_fonts += 1

    patched_tables = patch_width_tables(rom, width_pairs)
    return patched_fonts, patched_tables, relocated_fonts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch German umlaut glyphs (ä ö ü Ä Ö Ü) in a GBA ROM font."
    )
    parser.add_argument("--rom", required=True, help="Path to the ROM to patch")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.exists():
        raise SystemExit(f"ROM not found: {rom_path}")

    rom = bytearray(rom_path.read_bytes())
    patched_fonts, patched_tables, relocated_fonts = apply_patches(rom)
    rom_path.write_bytes(rom)

    print(
        f"Patched {patched_fonts} font block(s), relocated {relocated_fonts} block(s), "
        f"and updated {patched_tables} width table entries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
