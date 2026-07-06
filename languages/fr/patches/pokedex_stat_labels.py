#!/usr/bin/env python3
"""Patch the Pokédex "Liste Pokémon" base-stat abbreviations to French.

The Pokédex info page ("Liste Pokémon" / national-dex flavour screen) draws
six short stat labels — HP, Atk, Def, SpA, SpD, Spe — each through its own
pointer, one string per label, in game-engine order (HP, Atk, Def, Spe, SpA,
SpD). Every string has the same fixed layout: label letters, then enough
0x00 (space) padding to total 4 charmap bytes, then the 2-byte {STR_VAR_2}
placeholder (0xFD 0x02) that the engine fills in with the stat's numeric
value at render time, then the 0xFF terminator — 7 bytes per entry, packed
back-to-back with no gap:

    <label><spaces to 4 bytes><0xFD><0x02><0xFF>

Two byte-identical copies of the six-entry block exist in the ROM (each with
its own 6-pointer table immediately before the strings), at 0x8C972C /
0x8C9744 and 0x964A3C / 0x964A54. Both are patched so the fix holds
regardless of which screen variant reads which copy.

Why this is a class-3 *post-build* patch and not a `combined_fr.txt` entry:
these strings sit outside the pointer-chasing extractor's reach (absent from
the injection JSON, the Spanish extract AND `combined_fr.txt`), so no
translation pass touches them — confirmed empirically: they still render in
English in a freshly built FR ROM. Each FR abbreviation is picked to fit the
same 4-byte label+padding budget as its EN original, so in-place replacement
never needs to move the {STR_VAR_2}/terminator tail.

French labels (official-style 2-3 letter abbreviations):
    HP  -> PV   (Points de Vie)
    Atk -> Att  (Attaque)
    Def -> Déf  (Défense)
    Spe -> Vit  (Vitesse)
    SpA -> AtS  (Attaque Spéciale)
    SpD -> DéS  (Défense Spéciale)

The patch is idempotent and self-healing: it accepts either the EN original
or the current FR bytes at each offset, so re-running it over an
already-built ROM converges without a full rebuild.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import POKEMON_TABLE  # noqa: E402

ENC = POKEMON_TABLE
GBA_BASE = 0x08000000

# {STR_VAR_2} placeholder + terminator, common to every entry.
_VAR2_TERM = bytes([0xFD, 0x02, 0xFF])
_ENTRY_LABEL_BYTES = 4  # label + space padding budget, before _VAR2_TERM

# Pointer-table base offsets for the two duplicate copies in the ROM. Each
# table holds 6 consecutive 4-byte pointers, one per stat, in this order.
PTR_TABLE_OFFSETS = [0x8C972C, 0x964A3C]
PTR_STRIDE = 4
STAT_ORDER = ["hp", "atk", "def", "spe", "spa", "spd"]

_FR_LABELS = {
    "hp": "PV",
    "atk": "Att",
    "def": "Déf",
    "spe": "Vit",
    "spa": "AtS",
    "spd": "DéS",
}

_EN_LABELS = {
    "hp": "HP",
    "atk": "Atk",
    "def": "Def",
    "spe": "Spe",
    "spa": "SpA",
    "spd": "SpD",
}


def _encode(text: str) -> bytes:
    return bytes([ENC[c] for c in text])


def _entry_bytes(label: str) -> bytes:
    encoded = _encode(label)
    if len(encoded) > _ENTRY_LABEL_BYTES:
        raise ValueError(f"label {label!r} encodes to {len(encoded)} bytes, budget is {_ENTRY_LABEL_BYTES}")
    padded = encoded + bytes([0x00]) * (_ENTRY_LABEL_BYTES - len(encoded))
    return padded + _VAR2_TERM


_EN_ENTRIES = {key: _entry_bytes(label) for key, label in _EN_LABELS.items()}
_FR_ENTRIES = {key: _entry_bytes(label) for key, label in _FR_LABELS.items()}


def apply_to_rom(rom: bytearray, dry_run: bool = False) -> int:
    changes = 0

    for table_offset in PTR_TABLE_OFFSETS:
        for i, key in enumerate(STAT_ORDER):
            ptr_off = table_offset + i * PTR_STRIDE
            if ptr_off + 4 > len(rom):
                print(
                    f"  WARN table 0x{table_offset:06X} index={i} ({key}): "
                    f"pointer table offset out of range for this ROM — skip",
                    file=sys.stderr,
                )
                continue
            ptr_raw = struct.unpack_from("<I", rom, ptr_off)[0]
            file_off = ptr_raw - GBA_BASE

            if not (0 < file_off < len(rom)):
                print(
                    f"  WARN table 0x{table_offset:06X} index={i} ({key}): "
                    f"pointer 0x{ptr_raw:08X} out of range — skip",
                    file=sys.stderr,
                )
                continue

            en_entry = _EN_ENTRIES[key]
            fr_entry = _FR_ENTRIES[key]
            entry_len = len(en_entry)
            current = bytes(rom[file_off:file_off + entry_len])

            if current == fr_entry:
                continue  # already at target
            if current != en_entry:
                print(
                    f"  WARN 0x{file_off:06X} ({key}): bytes {current.hex()} match "
                    f"neither EN {en_entry.hex()} nor FR {fr_entry.hex()} — skip",
                    file=sys.stderr,
                )
                continue

            if not dry_run:
                rom[file_off:file_off + entry_len] = fr_entry

            print(
                f"  0x{file_off:06X}  «{_EN_LABELS[key]}» -> «{_FR_LABELS[key]}» "
                f"(table 0x{table_offset:06X})"
            )
            changes += 1

    return changes


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    rom = bytearray(rom_path.read_bytes())
    changes = apply_to_rom(rom, dry_run=dry_run)
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
    print(f"patch_pokedex_stat_labels_fr: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
