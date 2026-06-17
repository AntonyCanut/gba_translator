#!/usr/bin/env python3
"""Patch CFRU null-terminated type names at 0x3FE894 and frozen status at 0x3FE846.

The CFRU engine stores a secondary type-name table at 0x3FE890 as sequential
null-terminated strings, each embedded inside a template « a TYPE move ».
The status/summary window reads TYPE NAMES directly from these bytes by offset,
independently of the pointer table at 0x3FEA28 (which was already repointed to
« une capacité X » strings in free space by the main pipeline).

This post-build step patches the TYPE NAME bytes in-place so the status window
displays French type names.  Only replaces; never overflows the original slot,
so names longer than the EN original are abbreviated (e.g. GLACE→GLA, ROCHE→ROC).

Also fixes the frozen-status condition « ice » → « gel » at 0x3FE846 (same
length, direct in-place patch; the pointer at 0x2500F0 still points there).

IMPORTANT — type vs status must stay separate. « GEL » is the *frozen status*
(see patch_status_abbrevs_fr.py FRZ→GEL and CONDITION_PATCHES below); it must
never be reused as the *Ice type* name, or the summary window would conflate a
status with a type. The Ice type is therefore « GLA » (abbrev of GLACE), and the
frozen status stays « gel ». These two patch groups use different terminators
(0x00 space for the packed type table, 0xFF for standalone status strings).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE

REV = CHAR_TO_BYTE


def encode(text: str) -> bytes:
    return bytes([REV[c] for c in text])


# (rom_offset_of_type_name, EN_name, FR_name)
# FR name must be <= len(EN_name) bytes to fit in-place.
TYPE_PATCHES: list[tuple[int, str, str]] = [
    # NORMAL  → NORMAL  (same)   skip
    (0x3FE8A2, "FIGHTING", "COMBAT"),   # 8 → 6 chars
    (0x3FE8B2, "FLYING",   "VOL"),      # 6 → 3 chars
    # POISON  → POISON  (same)   skip
    (0x3FE8CE, "GROUND",   "SOL"),      # 6 → 3 chars
    (0x3FE8DC, "ROCK",     "ROC"),      # 4 → 3 chars  (ROCHE overflow slot)
    # BUG     → BUG     (3 chars, no good 3-char FR abbrev)  skip
    (0x3FE8F3, "GHOST",    "SPECT"),    # 5 → 5 exact fit  (abbrev SPECTRE)
    (0x3FE900, "STEEL",    "ACIER"),    # 5 → 5 exact fit
    (0x3FE918, "FIRE",     "FEU"),      # 4 → 3 chars
    (0x3FE924, "WATER",    "EAU"),      # 5 → 3 chars
    (0x3FE931, "GRASS",    "PLANT"),    # 5 → 5 exact fit  (abbrev PLANTE)
    (0x3FE93F, "ELECTRIC", "ÉLECTR"),   # 8 → 6 chars
    (0x3FE94F, "PSYCHIC",  "PSY"),      # 7 → 3 chars
    (0x3FE95F, "ICE",      "GLA"),      # 3 → 3 exact fit  (abbrev GLACE — NOT « GEL »)
    # DRAGON  → DRAGON  (same in FR)   skip
    (0x3FE978, "DARK",    "TÈN"),      # 4 → 3 chars  (abbrev TÉNÈBRES; 1 space pad)
    # NOTE  Ice/Glace MUST NOT be abbreviated to « GEL »: GEL is the *frozen
    #       status* (cf. patch_status_abbrevs_fr.py FRZ→GEL and the battle
    #       condition « gel » below). Using GEL for the *type* would collide
    #       status and type in the summary window. The slot is only 3 bytes
    #       wide (packed table, read by hardcoded offset), so the full word
    #       « GLACE » (5) cannot fit in-place; « GLA » is the 3-char abbrev.
    #       Likewise ROCK→ROC: « ROCHE » (5) overflows the 4-byte slot.
]

# Type names that were shipped with a *previous* (now-corrected) FR value.
# Listing the old value here lets the build self-heal: the patcher upgrades an
# already-built FR ROM (e.g. one still holding « GEL ») to the new value instead
# of warning « expected ICE got GEL — skip ».
MIGRATE_FROM: dict[int, tuple[str, ...]] = {
    0x3FE95F: ("GEL",),  # ICE: was wrongly abbreviated to the frozen-status word
    0x3FE978: (),        # DARK: no prior shipped value to migrate from
}

# Frozen status condition: « ice » → « gel » at 0x3FE846 (3 chars, exact fit).
# This IS the battle frozen *status* (legitimately « gel » in FR), 0xFF-terminated
# and reached via a separate pointer (0x2500F0) — distinct from the type table above.
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
        for offset, en_expected, fr_text in patch_list:
            current = _read_until(rom, offset, term_byte)
            if current == fr_text:
                continue  # already done
            acceptable = (en_expected, *MIGRATE_FROM.get(offset, ()))
            if current not in acceptable:
                print(
                    f"  WARN 0x{offset:07X}: expected one of {acceptable} got «{current}» — skip",
                    file=sys.stderr,
                )
                continue

            en_len = len(en_expected)
            fr_encoded = encode(fr_text)
            fr_len = len(fr_encoded)
            if fr_len > en_len:
                print(
                    f"  ERROR 0x{offset:07X}: FR «{fr_text}» ({fr_len}) > EN «{en_expected}» ({en_len}) — skip",
                    file=sys.stderr,
                )
                continue

            if not dry_run:
                # Write FR bytes; pad remainder of original slot with the term_byte so
                # the slot boundary stays in place (space for type names, 0xFF for conditions).
                rom[offset : offset + fr_len] = fr_encoded
                pad_len = en_len - fr_len
                if pad_len:
                    rom[offset + fr_len : offset + en_len] = bytes([term_byte] * pad_len)

            print(f"  {offset:#09x}  «{en_expected}» → «{fr_text}»")
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
    print(f"patch_cfru_type_names_fr: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
