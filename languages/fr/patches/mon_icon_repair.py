#!/usr/bin/env python3
"""Repair mon-icon graphics corrupted by the FR build (issue #104).

Symptom
-------
When a Pokémon levels up in battle, the CFRU/Unbound *level-up banner* slides in
showing that mon's 32×32 icon. For some species — Rattata being the one players
reported (« le sprite de Rattata est KO ») — that banner icon is visibly corrupted
(scrambled tiles + floating debris), even though the very same icon renders cleanly
in the party list.

Root cause
----------
Mon icons store **two animation frames** back to back. The party list happens to
display frame 0; the level-up banner displays frame 1. The FR *build* rotates a
handful of bytes inside a number of icons' **frame-1** tile data, so the corruption
only ever shows in the banner (frame 1), never in the party list (frame 0).

The rotation is a text pass misfiring on *graphic* data: in the CFRU charmap ``0x00``
decodes to a space and ``0xFF`` is the string terminator. When an icon's frame-1
tiles contain the run ``… FF 00 00 <tiles> …`` a string pass reads it as
« terminator, then a string starting with two spaces », trims the two leading spaces
in place and rotates the following tile bytes left by two — scrambling exactly the
affected tiles (same byte-rotation class as [[unbound-level-marker-memo-space-rotation-fix]]).
The source ROMs (english / spanish / patchedfrench) are all clean; the corruption is
introduced during ``build-fr``.

Fix
---
Icons are never translated, so the correct bytes are exactly the source bytes. This
runs LAST in ``build-fr`` (after every text/graphic pass) and restores the live
mon-icon graphics region from the source ROM — the same "repair after the text passes"
pattern as ``repair_lz77``. Only bytes that differ from source are rewritten, and the
region is bounded to the mon-icon graphics block (``gMonIconTable`` targets), which
holds no relocated strings, so nothing else is touched. Idempotent and self-healing.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

# Live mon-icon graphics block. Bounds derived from gMonIconTable (1294 entries at
# ROM 0x1A217FC): icon graphics span [min target, max target + icon stride 0x420).
# This is the block the party menu AND the level-up banner read icons from.
ICON_REGION_START = 0x189C054
ICON_REGION_END = 0x19DCFF4  # exclusive

# gMonIconTable location, for documentation / verification only.
MON_ICON_TABLE = 0x1A217FC
MON_ICON_TABLE_ENTRIES = 1294
ICON_STRIDE = 0x420


def _icon_region_bounds_from_table(rom: bytes) -> tuple[int, int]:
    """Recompute the icon-graphics bounds from gMonIconTable (defensive check)."""
    targets = []
    for i in range(MON_ICON_TABLE_ENTRIES):
        off = MON_ICON_TABLE + i * 4
        val = struct.unpack_from("<I", rom, off)[0]
        if 0x08000000 <= val < 0x0A000000:
            targets.append(val - 0x08000000)
    if not targets:
        return ICON_REGION_START, ICON_REGION_END
    return min(targets), max(targets) + ICON_STRIDE


def restore_region(rom: bytearray, source: bytes, lo: int, hi: int) -> int:
    """Restore ``rom[lo:hi]`` from ``source`` (icons are never translated). Returns
    the number of corrupted bytes rewritten."""
    restored = 0
    for i in range(lo, hi):
        if rom[i] != source[i]:
            rom[i] = source[i]
            restored += 1
    return restored


def region_bounds(rom: bytes) -> tuple[int, int]:
    """Icon-graphics bounds: table-derived when they cover the known constants,
    otherwise the known constants."""
    lo, hi = _icon_region_bounds_from_table(rom)
    if not (lo <= ICON_REGION_START and hi >= ICON_REGION_END):
        lo, hi = ICON_REGION_START, ICON_REGION_END
    return lo, hi


def apply_patch(rom_path: Path, source_path: Path) -> int:
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")
    source = source_path.read_bytes()
    if source[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA source ROM: {source_path}")

    lo, hi = region_bounds(rom)
    restored = restore_region(rom, source, lo, hi)

    if restored == 0:
        print("  mon-icon graphics: already clean — no change")
        return 0

    rom_path.write_bytes(rom)
    print(f"  mon-icon graphics (0x{lo:07X}-0x{hi:07X}): {restored} corrupted "
          f"byte(s) restored from source")
    return restored


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path,
                        default=Path("output/roms/GenedRom-fr.gba"))
    parser.add_argument("--source", type=Path,
                        default=Path("input/roms/patchedfrenchrom.gba"))
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    if not args.source.exists():
        raise SystemExit(f"Source ROM not found: {args.source}")
    n = apply_patch(args.rom, args.source)
    print(f"patch_mon_icon_repair_fr: {n} byte(s) restored")


if __name__ == "__main__":
    main()
