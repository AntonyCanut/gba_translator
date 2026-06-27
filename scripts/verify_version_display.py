#!/usr/bin/env python3
"""Verify the in-game version display of a built FR ROM.

This is the regression guard for the version-display feature fixed in B-19.
It reads back the **NOT FOR SALE** intro screen of a ROM and proves that the
version band literally spells ``FR.2.0.<build_number>`` — independently of the
code that wrote it (a blind glyph decoder, not a byte comparison against the
renderer).  It also checks the GBA header software-version byte (0xBC).

Why only the NOT FOR SALE screen?  Pokémon Unbound's real title screen
(PRESS START) shows **no** version number at all — the only in-game version
string lives on the NOT FOR SALE screen.  See ``scripts/patch_version_fr.py``
and ticket B-19 for the full diagnostic.  The old "title screen" pointers
(0x1413AC / 0x1413B8) actually address the Game Corner slot machine, so this
verifier also asserts they are *not* touched by the version patch — that
regression (a corrupted slot machine + an untouched version) must never return.

Usage::

    python3 scripts/verify_version_display.py \\
        --rom output/roms/GenedRom-fr.gba --build-number 42

Exit code 0 means the displayed version matches ``FR.2.0.<build_number>``.
A non-zero exit code (with a diagnostic on stderr) means the ROM would *not*
show the expected version — this is what fails the CI release pipeline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.patch_version_fr import (  # noqa: E402
    _CHAR_PIXELS,
    _GLYPH_H,
    _GLYPH_W,
    _NFS_TILESET_PTR_OFF,
    _VER_BG,
    _VER_FG,
    _VER_GRID_COLS,
    _VER_GRID_ROWS,
    _VER_TILE_START,
    _lz77_decompress,
    _read_gba_ptr,
    version_string,
)

# The old, *wrong* "title screen" pointers — they really address the Game
# Corner slot machine (CREDIT / PAYOUT).  The version patch must never write
# through them again.
_SLOT_MACHINE_PTRS = (0x1413AC, 0x1413B8)

# Pre-build a reverse lookup from glyph bitmap to character so the decoder
# never has to know the answer in advance.
_PIXELS_TO_CHAR: dict[tuple, str] = {
    tuple(tuple(row) for row in rows): ch
    for ch, rows in _CHAR_PIXELS.items()
    # ' ' has the same (all-zero) bitmap as a blank cell — exclude it so a
    # blank cell terminates decoding instead of matching a space.
    if ch != " "
}


def _decode_version_band(tileset: bytes) -> list[list[int]]:
    """Rebuild the 48x16 px palette-index grid from the version tiles."""
    pw = _VER_GRID_COLS * 8
    ph = _VER_GRID_ROWS * 8
    band = [[0] * pw for _ in range(ph)]
    for ty in range(_VER_GRID_ROWS):
        for tx in range(_VER_GRID_COLS):
            tile = _VER_TILE_START + ty * _VER_GRID_COLS + tx
            base = tile * 32
            for py in range(8):
                for px in range(8):
                    byte = tileset[base + py * 4 + (px >> 1)]
                    idx = (byte & 0xF) if (px & 1) == 0 else (byte >> 4)
                    band[ty * 8 + py][tx * 8 + px] = idx
    return band


def decode_version_string(rom_data: bytes | bytearray) -> str:
    """Read the NOT FOR SALE version band and return the string it displays.

    This is a blind OCR of the rendered glyphs: each 4 px-wide cell is matched
    against the known character bitmaps.  Returns the decoded string (which may
    contain ``'?'`` for an unrecognised glyph), or ``''`` if no version glyphs
    are present.
    """
    ts_off = _read_gba_ptr(bytearray(rom_data), _NFS_TILESET_PTR_OFF)
    result = _lz77_decompress(bytes(rom_data), ts_off)
    if result is None:
        raise RuntimeError(f"Failed to decompress intro tileset at 0x{ts_off:07X}")
    tileset, _ = result

    band = _decode_version_band(tileset)
    ph = _VER_GRID_ROWS * 8
    pw = _VER_GRID_COLS * 8
    y0 = (ph - _GLYPH_H) // 2

    # The glyph strokes are foreground pixels; find the leftmost one to anchor
    # the (centred) text.  The first character is always 'F', whose left column
    # is solid, so this aligns exactly to the first glyph cell.
    fg_cols = [
        x for x in range(pw)
        if any(band[y0 + ry][x] == _VER_FG for ry in range(_GLYPH_H))
    ]
    if not fg_cols:
        return ""
    x0 = min(fg_cols)

    decoded: list[str] = []
    i = 0
    while x0 + i * _GLYPH_W + _GLYPH_W <= pw:
        cx = x0 + i * _GLYPH_W
        cell = tuple(
            tuple(1 if band[y0 + ry][cx + col] == _VER_FG else 0
                  for col in range(_GLYPH_W))
            for ry in range(_GLYPH_H)
        )
        if all(v == 0 for row in cell for v in row):
            break  # blank cell — past the end of the version string
        decoded.append(_PIXELS_TO_CHAR.get(cell, "?"))
        i += 1
    return "".join(decoded)


def slot_machine_pointers(rom_data: bytes | bytearray) -> tuple[int, ...]:
    """Return the raw 32-bit values at the old (wrong) title-screen pointers."""
    import struct
    return tuple(
        struct.unpack_from("<I", rom_data, off)[0] for off in _SLOT_MACHINE_PTRS
    )


def verify(rom_data: bytes | bytearray, build_number: int,
           lang_code: str = "fr") -> list[str]:
    """Return a list of human-readable problems (empty list == all good)."""
    problems: list[str] = []
    expected = version_string(build_number, lang_code)

    # 1. Header software-version byte.
    header_byte = rom_data[0xBC]
    if header_byte != (build_number & 0xFF):
        problems.append(
            f"header byte 0xBC = 0x{header_byte:02X}, "
            f"expected 0x{build_number & 0xFF:02X} (build #{build_number})"
        )

    # 2. NOT FOR SALE version band.
    try:
        displayed = decode_version_string(rom_data)
    except Exception as exc:  # noqa: BLE001 — surface a clear CI failure
        problems.append(f"could not read NOT FOR SALE version band: {exc}")
        return problems

    if displayed != expected:
        problems.append(
            f"NOT FOR SALE screen shows {displayed!r}, expected {expected!r}"
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path,
                        default=Path("output/roms/GenedRom-fr.gba"))
    parser.add_argument("--build-number", type=int, required=True,
                        help="Expected CI build counter (e.g. GITHUB_RUN_NUMBER)")
    parser.add_argument("--lang-code", default="fr",
                        help="Expected language prefix (fr→FR, it→IT, de→DE). "
                             "Default: fr")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"ROM not found: {args.rom}", file=sys.stderr)
        return 1

    data = args.rom.read_bytes()
    if data[0xB2] != 0x96:
        print(f"Not a valid GBA ROM: {args.rom}", file=sys.stderr)
        return 1

    problems = verify(data, args.build_number, args.lang_code)
    expected = version_string(args.build_number, args.lang_code)
    if problems:
        print(f"✗ Version display verification FAILED for {args.rom}:",
              file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"✓ {args.rom.name}: NOT FOR SALE screen displays '{expected}' "
          f"and header byte 0xBC = 0x{args.build_number & 0xFF:02X}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
