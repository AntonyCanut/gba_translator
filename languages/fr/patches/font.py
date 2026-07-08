#!/usr/bin/env python3
"""Patch FR font glyphs for French accents in a GBA ROM."""

from __future__ import annotations

import argparse
import bisect
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

LZ77_MAGIC = 0x10
FONT_SIZE = 0x2000
GLYPH_SIZE = 32
MIN_GLYPH_DENSITY = 5

CP_A = 0xD5
CP_ACUTE_A = 0x17
CP_GRAVE_A = 0x16
CP_C = 0xD7
CP_C_CEDILLA = 0x19
CP_E = 0xD9
CP_GRAVE_E = 0x1A
CP_ACUTE_E = 0x1B

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
    on generic-built ROMs (IT, DE) that lack a large trailing 0xFF region.
    The scan is lazy — it only runs if ``allocate()`` is actually called, so
    there is no overhead for ROMs where all font blocks fit in-place.
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
    """Find the longest back-reference at ``pos`` with overlapping-match support.

    Scans right-to-left (smallest displacement first) so ties resolve to the
    most-recent occurrence.  Handles overlapping matches (e.g. ABABAB) by
    comparing byte-by-byte against the source array rather than using rfind,
    which cannot find patterns that extend beyond the current window boundary.
    """
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
    """LZ77-compress *data* for GBA (header byte 0x10).

    Uses proper byte-by-byte overlapping match detection and one-step lazy
    evaluation (skip a short match at ``pos`` when ``pos+1`` offers a longer
    one) to approach GBA-tool compression quality.
    """
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
                # Lazy: if pos+1 yields a strictly longer match, emit a literal
                # at pos and let the next iteration use the better match.
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
    pixels = glyph_pixels(font, codepoint)
    return sum(1 for p in pixels if p)




def is_font_block(font: bytes) -> bool:
    sample = [0xA1, 0xA2, 0xA3, 0xBB, 0xBC, 0xD5, 0xD7]
    score = 0
    for cp in sample:
        density = glyph_density(font, cp)
        if 5 < density < 60:
            score += 1
    return score >= 4


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


def extract_cedilla_mask(font: bytes) -> List[Tuple[int, int]]:
    base = glyph_pixels(font, CP_C)
    cedilla = glyph_pixels(font, CP_C_CEDILLA)
    mask: List[Tuple[int, int]] = []
    for y in range(6, 8):
        for x in range(8):
            idx = y * 8 + x
            if base[idx] == 0 and cedilla[idx] != 0:
                mask.append((x, y))
    return mask


def dominant_color(pixels: Iterable[int]) -> int:
    counts = Counter([p for p in pixels if p])
    if not counts:
        return 1
    return counts.most_common(1)[0][0]


def acute_accent_positions(font: bytes) -> List[Tuple[int, int, int]]:
    """Extract the compact acute accent from ``á`` (rows 0-1 only).

    Returns the ``(x, y, value)`` pixels of the acute accent that differ from
    the bare base ``a`` glyph — i.e. the accent stroke itself, without the
    letter body.  This is the proven-good source used to rebuild ``à``, ``é``
    and ``è`` (the standalone é/è glyphs in the international font are drawn too
    high and crush the letter body, so we never copy them verbatim).

    Exclude edge pixels (x=0, x=7) to avoid rendering artifacts on small text.
    """
    base = glyph_pixels(font, CP_A)
    acute = glyph_pixels(font, CP_ACUTE_A)
    return [
        (x, y, acute[y * 8 + x])
        for y in range(2)
        for x in range(1, 7)  # Exclude edge pixels (x=0, x=7) to prevent phantom pixels
        if acute[y * 8 + x] != 0 and acute[y * 8 + x] != base[y * 8 + x]
    ]


def grave_shift(positions: List[Tuple[int, int, int]]) -> int:
    """Horizontal shift that turns the acute accent into a grave accent."""
    avg_x = sum(x for x, _, _ in positions) / len(positions)
    shift = int(round(avg_x - 1.0))
    return max(1, min(6, shift))


def overlay_accent(
    base: List[int], positions: List[Tuple[int, int, int]], shift: int = 0
) -> List[int]:
    """Overlay accent ``positions`` onto a copy of ``base`` (shifted left by
    ``shift``), keeping the darker pixel where they overlap."""
    out = base[:]
    for x, y, val in positions:
        nx = x - shift
        if 0 <= nx < 8:
            idx = y * 8 + nx
            if val > out[idx]:
                out[idx] = val
    return out


def build_grave_a(font: bytes) -> bytes:
    base = glyph_pixels(font, CP_A)
    positions = acute_accent_positions(font)
    if not positions:
        return pixels_to_tile(base)
    return pixels_to_tile(overlay_accent(base, positions, grave_shift(positions)))


def build_acute_e(font: bytes) -> bytes:
    """Rebuild ``é`` from the clean ``e`` body plus the compact acute accent."""
    base = glyph_pixels(font, CP_E)
    positions = acute_accent_positions(font)
    if not positions:
        return pixels_to_tile(base)
    return pixels_to_tile(overlay_accent(base, positions))


def build_grave_e(font: bytes) -> bytes:
    """Rebuild ``è`` from the clean ``e`` body plus the compact grave accent."""
    base = glyph_pixels(font, CP_E)
    positions = acute_accent_positions(font)
    if not positions:
        return pixels_to_tile(base)
    return pixels_to_tile(overlay_accent(base, positions, grave_shift(positions)))


def build_cedilla(font: bytes, fallback_mask: List[Tuple[int, int]]) -> bytes:
    base = glyph_pixels(font, CP_C)
    cedilla = glyph_pixels(font, CP_C_CEDILLA)

    local_mask = extract_cedilla_mask(font)
    use_mask = local_mask if len(local_mask) >= max(2, len(fallback_mask) // 2) else fallback_mask
    color = dominant_color(base)

    out = base[:]
    for x, y in use_mask:
        idx = y * 8 + x
        if out[idx] == 0:
            out[idx] = color

    return pixels_to_tile(out)


def patch_width_tables(rom: bytearray) -> int:
    patched = 0
    # Alias each accented glyph's advance width to its bare base letter so the
    # rebuilt à/é/è render with the same spacing as a/e.
    aliases = [
        (CP_GRAVE_A, CP_A),
        (CP_ACUTE_E, CP_E),
        (CP_GRAVE_E, CP_E),
    ]
    for offset in WIDTH_TABLE_OFFSETS:
        if offset + 0x100 > len(rom):
            continue
        for accent_cp, base_cp in aliases:
            base_width = rom[offset + base_cp]
            if base_width == 0:
                continue
            if rom[offset + accent_cp] != base_width:
                rom[offset + accent_cp] = base_width
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

    fallback_mask: List[Tuple[int, int]] = []
    for block in blocks:
        mask = extract_cedilla_mask(block.decompressed)
        if len(mask) > len(fallback_mask):
            fallback_mask = mask
    if not fallback_mask:
        fallback_mask = [(1, 7), (2, 7), (5, 7), (6, 7), (7, 7)]

    patched_fonts = 0
    relocated_fonts = 0
    allocator = FreeSpaceAllocator(rom)
    for block in blocks:
        font = bytearray(block.decompressed)
        original = bytes(font)
        grave_tile = build_grave_a(original)
        if font[CP_GRAVE_A * GLYPH_SIZE: (CP_GRAVE_A + 1) * GLYPH_SIZE] != grave_tile:
            font[CP_GRAVE_A * GLYPH_SIZE: (CP_GRAVE_A + 1) * GLYPH_SIZE] = grave_tile
        acute_e_tile = build_acute_e(original)
        if font[CP_ACUTE_E * GLYPH_SIZE: (CP_ACUTE_E + 1) * GLYPH_SIZE] != acute_e_tile:
            font[CP_ACUTE_E * GLYPH_SIZE: (CP_ACUTE_E + 1) * GLYPH_SIZE] = acute_e_tile
        grave_e_tile = build_grave_e(original)
        if font[CP_GRAVE_E * GLYPH_SIZE: (CP_GRAVE_E + 1) * GLYPH_SIZE] != grave_e_tile:
            font[CP_GRAVE_E * GLYPH_SIZE: (CP_GRAVE_E + 1) * GLYPH_SIZE] = grave_e_tile
        cedilla_tile = build_cedilla(original, fallback_mask)
        if font[CP_C_CEDILLA * GLYPH_SIZE: (CP_C_CEDILLA + 1) * GLYPH_SIZE] != cedilla_tile:
            font[CP_C_CEDILLA * GLYPH_SIZE: (CP_C_CEDILLA + 1) * GLYPH_SIZE] = cedilla_tile
        if bytes(font) == original:
            continue

        compressed = lz77_compress(bytes(font))
        if len(compressed) <= block.compressed_len:
            rom[block.offset:block.offset + len(compressed)] = compressed
            if len(compressed) < block.compressed_len:
                pad_start = block.offset + len(compressed)
                pad_len = block.compressed_len - len(compressed)
                rom[pad_start:pad_start + pad_len] = b"\x00" * pad_len
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

    patched_tables = patch_width_tables(rom)
    return patched_fonts, patched_tables, relocated_fonts


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch French glyphs (à, é, è, ç) in a GBA ROM font.")
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
        f"and updated {patched_tables} width table(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
