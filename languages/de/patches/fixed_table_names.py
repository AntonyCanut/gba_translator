#!/usr/bin/env python3
"""Fix protected fixed-width name cells of the built German ROM.

These are class-2 fixed-width cells (no pointer): absent from
``translation_ready.json`` and the Spanish extraction, so neither the
reinsertion pass nor the inline-override pass ever reaches them — they ship
in English regardless of target language. Same rationale and mechanism as
``languages/fr/patches/fixed_table_names.py``; the German fixes below are
sourced independently since each cell's byte budget differs from French.

Unlike French, German keeps the "TM" abbreviation (Technische Maschine), so
there is no TM→CT-style rename pass here.

Usage:
    python3 languages/de/patches/fixed_table_names.py --rom output/roms/GenedRom-de.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import CHAR_TO_BYTE

# offset -> (expected current name, corrected name, cell stride)
NAME_FIXES = {
    # Prof.'s parcel item: never reached by the translation pipeline (not in
    # translation_ready.json nor Spanish extraction), stays English. Budget:
    # stride 7 - 1 (terminator) = 6 glyphs.
    0x879DFC: ("Parcel", "Paket", 7),
    # Package item (delivered to rival): same class-2 gap. Budget: stride 8 -
    # 1 = 7 glyphs.
    0x879E80: ("Package", "Sendung", 8),
    # Berry Pouch key item: centered, space-padded name cell absent from both
    # translation_ready.json and the Spanish extraction. Budget: stride 26 -
    # 12 (leading spaces) - 1 (terminator) = 13 glyphs.
    0x3DEED8: (" " * 12 + "Berry Pouch", " " * 12 + "Beerentasche", 26),
    0x87A0B0: (" " * 12 + "Berry Pouch", " " * 12 + "Beerentasche", 26),
    # Town Map key item: same class-2 structure.
    0x3DEE28: (" " * 12 + "Town Map", " " * 12 + "Karte", 26),
    0x87A000: (" " * 12 + "Town Map", " " * 12 + "Karte", 26),
    # Hard Stone hold item: same class-2 structure.
    0x3DD32C: (" " * 12 + "Hard Stone", " " * 12 + "Harter Stein", 26),
    0x878504: (" " * 12 + "Hard Stone", " " * 12 + "Harter Stein", 26),
    # TM Case key item: same class-2 structure. "TM-Box" (not "TM-Hülle" /
    # "Etui", which are not the game's established German term) — issue #39.
    0x3DEEAC: (" " * 12 + "TM Case", " " * 12 + "TM-Box", 26),
    0x87A084: (" " * 12 + "TM Case", " " * 12 + "TM-Box", 26),
    # Roggenrola/Nodulithe ability "Weak Armor": fixed-width 17-byte cell, no
    # pointer. Absent from translation_ready.json and the Spanish extraction,
    # so it ships untouched in English. Official German name is "Sprödigkeit".
    0xA37069: ("Weak Armor", "Sprödigkeit", 17),
    # "Key Items" pocket name shown on the Bag screen (issue #39). Present in
    # translation_ready.json (not a class-2 gap like the others above) but the
    # generic reinserter's write is silently lost every build — the identical
    # string at 0x417B17 (Cube screen) reaches the ROM fine, this one never
    # does. Forced directly rather than traced further. "Basis It." is the
    # reporter's own rename away from "Seltene Items" ("rare items" — wrong,
    # inherited from the French mistranslation "Objets rares"), abbreviated
    # to fit the tight 10-byte cell (budget: stride 10 - 1 terminator = 9
    # glyphs, no padding — the next string starts immediately after).
    0x4162DE: ("Key Items", "Basis It.", 10),
}


def encode(name: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in name)


def apply_name_fixes(data: bytearray, fixes: dict) -> int:
    """Apply cell-bound name fixes; returns the number of cells patched."""
    patched = 0
    for offset, (old, new, stride) in fixes.items():
        old_bytes = encode(old)
        new_bytes = encode(new)
        if len(new_bytes) + 1 > stride:
            raise ValueError(f"0x{offset:X}: {new!r} does not fit a {stride}-byte cell")
        # Idempotency: check by new name length (handles old != new lengths).
        new_slice = bytes(data[offset : offset + len(new_bytes)])
        if new_slice == new_bytes and data[offset + len(new_bytes)] == 0xFF:
            continue  # already patched
        current = bytes(data[offset : offset + len(old_bytes)])
        if current != old_bytes or data[offset + len(old_bytes)] != 0xFF:
            raise ValueError(
                f"0x{offset:X}: cell does not hold expected name {old!r} "
                f"(found {current.hex(' ')})"
            )
        cell = new_bytes + b"\xff" + bytes(stride - len(new_bytes) - 1)
        data[offset : offset + stride] = cell
        patched += 1
    return patched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-de.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    patched = apply_name_fixes(data, NAME_FIXES)
    if patched:
        args.rom.write_bytes(data)
    print(f"Fixed-table name cells patched: {patched} (of {len(NAME_FIXES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
