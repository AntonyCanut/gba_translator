#!/usr/bin/env python3
"""Patch the FR ROM with the CI build number.

Two patches are applied:

1. The GBA header byte 0xBC (software-version field) is set to
   ``build_number & 0xFF`` and the header complement checksum at 0xBD is
   recomputed.

2. The in-game version display on the **NOT FOR SALE** intro screen is changed
   from the pre-rendered ``v2.1.1.1`` to ``FR.2.1.<build_number>``.

   The intro screen is a single BG0 layer (mode 0, charblock 0, screenblock 7).
   Its ``v2.1.1.1`` string is pre-rendered as twelve 8x8 tiles (indices
   0xE1-0xEC, a 6x2 grid) inside an LZ77-compressed tileset.  The tilemap that
   places those tiles never changes, so we only have to redraw the twelve glyph
   tiles in the tileset: we decompress it, paint ``FR.2.1.<build_number>`` over
   the version band, recompress it into free space and update the single ROM
   pointer that references it (at 0xEC610).

History note — earlier revisions of this script targeted the wrong graphics:
the old "title screen" pointers (0x1413AC / 0x1413B8) actually point at the
Game Corner *slot machine* (CREDIT / PAYOUT), so the previous code corrupted
that screen while leaving the real version display untouched.  The real Pokémon
Unbound title screen (PRESS START) shows **no** version number at all; the only
in-game version string is the one on the NOT FOR SALE screen handled here.

Usage::

    python3 scripts/patch_version_fr.py --rom output/roms/GenedRom-fr.gba \\
        --build-number 42
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# LZ77 (GBA BIOS format) — identical to the copies in patch_font_fr.py
# ---------------------------------------------------------------------------

_LZ77_MAGIC = 0x10


def _lz77_decompress(data: bytes | bytearray, offset: int) -> tuple[bytes, int] | None:
    if offset + 4 > len(data) or data[offset] != _LZ77_MAGIC:
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


def _lz77_compress(data: bytes) -> bytes:
    size = len(data)
    out = bytearray()
    out.append(_LZ77_MAGIC)
    out.extend((size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF))
    pos = 0
    while pos < size:
        flags_pos = len(out)
        out.append(0)
        flags = 0
        for i in range(8):
            if pos >= size:
                break
            max_len = min(18, size - pos)
            window_start = max(0, pos - 0x1000)
            window = data[window_start:pos]
            best_len = 0
            best_disp = 0
            if window:
                for length in range(max_len, 2, -1):
                    idx = window.rfind(data[pos:pos + length])
                    if idx != -1:
                        best_len = length
                        best_disp = pos - (window_start + idx)
                        break
            if best_len >= 3:
                flags |= 1 << (7 - i)
                disp = best_disp - 1
                out.append(((best_len - 3) << 4) | ((disp >> 8) & 0x0F))
                out.append(disp & 0xFF)
                pos += best_len
            else:
                out.append(data[pos])
                pos += 1
        out[flags_pos] = flags
    return bytes(out)


# ---------------------------------------------------------------------------
# GBA ROM header patch
# ---------------------------------------------------------------------------

def _compute_checksum(data: bytes | bytearray) -> int:
    return (-(sum(data[0xA0:0xBD]) + 0x19)) & 0xFF


def patch_version(data: bytearray, build_number: int) -> bool:
    version_byte = build_number & 0xFF
    if data[0xBC] == version_byte:
        return False
    data[0xBC] = version_byte
    data[0xBD] = _compute_checksum(data)
    return True


# ---------------------------------------------------------------------------
# Shared ROM helpers
# ---------------------------------------------------------------------------

_GBA_BASE = 0x08000000


def _find_free_block(data: bytearray, size: int, min_offset: int = 0x100) -> int:
    """Find the first 4-byte-aligned run of 0xFF bytes of at least ``size`` bytes.

    Scans the whole ROM (after ``min_offset``) rather than only the trailing
    region, so it works even after other patches have consumed the tail.
    """
    i = min_offset
    rom_size = len(data)
    while i < rom_size:
        if data[i] != 0xFF:
            i += 1
            continue
        start = i
        while i < rom_size and data[i] == 0xFF:
            i += 1
        aligned = (start + 3) & ~3
        if i - aligned >= size:
            return aligned
    raise RuntimeError("Insufficient free space for intro version patch")


def _read_gba_ptr(data: bytearray, off: int) -> int:
    val = struct.unpack_from("<I", data, off)[0]
    if val < _GBA_BASE:
        raise ValueError(f"Not a valid GBA pointer at 0x{off:07X}: 0x{val:08X}")
    return val - _GBA_BASE


def _write_gba_ptr(data: bytearray, off: int, rom_addr: int) -> None:
    struct.pack_into("<I", data, off, rom_addr + _GBA_BASE)


# ---------------------------------------------------------------------------
# NOT FOR SALE intro-screen version display
# ---------------------------------------------------------------------------

# The single ROM pointer that references the intro BG0 tileset (charblock 0).
_NFS_TILESET_PTR_OFF = 0xEC610

# Within the decompressed tileset the version glyphs occupy a 6-tile-wide,
# 2-tile-tall band starting at tile index 0xE1 (tiles 0xE1-0xEC).
_VER_TILE_START = 0xE1
_VER_GRID_COLS = 6
_VER_GRID_ROWS = 2

# 4bpp palette indices used by the intro tiles: the glyph strokes are drawn in
# index 4 (white) over an index-9 (black) tile background — matching exactly how
# the original "v2.1.1.1" was encoded.
_VER_FG = 4
_VER_BG = 9

# Character bitmaps: 4 px wide x 5 px tall, 1 = stroke pixel.  Narrow enough to
# fit ``FR.2.1.<build_number>`` (up to 12 characters) across the 48 px band.
_CHAR_PIXELS: dict[str, list[list[int]]] = {
    '0': [[0, 1, 1, 0], [1, 0, 0, 1], [1, 0, 0, 1], [1, 0, 0, 1], [0, 1, 1, 0]],
    '1': [[0, 0, 1, 0], [0, 1, 1, 0], [0, 0, 1, 0], [0, 0, 1, 0], [0, 1, 1, 1]],
    '2': [[0, 1, 1, 0], [1, 0, 0, 1], [0, 0, 1, 0], [0, 1, 0, 0], [1, 1, 1, 1]],
    '3': [[1, 1, 1, 0], [0, 0, 0, 1], [0, 1, 1, 0], [0, 0, 0, 1], [1, 1, 1, 0]],
    '4': [[0, 0, 1, 1], [0, 1, 0, 1], [1, 1, 1, 1], [0, 0, 0, 1], [0, 0, 0, 1]],
    '5': [[1, 1, 1, 1], [1, 0, 0, 0], [1, 1, 1, 0], [0, 0, 0, 1], [1, 1, 1, 0]],
    '6': [[0, 1, 1, 0], [1, 0, 0, 0], [1, 1, 1, 0], [1, 0, 0, 1], [0, 1, 1, 0]],
    '7': [[1, 1, 1, 1], [0, 0, 0, 1], [0, 0, 1, 0], [0, 1, 0, 0], [0, 1, 0, 0]],
    '8': [[0, 1, 1, 0], [1, 0, 0, 1], [0, 1, 1, 0], [1, 0, 0, 1], [0, 1, 1, 0]],
    '9': [[0, 1, 1, 0], [1, 0, 0, 1], [0, 1, 1, 1], [0, 0, 0, 1], [0, 1, 1, 0]],
    'F': [[1, 1, 1, 1], [1, 0, 0, 0], [1, 1, 1, 0], [1, 0, 0, 0], [1, 0, 0, 0]],
    'R': [[1, 1, 1, 0], [1, 0, 0, 1], [1, 1, 1, 0], [1, 0, 1, 0], [1, 0, 0, 1]],
    # Glyphs for the other language prefixes: IT (Italian), DE (German).
    'I': [[1, 1, 1, 1], [0, 1, 1, 0], [0, 1, 1, 0], [0, 1, 1, 0], [1, 1, 1, 1]],
    'T': [[1, 1, 1, 1], [0, 1, 1, 0], [0, 1, 1, 0], [0, 1, 1, 0], [0, 1, 1, 0]],
    'D': [[1, 1, 1, 0], [1, 0, 0, 1], [1, 0, 0, 1], [1, 0, 0, 1], [1, 1, 1, 0]],
    'E': [[1, 1, 1, 1], [1, 0, 0, 0], [1, 1, 1, 0], [1, 0, 0, 0], [1, 1, 1, 1]],
    '.': [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 1, 1, 0]],
    ' ': [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
}

_GLYPH_W = 4   # advance per character (glyphs are 4 px wide, no extra gap)
_GLYPH_H = 5


def version_string(build_number: int, lang_code: str = "fr") -> str:
    """Return the version label rendered on the intro screen.

    The label is ``<PREFIX>.2.1.<build_number>`` where ``PREFIX`` is the
    upper-cased language code (``FR`` for French, ``IT`` for Italian, ``DE``
    for German…).  This is what makes the NOT FOR SALE screen advertise which
    language build is running.
    """
    return f"{lang_code.upper()}.2.1.{build_number}"


def _render_version_band(text: str) -> list[list[int]]:
    """Paint ``text`` into the version band as a grid of 4bpp palette indices.

    The band is ``_VER_GRID_COLS`` x ``_VER_GRID_ROWS`` tiles (48 x 16 px).  The
    background is filled with ``_VER_BG`` and the glyph strokes with ``_VER_FG``,
    horizontally and vertically centred.
    """
    pw = _VER_GRID_COLS * 8
    ph = _VER_GRID_ROWS * 8
    band = [[_VER_BG] * pw for _ in range(ph)]
    x0 = max(0, (pw - len(text) * _GLYPH_W) // 2)
    y0 = (ph - _GLYPH_H) // 2
    for i, ch in enumerate(text):
        glyph = _CHAR_PIXELS.get(ch, _CHAR_PIXELS[' '])
        for ry, row in enumerate(glyph):
            for cx, on in enumerate(row):
                if not on:
                    continue
                px = x0 + i * _GLYPH_W + cx
                py = y0 + ry
                if 0 <= px < pw and 0 <= py < ph:
                    band[py][px] = _VER_FG
    return band


def _blit_band_to_tiles(tileset: bytearray, band: list[list[int]]) -> None:
    """Write the rendered band over the version tiles (in place)."""
    for ty in range(_VER_GRID_ROWS):
        for tx in range(_VER_GRID_COLS):
            tile = _VER_TILE_START + ty * _VER_GRID_COLS + tx
            base = tile * 32
            for py in range(8):
                for px in range(0, 8, 2):
                    lo = band[ty * 8 + py][tx * 8 + px] & 0xF
                    hi = band[ty * 8 + py][tx * 8 + px + 1] & 0xF
                    tileset[base + py * 4 + (px >> 1)] = lo | (hi << 4)


def patch_intro_version(data: bytearray, build_number: int, lang_code: str = "fr") -> bool:
    """Replace 'v2.1.1.1' on the NOT FOR SALE screen with '<PREFIX>.2.1.<build>'.

    ``lang_code`` selects the prefix glyphs (``fr`` → ``FR``, ``it`` → ``IT``…),
    so each language build advertises itself on the intro screen.

    Returns True if the ROM was modified.
    """
    ts_off = _read_gba_ptr(data, _NFS_TILESET_PTR_OFF)
    result = _lz77_decompress(data, ts_off)
    if result is None:
        raise RuntimeError(f"Failed to decompress intro tileset at 0x{ts_off:07X}")
    tileset, _ = result
    tileset = bytearray(tileset)

    needed = (_VER_TILE_START + _VER_GRID_COLS * _VER_GRID_ROWS) * 32
    if len(tileset) < needed:
        raise RuntimeError(
            f"Intro tileset too small ({len(tileset)} bytes) for version band"
        )

    band = _render_version_band(version_string(build_number, lang_code))
    _blit_band_to_tiles(tileset, band)

    compressed = _lz77_compress(bytes(tileset))
    padded = compressed + b"\xFF" * ((-len(compressed)) & 3)
    cursor = _find_free_block(data, len(padded))
    data[cursor:cursor + len(padded)] = padded
    _write_gba_ptr(data, _NFS_TILESET_PTR_OFF, cursor)
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    parser.add_argument("--build-number", type=int, required=True,
                        help="CI build counter (e.g. GITHUB_RUN_NUMBER)")
    parser.add_argument("--lang-code", default="fr",
                        help="Language code shown as the version prefix "
                             "(fr→FR, it→IT, de→DE). Default: fr")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"ROM not found: {args.rom}", file=sys.stderr)
        return 1

    data = bytearray(args.rom.read_bytes())

    if data[0xB2] != 0x96:
        print(f"Not a valid GBA ROM: {args.rom}", file=sys.stderr)
        return 1

    old_version = data[0xBC]
    header_changed = patch_version(data, args.build_number)

    try:
        screen_changed = patch_intro_version(data, args.build_number, args.lang_code)
    except Exception as exc:  # noqa: BLE001 — surface a clear CI failure
        print(f"Intro version patch failed: {exc}", file=sys.stderr)
        return 1

    args.rom.write_bytes(data)

    if header_changed:
        print(
            f"Header patched: version 0x{old_version:02X} → 0x{args.build_number & 0xFF:02X} "
            f"(build #{args.build_number}), checksum 0xBD = 0x{_compute_checksum(data):02X}"
        )
    else:
        print(f"Header version already 0x{old_version:02X} — no change.")

    if screen_changed:
        print(
            "NOT FOR SALE screen: version display updated to "
            f"'{version_string(args.build_number, args.lang_code)}'"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
