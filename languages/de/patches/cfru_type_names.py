#!/usr/bin/env python3
"""Patch CFRU null-terminated type names at 0x3FE894 and frozen status at 0x3FE846 (German).

See ``patch_cfru_type_names_fr.py`` for the full root-cause writeup: the CFRU
engine stores a secondary type-name table at 0x3FE890 as sequential,
space(0x00)-terminated strings, each embedded inside a template « a TYPE move »;
the status/summary window reads TYPE NAMES directly from these bytes by
offset, independently of the pointer table repointed by the main pipeline.

Unlike French, almost none of the 18 CFRU type words happen to already match
their German spelling (only NORMAL is identical), so every type is patched
here (French only needed to patch the handful where FR and EN differ). Each
slot is only as wide as the *English* original. The stable constrained form
uses three-letter stems of the official German names, never an improvised
synonym or a term inherited from another language.

Also fixes the frozen-status condition word "ice" -> "gef" (Gefroren) at
0x3FE846 (same 3-byte slot, direct in-place patch; unrelated to the "GEF"
battle-HUD abbreviation from patch_status_abbrevs_fr.py / lang.yaml
status_abbrev, which lives in a different table entirely).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from languages.de.terminology import section as terminology_section  # noqa: E402
from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE

REV = CHAR_TO_BYTE


def encode(text: str) -> bytes:
    return bytes([REV[c] for c in text])


# (rom_offset_of_type_name, EN_name, DE_name)
# DE name must be <= len(EN_name) bytes to fit in-place. NORMAL is omitted:
# the German word is spelled identically, so the slot needs no change.
TYPE_PATCHES: list[tuple[int, str, str]] = [
    (0x3FE8A2, "FIGHTING", "KAM"),
    (0x3FE8B2, "FLYING",   "FLU"),
    (0x3FE8C0, "POISON",   "GIF"),
    (0x3FE8CE, "GROUND",   "BOD"),
    (0x3FE8DC, "ROCK",     "GES"),
    (0x3FE8E8, "BUG",      "KÄF"),
    (0x3FE8F3, "GHOST",    "GEI"),
    (0x3FE900, "STEEL",    "STA"),
    (0x3FE918, "FIRE",     "FEU"),
    (0x3FE924, "WATER",    "WAS"),
    (0x3FE931, "GRASS",    "PFL"),
    (0x3FE93F, "ELECTRIC", "ELE"),
    (0x3FE94F, "PSYCHIC",  "PSY"),
    (0x3FE95F, "ICE",      "EIS"),
    (0x3FE96A, "DRAGON",   "DRA"),
    (0x3FE978, "DARK",     "UNL"),
]

OFFICIAL_TYPES = terminology_section("types")
_TYPE_BY_ENGLISH = {
    "FIGHTING": "Fighting", "FLYING": "Flying", "POISON": "Poison",
    "GROUND": "Ground", "ROCK": "Rock", "BUG": "Bug", "GHOST": "Ghost",
    "STEEL": "Steel", "FIRE": "Fire", "WATER": "Water", "GRASS": "Grass",
    "ELECTRIC": "Electric", "PSYCHIC": "Psychic", "ICE": "Ice",
    "DRAGON": "Dragon", "DARK": "Dark",
}
for _offset, _english, _display in TYPE_PATCHES:
    _official = OFFICIAL_TYPES[_TYPE_BY_ENGLISH[_english]]
    if _display != _official[:3].upper():
        raise ValueError(f"German CFRU type stem {_display!r} diverges from {_official!r}")

# Frozen-status condition word: "ice" -> "gef" (Gefroren) at 0x3FE846 (3 chars,
# exact fit). This is a generic condition NOUN used inline in body text
# ("... is <condition> ..."), distinct from the 3-4 letter battle-HUD status
# abbreviations (GIF/VBR/GEF/SCH/PAR/KO) configured in languages/de/lang.yaml.
CONDITION_PATCHES: list[tuple[int, str, str]] = [
    (0x3FE846, "ice", "gef"),
]

# The generic translation pass runs before this fixed-table patch and may
# already have localized the condition cell.  Accept that known source state;
# all other unexpected values remain protected by the skip guard below.
SOURCE_ALIASES: dict[int, frozenset[str]] = {
    0x3FE846: frozenset({"Eis"}),
}


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
        for offset, en_expected, de_text in patch_list:
            current = _read_until(rom, offset, term_byte)
            if current == de_text:
                continue  # already done
            if current != en_expected and current not in SOURCE_ALIASES.get(offset, ()):
                print(
                    f"  WARN 0x{offset:07X}: expected «{en_expected}» got «{current}» — skip",
                    file=sys.stderr,
                )
                continue

            en_len = len(en_expected)
            de_encoded = encode(de_text)
            de_len = len(de_encoded)
            if de_len > en_len:
                print(
                    f"  ERROR 0x{offset:07X}: DE «{de_text}» ({de_len}) > EN «{en_expected}» ({en_len}) — skip",
                    file=sys.stderr,
                )
                continue

            if not dry_run:
                # Write DE bytes; pad remainder of original slot with the term_byte so
                # the slot boundary stays in place (space for type names, 0xFF for conditions).
                rom[offset : offset + de_len] = de_encoded
                pad_len = en_len - de_len
                if pad_len:
                    rom[offset + de_len : offset + en_len] = bytes([term_byte] * pad_len)

            print(f"  {offset:#09x}  «{en_expected}» -> «{de_text}»")
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
    print(f"patch_cfru_type_names_de: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
