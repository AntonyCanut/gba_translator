#!/usr/bin/env python3
"""Patch the GBA ROM header version byte with the CI build number.

The GBA ROM header contains a one-byte software version field at offset 0xBC
(value 0x00 in the stock FireRed ROM).  This script replaces that byte with
``build_number & 0xFF`` and recomputes the header complement checksum at 0xBD
so that emulators and flash-cart loaders still validate the ROM.

The checksum covers header bytes 0xA0–0xBC (inclusive) and is defined as:
    complement = -(sum(header[0xA0:0xBD]) + 0x19) & 0xFF

The patch is idempotent: if 0xBC already holds the target value the script
exits without touching the file.

Usage:
    python3 scripts/patch_version_fr.py --rom output/roms/GenedRom-fr.gba \\
        --build-number 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _compute_checksum(data: bytes | bytearray) -> int:
    return (-(sum(data[0xA0:0xBD]) + 0x19)) & 0xFF


def patch_version(data: bytearray, build_number: int) -> bool:
    version_byte = build_number & 0xFF
    if data[0xBC] == version_byte:
        return False  # already set
    data[0xBC] = version_byte
    data[0xBD] = _compute_checksum(data)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    parser.add_argument("--build-number", type=int, required=True,
                        help="CI build counter (e.g. GITHUB_RUN_NUMBER)")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"ROM not found: {args.rom}", file=sys.stderr)
        return 1

    data = bytearray(args.rom.read_bytes())

    # Basic GBA magic check
    if data[0xB2] != 0x96:
        print(f"Not a valid GBA ROM: {args.rom}", file=sys.stderr)
        return 1

    old_version = data[0xBC]
    changed = patch_version(data, args.build_number)

    if changed:
        args.rom.write_bytes(data)
        new_version = args.build_number & 0xFF
        new_checksum = _compute_checksum(data)
        print(
            f"Version patched: 0x{old_version:02X} → 0x{new_version:02X} "
            f"(build #{args.build_number}), checksum 0xBD = 0x{new_checksum:02X}"
        )
    else:
        print(f"Version already 0x{old_version:02X} — no change.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
