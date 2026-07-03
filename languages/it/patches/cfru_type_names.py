#!/usr/bin/env python3
"""Patch CFRU null-terminated type names at 0x3FE894 and frozen status at 0x3FE846 (Italian).

See ``patch_cfru_type_names_fr.py`` for the full root-cause writeup: the CFRU
engine stores a secondary type-name table at 0x3FE890 as sequential,
space(0x00)-terminated strings, each embedded inside a template « a TYPE move »;
the status/summary window reads TYPE NAMES directly from these bytes by
offset, independently of the pointer table repointed by the main pipeline.

Each slot is only as wide as the *English* original, so official Italian type
names longer than their slot are abbreviated (documented per-entry below).
NORMAL is left untouched: "Normale" (7) overflows the 6-byte EN slot and the
unabbreviated English word reads fine in context, matching the FR/DE
precedent of only patching entries that actually need it.

Also fixes the frozen-status condition word "ice" -> "gel" (abbrev of
"gelo", frost) at 0x3FE846 (same 3-byte slot, direct in-place patch;
unrelated to the "CON" battle-HUD freeze abbreviation from
patch_status_abbrevs_fr.py / lang.yaml status_abbrev, which lives in a
different table entirely).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE

REV = CHAR_TO_BYTE


def encode(text: str) -> bytes:
    return bytes([REV[c] for c in text])


# (rom_offset_of_type_name, EN_name, IT_name)
# IT name must be <= len(EN_name) bytes to fit in-place. NORMAL is omitted:
# "Normale" (7) would overflow the 6-byte EN slot.
TYPE_PATCHES: list[tuple[int, str, str]] = [
    (0x3FE8A2, "FIGHTING", "LOTTA"),    # 8 -> 5 chars
    (0x3FE8B2, "FLYING",   "VOLA"),     # 6 -> 4 chars (abbrev of Volante)
    (0x3FE8C0, "POISON",   "VELENO"),   # 6 -> 6 exact fit
    (0x3FE8CE, "GROUND",   "TERRA"),    # 6 -> 5 chars
    (0x3FE8DC, "ROCK",     "ROCC"),     # 4 -> 4 exact fit (abbrev of Roccia)
    (0x3FE8E8, "BUG",      "COL"),      # 3 -> 3 exact fit (abbrev of Coleottero)
    (0x3FE8F3, "GHOST",    "SPETT"),    # 5 -> 5 exact fit (abbrev of Spettro)
    (0x3FE900, "STEEL",    "ACCIA"),    # 5 -> 5 exact fit (abbrev of Acciaio)
    (0x3FE918, "FIRE",     "FUOC"),     # 4 -> 4 exact fit (abbrev of Fuoco)
    (0x3FE924, "WATER",    "ACQUA"),    # 5 -> 5 exact fit
    (0x3FE931, "GRASS",    "ERBA"),     # 5 -> 4 chars
    (0x3FE93F, "ELECTRIC", "ELETTRO"),  # 8 -> 7 chars
    (0x3FE94F, "PSYCHIC",  "PSICO"),    # 7 -> 5 chars
    (0x3FE95F, "ICE",      "GHI"),      # 3 -> 3 exact fit (abbrev of Ghiaccio)
    (0x3FE96A, "DRAGON",   "DRAGO"),    # 6 -> 5 chars
    (0x3FE978, "DARK",     "BUIO"),     # 4 -> 4 exact fit
]

# Frozen-status condition word: "ice" -> "gel" (abbrev of "gelo", frost) at
# 0x3FE846 (3 chars, exact fit). This is a generic condition NOUN used inline
# in body text ("... is <condition> ..."), distinct from the 3-letter
# battle-HUD status abbreviations (PSN/SCT/CON/PAR/SON/KO) configured in
# languages/it/lang.yaml status_abbrev.
CONDITION_PATCHES: list[tuple[int, str, str]] = [
    (0x3FE846, "ice", "gel"),
]


def _read_until(rom: bytearray, offset: int, terminator: int) -> str:
    """Decode bytes at offset until terminator byte."""
    chars = []
    i = offset
    while i < len(rom) and rom[i] != terminator:
        chars.append(BYTE_TO_CHAR.get(rom[i], f"[{rom[i]:02X}]"))
        i += 1
    return "".join(chars)


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    rom = bytearray(rom_path.read_bytes())
    changes = 0

    # Type names: space-separated inside « a TYPE move » template — terminate at 0x00 (space).
    # Condition names: standalone 0xFF-terminated strings — terminate at 0xFF.
    patch_groups: list[tuple[list, int]] = [
        (TYPE_PATCHES, 0x00),
        (CONDITION_PATCHES, 0xFF),
    ]

    for patch_list, term_byte in patch_groups:
        for offset, en_expected, it_text in patch_list:
            current = _read_until(rom, offset, term_byte)
            if current == it_text:
                continue  # already done
            if current != en_expected:
                print(
                    f"  WARN 0x{offset:07X}: expected «{en_expected}» got «{current}» — skip",
                    file=sys.stderr,
                )
                continue

            en_len = len(en_expected)
            it_encoded = encode(it_text)
            it_len = len(it_encoded)
            if it_len > en_len:
                print(
                    f"  ERROR 0x{offset:07X}: IT «{it_text}» ({it_len}) > EN «{en_expected}» ({en_len}) — skip",
                    file=sys.stderr,
                )
                continue

            if not dry_run:
                # Write IT bytes; pad remainder of original slot with the term_byte so
                # the slot boundary stays in place (space for type names, 0xFF for conditions).
                rom[offset : offset + it_len] = it_encoded
                pad_len = en_len - it_len
                if pad_len:
                    rom[offset + it_len : offset + en_len] = bytes([term_byte] * pad_len)

            print(f"  {offset:#09x}  «{en_expected}» -> «{it_text}»")
            changes += 1

    if not dry_run and changes:
        rom_path.write_bytes(rom)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = apply_patches(args.rom, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_cfru_type_names_it: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
