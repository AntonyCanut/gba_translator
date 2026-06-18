#!/usr/bin/env python3
"""Translate remaining shop-menu strings that the text pipeline misses.

The shop-menu strings "Buy" and "In Cube:" are not covered by the pointer
pipeline: "Buy" (4 bytes) has no Spanish equivalent (ES kept it in English),
so the pipeline has nothing to copy.  "In Cube:" lives in the CFRU free-space
region at 0x1F11DD6 and is not reachable by the inline-overrides script.

Patches applied:
  1. "In Cube:" → "Possédé:" at 0x1F11DD6 (same 8 bytes, no repointing).
  2. "Buy" → "Acheter" via free space at 0x284EB4, pointer at 0x3DF09C
     updated from 0x08416738 → 0x08284EB4.

Both patches are idempotent (already-patched bytes are silently skipped).

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
    return bytes(CHAR_TO_BYTE[c] for c in text) + b"\xff"


# ── patches ──────────────────────────────────────────────────────────────────
# Each entry: (rom_offset, expected_old_bytes, new_bytes)
# old and new MUST have the same length.

PATCHES = [
    # 1. "In Cube:" → "Possédé:" in place (8 chars, same byte count)
    #    Full slot at 0x1F11DD6 is: "In Cube:[FC06]  [FD02][FF]" (15 bytes).
    #    Only the text portion (bytes 0-7) is changed; control codes stay.
    (
        0x1F11DD6,
        bytes(CHAR_TO_BYTE[c] for c in "In Cube:"),   # c3 e2 00 bd e9 d6 d9 f0
        bytes(CHAR_TO_BYTE[c] for c in "Possédé:"),   # ca e3 e7 e7 1b d8 1b f0
    ),
    # 2a. Write "Acheter" into free space immediately after "Utiliser"
    #     (which patch_time_format_fr.py placed at 0x284EAB; its 9 bytes end
    #     at 0x284EB4, which is confirmed 0xFF in the built FR ROM).
    (
        0x284EB4,
        b"\xff" * 8,
        encode("Acheter"),                             # bb d7 dc d9 e8 d9 e6 ff
    ),
    # 2b. Repoint the single "Buy" pointer from 0x08416738 → 0x08284EB4.
    (
        0x3DF09C,
        b"\x38\x67\x41\x08",                          # → 0x08416738 (original "Buy")
        b"\xb4\x4e\x28\x08",                          # → 0x08284EB4 (new "Acheter")
    ),
]


def apply_patches(data: bytearray) -> int:
    applied = 0
    for offset, old, new in PATCHES:
        if len(old) != len(new):
            raise ValueError(f"0x{offset:X}: length mismatch ({len(old)} vs {len(new)})")
        current = bytes(data[offset: offset + len(old)])
        if current == new:
            continue  # already patched — idempotent
        if current != old:
            raise ValueError(
                f"0x{offset:X}: unexpected bytes {current.hex(' ')} "
                f"(expected {old.hex(' ')})"
            )
        data[offset: offset + len(new)] = new
        applied += 1
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    if applied:
        args.rom.write_bytes(data)
    print(f"Shop patches applied: {applied} (of {len(PATCHES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
