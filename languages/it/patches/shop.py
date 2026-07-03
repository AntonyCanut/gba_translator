#!/usr/bin/env python3
"""Translate remaining shop-menu strings that the text pipeline misses (Italian).

Port of ``patch_shop_fr.py``. The shop-menu strings "Buy" and "In Cube:" are
not covered by the pointer pipeline: "Buy" has no Spanish equivalent (ES kept
it in English), so the pipeline has nothing to copy; "In Cube:" lives in the
CFRU free-space region at 0x1F11DD6 and is not reachable by the inline-
overrides script.

Patches applied:
  1. "In Cube:" -> "In Cubo:" in place at 0x1F11DD6 (same 8-byte length, no
     repointing needed).
  2. "Buy" -> "Compra" via freshly-allocated free space, with the single
     "Buy" pointer at 0x3DF09C repointed at it. Unlike the French dedicated
     build (byte-perfect, so a fixed free-space address can be hardcoded),
     the Italian ROM is produced by the generic per-language builder, whose
     free-space layout is NOT guaranteed to match FR's — so this uses
     ``FreeSpaceAllocator`` to find free space dynamically instead of
     reusing FR's hardcoded 0x284EB4 slot (see patch_shop_de.py, the same
     fix already applied for German). The IT combined_it.txt payload is much
     larger than DE's, and this step runs near the end of
     languages/it/lang.yaml's patches list, so free space can already be
     exhausted by the time it runs — if so, "Buy" is left in English with a
     warning rather than aborting the whole build (see apply_patches).

Both patches are idempotent (already-patched bytes are silently skipped).

Usage:
    python3 languages/it/patches/shop.py --rom output/roms/GenedRom-it.gba
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

# "In Cube:" -> "In Cubo:" in place (8 chars, same byte count).
# Full slot at 0x1F11DD6 is: "In Cube:[FC06]  [FD02][FF]" (15 bytes); only the
# text portion (bytes 0-7) is changed, control codes stay untouched.
_IN_CUBE_OFFSET = 0x1F11DD6
_IN_CUBE_EN = bytes(CHAR_TO_BYTE[c] for c in "In Cube:")
_IN_CUBE_IT = bytes(CHAR_TO_BYTE[c] for c in "In Cubo:")
assert len(_IN_CUBE_EN) == len(_IN_CUBE_IT)

# "Buy" pointer cell + its original EN target (untouched by either the FR or
# generic pipeline, since ES kept "Buy" in English too).
_BUY_PTR_OFFSET = 0x3DF09C
_BUY_EN_POINTER = struct.pack("<I", 0x08416738)
_BUY_IT_TEXT = "Compra"


def _encode(text: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in text) + b"\xff"


def apply_patches(data: bytearray, reserved_rom: bytes | None = None) -> int:
    applied = 0

    current = bytes(data[_IN_CUBE_OFFSET:_IN_CUBE_OFFSET + len(_IN_CUBE_EN)])
    if current == _IN_CUBE_IT:
        pass  # already patched — idempotent
    elif current != _IN_CUBE_EN:
        raise ValueError(
            f"0x{_IN_CUBE_OFFSET:X}: unexpected bytes {current.hex(' ')} "
            f"(expected {_IN_CUBE_EN.hex(' ')})"
        )
    else:
        data[_IN_CUBE_OFFSET:_IN_CUBE_OFFSET + len(_IN_CUBE_IT)] = _IN_CUBE_IT
        applied += 1

    current_ptr = bytes(data[_BUY_PTR_OFFSET:_BUY_PTR_OFFSET + 4])
    if current_ptr == _BUY_EN_POINTER:
        allocator = FreeSpaceAllocator(data, reserved_rom=reserved_rom)
        encoded = _encode(_BUY_IT_TEXT)
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            # The generic IT builder's own translated-content packing can
            # exhaust free space well before this patch runs (it applies
            # near the end of languages/it/lang.yaml's patches list) — see
            # the module docstring. "Buy" staying English is a soft
            # degradation, not a broken build: never abort the whole build
            # over this single 7-byte allocation.
            print("  WARN: insufficient free space for IT 'Buy' -> 'Compra' — left as 'Buy'")
        else:
            data[new_offset:new_offset + len(encoded)] = encoded
            data[_BUY_PTR_OFFSET:_BUY_PTR_OFFSET + 4] = struct.pack(
                "<I", new_offset + ROM_POINTER_BASE
            )
            applied += 1
    elif current_ptr != _BUY_EN_POINTER:
        # Already repointed by a previous run — verify it resolves to "Compra".
        target = struct.unpack("<I", current_ptr)[0] - ROM_POINTER_BASE
        expected = _encode(_BUY_IT_TEXT)
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
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-it.gba"))
    parser.add_argument("--reference-rom", default=None, type=Path,
                        help="Same-base ROM whose populated bytes must not be reused as free space")
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    reserved = args.reference_rom.read_bytes() if args.reference_rom else None
    applied = apply_patches(data, reserved_rom=reserved)
    if applied:
        args.rom.write_bytes(data)
    print(f"Shop patches applied (IT): {applied} (of 2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
