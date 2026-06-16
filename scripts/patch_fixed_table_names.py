#!/usr/bin/env python3
"""Fix typos inside protected fixed-width name tables of the built ROM.

The move/species name tables come already French in the source ROM and
are deliberately left untouched by text reinsertion (see
``src/core/fixed_tables.py``). That contamination ships a few typos of
its own, which no translation pass can reach. This script rewrites the
affected cells in place, byte-exact, after the build.

Usage:
    python3 scripts/patch_fixed_table_names.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.text.charmap_data import CHAR_TO_BYTE

# offset -> (expected current name, corrected name, cell stride)
NAME_FIXES = {
    # Aerial Ace: official French name is "Aéropiqué" (final é missing
    # in the source table; dialogue and TM40 text use the correct form).
    0x1B3A5C: ("Aéropique", "Aéropiqué", 13),
    # Prof. Log's parcel item: never reached by the translation pipeline
    # (not in translation_ready.json nor Spanish extraction), stays English.
    0x879DFC: ("Parcel", "Colis", 7),
    # Package item (delivered to rival): the translation pipeline writes "Paquet"
    # at 0x879E74 (the extracted string with 12 leading zero-spaces), but the game
    # reads the inline name cell at 0x879E80 (12 bytes into the padded entry).
    0x879E80: ("Package", "Paquet", 8),
    # Berry Pouch key item: the centered, space-padded name cells are absent
    # from both translation_ready.json and the Spanish extraction, so the
    # inline-override pass skips them (no reference entry) and they ship in
    # English. The official French name "Sac à Baies" is byte-exact with
    # "Berry Pouch" (11 glyphs), so the 12-space centering and cell size are
    # preserved. Same case as Parcel/Package above: patched byte-exact here.
    0x3DEED8: (" " * 12 + "Berry Pouch", " " * 12 + "Sac à Baies", 26),
    0x87A0B0: (" " * 12 + "Berry Pouch", " " * 12 + "Sac à Baies", 26),
    # Town Map key item (bag name shown in the items list): the centered,
    # space-padded name cells are absent from both translation_ready.json and the
    # Spanish extraction, and combined_fr.txt has no entry for them, so neither the
    # reinsertion nor the inline-override pass ever reaches them — they ship in
    # English. Identical structure to Berry Pouch above: the game reads the name at
    # base+12 (0x3DEE34 / 0x87A00C), so the whole 26-byte cell (12 leading spaces +
    # name) is rewritten byte-exact here. "Carte" is the official French item name.
    0x3DEE28: (" " * 12 + "Town Map", " " * 12 + "Carte", 26),
    0x87A000: (" " * 12 + "Town Map", " " * 12 + "Carte", 26),
    # Hard Stone hold item: same class-2 structure as Berry Pouch/Town Map.
    # Absent from translation_ready.json and the Spanish extraction → never
    # reached by the reinsertion or inline-override pass → ships in English.
    # "Pierre Dure" (11 glyphs) fits the stride-26 cell (12 + 11 + FF + 2 pad).
    0x3DD32C: (" " * 12 + "Hard Stone", " " * 12 + "Pierre Dure", 26),
    0x878504: (" " * 12 + "Hard Stone", " " * 12 + "Pierre Dure", 26),
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
        # Idempotency: check by new name length (handles old ≠ new lengths).
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
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    patched = apply_name_fixes(data, NAME_FIXES)
    if patched:
        args.rom.write_bytes(data)
    print(f"Fixed-table name cells patched: {patched} (of {len(NAME_FIXES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
