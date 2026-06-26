#!/usr/bin/env python3
"""Translate and relocate the trainer Pokémon recall strings (come-back messages).

Context (tickets B-78 / B-81)
------------------------------
``patch_battle_string_templates_fr.py`` restores the whole cluster
``0x3FB219..0x3FB264`` from the English ROM to keep STRINGID 0 (the defeat-speech
template ``{FD24}``) correct.  Side-effect: the three trainer "come back!" switch-out
lines in that cluster also revert to English.

Those three bodies sit at fixed offsets INSIDE the cluster, but each is also
pointed to by an entry in a SEPARATE pointer table (``0x3FE504 / 0x3FE50C /
0x3FE510``).  Because the pointers are external, we can relocate the French
translations to free space and repoint the table — leaving the EN cluster intact
(STRINGID 0 continues to work) while the recalled-Pokémon messages display in
French.

English originals decoded
-------------------------
  0x3FB21F  {FD1D}: {FD06}, come back!       (trainer name: mon1, come back!)
  0x3FB235  {FD1D}: {FD08}, come back!       (trainer name: mon2, come back!)
  0x3FB248  {FD1D}: {FD06} and\\n{FD08}, come back!  (two Pokémon)

French translations
-------------------
  {FD1D}: {FD06}, reviens !
  {FD1D}: {FD08}, reviens !
  {FD1D}: {FD06} et\\n{FD08}, revenez !

Idempotent: only writes when the pointer still targets the old EN offset.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

GBA_BASE = 0x08000000

# Pointer table entries that reference the three come-back strings.
RECALL_PTRS = [
    (0x3FE504, 0x3FB21F),   # single-mon recall 1  ({FD06})
    (0x3FE50C, 0x3FB235),   # single-mon recall 2  ({FD08})
    (0x3FE510, 0x3FB248),   # double-mon recall     ({FD06} and {FD08})
]

# French encodings (raw bytes, verified against CFRU charmap):
#   {FD1D}= FD1D  ':'=F0  ' '=00  {FD06/08}= FD06/FD08
#   ','=B8  'r'=E6  'e'=D9  'v'=EA  'i'=DD  'e'=D9  'n'=E2  's'=E7  '!'=AB
#   'e'=D9  't'=E8  '\n'=FE  'z'=EE  terminator=FF
FR_STRINGS: list[bytes] = [
    bytes.fromhex("fd1d f0 00 fd06 b8 00 e6d9eadd d9e2e7 00 ab ff".replace(" ", "")),
    bytes.fromhex("fd1d f0 00 fd08 b8 00 e6d9eadd d9e2e7 00 ab ff".replace(" ", "")),
    bytes.fromhex("fd1d f0 00 fd06 00 d9e8 fe fd08 b8 00 e6d9ead9e2d9ee 00 ab ff".replace(" ", "")),
]

# Minimum run of 0xFF bytes to be considered genuine free space.
_MIN_FREE_RUN = 256


def _find_free(rom: bytearray, size: int, start: int = 0x500000) -> int | None:
    """Return offset of first 0xFF run ≥ size bytes after `start`.

    Skips the CFRU upper-ROM range (0x1000000+) which the engine uses for its own
    dynamic data, and the battle-animation range (0x230000–0x500000) whose 0xFF
    padding blocks are graphic data, not free space.
    """
    exclude = [(0x230000, 0x500000), (0x1000000, len(rom))]
    needed = size + 8  # leave 8-byte margin on each edge
    i = max(start, 0x500000)
    run_start: int | None = None
    while i < len(rom):
        # Skip excluded ranges
        for lo, hi in exclude:
            if lo <= i < hi:
                i = hi
                run_start = None
                break
        else:
            if rom[i] == 0xFF:
                if run_start is None:
                    run_start = i
                if i - run_start + 1 >= needed:
                    return run_start + 8  # leave leading margin
            else:
                run_start = None
            i += 1
    return None


def apply_to_rom(rom: bytearray, dry_run: bool = False) -> int:
    """Write the FR recall strings and repoint the table. Returns patch count."""
    changes = 0
    for (ptr_off, old_body_off), fr_bytes in zip(RECALL_PTRS, FR_STRINGS):
        ptr = struct.unpack_from("<I", rom, ptr_off)[0]
        expected_ptr = GBA_BASE + old_body_off

        if ptr != expected_ptr:
            # Already repointed (idempotent) or unexpectedly different.
            # Check if the current target starts with the French string.
            cur_off = ptr - GBA_BASE
            if 0 < cur_off < len(rom) - len(fr_bytes):
                if rom[cur_off: cur_off + len(fr_bytes)] == fr_bytes:
                    continue  # already done
            print(
                f"  SKIP @0x{ptr_off:06X}: pointer is 0x{ptr:08X}, "
                f"expected 0x{expected_ptr:08X}",
                file=sys.stderr,
            )
            continue

        new_off = _find_free(rom, len(fr_bytes))
        if new_off is None:
            print(f"  FAIL @0x{ptr_off:06X}: no free space for {len(fr_bytes)} bytes", file=sys.stderr)
            continue

        if not dry_run:
            rom[new_off: new_off + len(fr_bytes)] = fr_bytes
            new_ptr = struct.pack("<I", GBA_BASE + new_off)
            rom[ptr_off: ptr_off + 4] = new_ptr

        changes += 1
        print(
            f"  0x{ptr_off:06X} → 0x{GBA_BASE + new_off:08X}  "
            f"recall string #{changes} relocated to 0x{new_off:06X} ({len(fr_bytes)} bytes)"
        )

    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path, help="Built FR ROM (modified in place)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rom = bytearray(args.rom.read_bytes())
    n = apply_to_rom(rom, dry_run=args.dry_run)
    if not args.dry_run and n:
        args.rom.write_bytes(rom)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_battle_recall_strings_fr: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
