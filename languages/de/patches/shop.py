#!/usr/bin/env python3
"""Translate remaining shop-menu strings that the text pipeline misses (German).

Port of ``patch_shop_fr.py``. The shop-menu strings "Buy" and "In Cube:" are
not covered by the pointer pipeline: "Buy" has no Spanish equivalent (ES kept
it in English), so the pipeline has nothing to copy; "In Cube:" lives in the
CFRU free-space region at 0x1F11DD6 and is not reachable by the inline-
overrides script.

Patches applied:
  1. "In Cube:" -> "Bestand:" in place at 0x1F11DD6 (same 8-byte length, no
     repointing needed).
  2. "Buy" -> "Kaufen" via freshly-allocated free space, with the single
     "Buy" pointer at 0x3DF09C repointed at it. Unlike the French dedicated
     build (byte-perfect, so a fixed free-space address can be hardcoded),
     the German ROM is produced by the generic per-language builder, whose
     free-space layout is NOT guaranteed to match FR's — so this uses
     ``FreeSpaceAllocator`` to find free space dynamically instead of
     reusing FR's hardcoded 0x284EB4 slot.

Both patches are idempotent (already-patched bytes are silently skipped).

Usage:
    python3 languages/de/patches/shop.py --rom output/roms/GenedRom-de.gba
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import CHAR_TO_BYTE
from src.core.text_reinserter import FreeSpaceAllocator

ROM_POINTER_BASE = 0x08000000

# "In Cube:" -> "Bestand:" in place (8 chars, same byte count).
# Full slot at 0x1F11DD6 is: "In Cube:[FC06]  [FD02][FF]" (15 bytes); only the
# text portion (bytes 0-7) is changed, control codes stay untouched.
_IN_CUBE_OFFSET = 0x1F11DD6
_IN_CUBE_EN = bytes(CHAR_TO_BYTE[c] for c in "In Cube:")
_IN_CUBE_DE = bytes(CHAR_TO_BYTE[c] for c in "Bestand:")
assert len(_IN_CUBE_EN) == len(_IN_CUBE_DE)

# "Buy" pointer cell + its original EN target (untouched by either the FR or
# generic pipeline, since ES kept "Buy" in English too).
_BUY_PTR_OFFSET = 0x3DF09C
_BUY_EN_POINTER = struct.pack("<I", 0x08416738)
_BUY_DE_TEXT = "Kaufen"


def _encode(text: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in text) + b"\xff"


def apply_patches(data: bytearray, reserved_rom: bytes | None = None) -> int:
    applied = 0

    current = bytes(data[_IN_CUBE_OFFSET:_IN_CUBE_OFFSET + len(_IN_CUBE_EN)])
    if current == _IN_CUBE_DE:
        pass  # already patched — idempotent
    elif current != _IN_CUBE_EN:
        raise ValueError(
            f"0x{_IN_CUBE_OFFSET:X}: unexpected bytes {current.hex(' ')} "
            f"(expected {_IN_CUBE_EN.hex(' ')})"
        )
    else:
        data[_IN_CUBE_OFFSET:_IN_CUBE_OFFSET + len(_IN_CUBE_DE)] = _IN_CUBE_DE
        applied += 1

    current_ptr = bytes(data[_BUY_PTR_OFFSET:_BUY_PTR_OFFSET + 4])
    if current_ptr == _BUY_EN_POINTER:
        allocator = FreeSpaceAllocator(data, reserved_rom=reserved_rom)
        encoded = _encode(_BUY_DE_TEXT)
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            raise ValueError("insufficient free space for DE 'Buy' -> 'Kaufen' relocation")
        data[new_offset:new_offset + len(encoded)] = encoded
        data[_BUY_PTR_OFFSET:_BUY_PTR_OFFSET + 4] = struct.pack(
            "<I", new_offset + ROM_POINTER_BASE
        )
        applied += 1
    elif current_ptr != _BUY_EN_POINTER:
        # Already repointed by a previous run — verify it resolves to "Kaufen".
        target = struct.unpack("<I", current_ptr)[0] - ROM_POINTER_BASE
        expected = _encode(_BUY_DE_TEXT)
        if 0 <= target < len(data) and bytes(data[target:target + len(expected)]) == expected:
            pass  # already patched — idempotent
        else:
            raise ValueError(
                f"0x{_BUY_PTR_OFFSET:X}: unexpected pointer {current_ptr.hex(' ')} "
                f"(expected EN original {_BUY_EN_POINTER.hex(' ')})"
            )

    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-de.gba"))
    parser.add_argument("--reference-rom", default=None, type=Path,
                        help="Same-base ROM whose populated bytes must not be reused as free space")
    args = parser.parse_args()

    # Under build_language.py's generic `patch_<step>_<code>.py --rom` dispatch no
    # --reference-rom is passed; fall back to the Spanish ROM when present so the
    # free-space guard still holds (matches the dedicated elif branch, which only
    # adds --reference-rom when the Spanish ROM exists).
    if args.reference_rom is None:
        _default_ref = Path("input/roms/spanishrom.gba")
        if _default_ref.exists():
            args.reference_rom = _default_ref

    data = bytearray(args.rom.read_bytes())
    reserved = args.reference_rom.read_bytes() if args.reference_rom else None
    applied = apply_patches(data, reserved_rom=reserved)
    if applied:
        args.rom.write_bytes(data)
    print(f"Shop patches applied (DE): {applied} (of 2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
