#!/usr/bin/env python3
"""Patch shop menu labels to French.

"Buy" (3 chars, 4 bytes with 0xFF) lives at 0x416738, pointed to by
0x3DF09C.  "Acheter" (7 chars, 8 bytes) cannot fit in-place.  Free
space (0xFF) is available at 0x284EB4 (right after "Utiliser" written
by patch_time_format_fr.py), so we write there and redirect the single
pointer entry from 0x08416738 to 0x08284EB4.

Every patch verifies the bytes it expects (English original) and is
idempotent (already-patched cells are skipped).

Usage:
    python3 scripts/patch_shop_fr.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.text.charmap_data import CHAR_TO_BYTE


def encode(text: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in text)


PATCHES = [
    # "Acheter" written into free space at 0x284EB4
    (0x284EB4, b"\xff" * 8, encode("Acheter") + b"\xff"),
    # Redirect the single pointer entry from "Buy" to "Acheter"
    (0x3DF09C, b"\x38\x67\x41\x08", b"\xb4\x4e\x28\x08"),
]


def apply_patches(data: bytearray, patches=PATCHES) -> int:
    applied = 0
    for offset, old, new in patches:
        if len(old) != len(new):
            raise ValueError(f"0x{offset:X}: length mismatch")
        current = bytes(data[offset : offset + len(old)])
        if current == new:
            continue  # already patched
        if current != old:
            raise ValueError(
                f"0x{offset:X}: unexpected bytes {current.hex(' ')} "
                f"(wanted {old.hex(' ')})"
            )
        data[offset : offset + len(new)] = new
        applied += 1
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch shop menu labels to French.")
    parser.add_argument("--rom", type=Path, required=True, help="Built French ROM to patch")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"Error: ROM not found: {args.rom}")
        return 1

    data = bytearray(args.rom.read_bytes())
    try:
        applied = apply_patches(data)
    except ValueError as exc:
        print(f"Patch error: {exc}")
        return 1

    args.rom.write_bytes(data)
    print(f"Shop patch: {applied} patch(es) applied to {args.rom}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
