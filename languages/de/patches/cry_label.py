#!/usr/bin/env python3
"""Translate and relocate the Pokémon-list "Cry" menu-entry label — DE port.

Context (ticket B-188, split from B-180 / issue #7)
----------------------------------------------------
The FR fix for issue #7 replaced "Cry" with "Cri" in place: both are 3
glyphs, so the translated name fits the source ROM's fixed 6-byte cell
(``<0xF8><0x04>`` control code + 3-glyph name + terminator) without moving
anything. IT ("Grido", 5 glyphs) and DE ("Schrei", 6 glyphs) are both longer
than the 3-byte budget, and the generic build pipeline (``build_language.py``
→ ``19_build_translated_rom_generic.py`` → ``SmartReinserter``) never
propagates ``pointer_offsets`` for IT/DE, so it cannot relocate this cell —
the ROM ships with the untouched English body.

Two pointers reference the body directly (verified by scanning the whole
English ROM for every 4-byte occurrence of ``0x08415FAD``, rather than
trusting the ticket-recorded ``table_offsets`` blindly — see
``unbound-trace-live-pointer-not-original-offset`` / ``…-move-names-real-
table-vs-legacy-offset``):

  0x105FE4, 0x1067B8  -> both hold 0x08415FAD (the "Cry" body)

The ticket also lists ``table_offsets: 0x00105FD8``, 12 bytes before
0x105FE4: that is the *start of the struct row* the pointer lives in
(species cry-menu-entry, stride 12), not itself a pointer to the string —
writing there would corrupt an unrelated field, so this script leaves it
alone.

Because the two pointers are external to the body, we can relocate the
German translation to free space and repoint both — leaving the untouched
English body where it is.

Idempotent: only writes when both pointers still target the old EN offset.

Usage:
    python3 languages/de/patches/cry_label.py --rom output/roms/GenedRom-de.gba
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import CHAR_TO_BYTE

GBA_BASE = 0x08000000
OLD_BODY_OFFSET = 0x415FAD
CRY_PTR_OFFSETS = [0x105FE4, 0x1067B8]
NAME = "Schrei"

_MIN_FREE_RUN = 256


def _body_bytes(name: str) -> bytes:
    return b"\xf8\x04" + bytes(CHAR_TO_BYTE[c] for c in name) + b"\xff"


def _find_free(rom: bytearray, size: int, start: int = 0x500000) -> int | None:
    """Return offset of first 0xFF run >= size bytes after `start`.

    Skips the CFRU upper-ROM range (0x1000000+, the engine's own dynamic
    data) and the battle-animation range (0x230000-0x500000) whose 0xFF
    padding blocks are graphic data, not free space.
    """
    exclude = [(0x230000, 0x500000), (0x1000000, len(rom))]
    needed = size + 8  # leave 8-byte margin on each edge
    i = max(start, 0x500000)
    run_start: int | None = None
    while i < len(rom):
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
                    return run_start + 8
            else:
                run_start = None
            i += 1
    return None


def apply_to_rom(rom: bytearray, dry_run: bool = False) -> int:
    """Write the DE "Schrei" body and repoint both cells. Returns patch count."""
    body = _body_bytes(NAME)
    expected_ptr = GBA_BASE + OLD_BODY_OFFSET
    current = [struct.unpack_from("<I", rom, off)[0] for off in CRY_PTR_OFFSETS]

    if all(ptr == expected_ptr for ptr in current):
        pass  # still pointing at the untouched EN body: proceed to relocate
    elif all(
        0 < ptr - GBA_BASE < len(rom) - len(body)
        and rom[ptr - GBA_BASE : ptr - GBA_BASE + len(body)] == body
        for ptr in current
    ):
        return 0  # already relocated and repointed
    else:
        print(
            f"  SKIP: pointers are inconsistent with the expected EN offset "
            f"(found {[hex(p) for p in current]})",
            file=sys.stderr,
        )
        return 0

    new_off = _find_free(rom, len(body))
    if new_off is None:
        print(f"  FAIL: no free space for {len(body)} bytes", file=sys.stderr)
        return 0

    if not dry_run:
        rom[new_off : new_off + len(body)] = body
        new_ptr = struct.pack("<I", GBA_BASE + new_off)
        for off in CRY_PTR_OFFSETS:
            rom[off : off + 4] = new_ptr

    print(
        f"  Cry label relocated to 0x{new_off:06X} ({len(body)} bytes); "
        f"{len(CRY_PTR_OFFSETS)} pointer(s) repointed to {NAME!r}"
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path, help="Built DE ROM (modified in place)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rom = bytearray(args.rom.read_bytes())
    n = apply_to_rom(rom, dry_run=args.dry_run)
    if not args.dry_run and n:
        args.rom.write_bytes(rom)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_cry_label_de: {n} patch(es) applied{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
