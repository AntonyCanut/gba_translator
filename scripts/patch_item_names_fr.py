#!/usr/bin/env python3
"""Translate untranslated item NAME cells (Berries) in the built FR ROM.

Item names live as fixed-width cells inside the CFRU item table (``gItems``)
at 0x876074, stride 44: ``name[14]`` followed by the item data (id, price,
hold-effect, description pointer at +0x14…). These name cells are **copied
byte-for-byte from the source ROM** by the build pipeline — no translation
pass touches them (they are absent from translation_ready.json, combined_fr.txt
and the Spanish extraction). The Unbound source already ships French names for
the medicine/general items, but every Berry stayed English ("Aspear Berry",
"Oran Berry", …). This script rewrites the Berry name cells in place,
byte-exact, with their official French names ("Baie Willia", "Baie Oran", …).

It is data-driven: each cell whose current name exactly matches an English key
in BERRY_NAMES is rewritten with the French value. Cells that already hold the
French name are skipped (idempotent), and item data after the 14-byte name
field is never touched.

Usage:
    python3 scripts/patch_item_names_fr.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE

# CFRU item table (gItems). Each entry is 44 bytes: name[14] then item data
# (id u16 at +14, price u16 at +16, …, description pointer at +0x14). Only the
# 14-byte name field is ever rewritten here.
ITEM_TABLE_BASE = 0x876074
ITEM_STRIDE = 44
NAME_FIELD = 14  # bytes available for the name (13 glyphs max + 0xFF terminator)
# Generous upper bound on the number of item entries to scan. The exact-name
# match guard below makes over-scanning harmless (no random cell equals a Berry
# name), so we simply cover the whole table.
SCAN_COUNT = 1100

# English item name -> official French (France) name.
# Berry names verified individually against Bulbapedia / Poképédia "In other
# languages" tables (canonical localised names used by the official FR games).
# NOTE: CFRU spells the Gen VI berry "Maranga Berry" as "Marang Berry"; the key
# below matches the in-ROM English string.
BERRY_NAMES = {
    "Cheri Berry": "Baie Ceriz",
    "Chesto Berry": "Baie Maron",
    "Pecha Berry": "Baie Pêcha",
    "Rawst Berry": "Baie Fraive",
    "Aspear Berry": "Baie Willia",
    "Leppa Berry": "Baie Mepo",
    "Oran Berry": "Baie Oran",
    "Persim Berry": "Baie Kika",
    "Lum Berry": "Baie Prine",
    "Sitrus Berry": "Baie Sitrus",
    "Figy Berry": "Baie Figuy",
    "Wiki Berry": "Baie Wiki",
    "Mago Berry": "Baie Mago",
    "Aguav Berry": "Baie Gowav",
    "Iapapa Berry": "Baie Papaya",
    "Razz Berry": "Baie Framby",
    "Bluk Berry": "Baie Remu",
    "Nanab Berry": "Baie Nanab",
    "Wepear Berry": "Baie Repoi",
    "Pinap Berry": "Baie Nanana",
    "Pomeg Berry": "Baie Grena",
    "Kelpsy Berry": "Baie Alga",
    "Qualot Berry": "Baie Qualot",
    "Hondew Berry": "Baie Lonme",
    "Grepa Berry": "Baie Résin",
    "Tamato Berry": "Baie Tamato",
    "Cornn Berry": "Baie Siam",
    "Magost Berry": "Baie Mangou",
    "Rabuta Berry": "Baie Rabuta",
    "Nomel Berry": "Baie Tronci",
    "Spelon Berry": "Baie Kiwan",
    "Pamtre Berry": "Baie Palma",
    "Watmel Berry": "Baie Stekpa",
    "Durin Berry": "Baie Durin",
    "Belue Berry": "Baie Myrte",
    "Occa Berry": "Baie Chocco",
    "Passho Berry": "Baie Pocpoc",
    "Wacan Berry": "Baie Parma",
    "Rindo Berry": "Baie Ratam",
    "Yache Berry": "Baie Nanone",
    "Chople Berry": "Baie Pomroz",
    "Kebia Berry": "Baie Kébia",
    "Shuca Berry": "Baie Jouca",
    "Coba Berry": "Baie Cobaba",
    "Payapa Berry": "Baie Yapap",
    "Tanga Berry": "Baie Panga",
    "Charti Berry": "Baie Charti",
    "Kasib Berry": "Baie Sédra",
    "Haban Berry": "Baie Fraigo",
    "Colbur Berry": "Baie Lampou",
    "Babiri Berry": "Baie Babiri",
    "Chilan Berry": "Baie Zalis",
    "Liechi Berry": "Baie Lichii",
    "Ganlon Berry": "Baie Lingan",
    "Salac Berry": "Baie Sailak",
    "Petaya Berry": "Baie Pitaye",
    "Apicot Berry": "Baie Abriko",
    "Lansat Berry": "Baie Lansat",
    "Starf Berry": "Baie Frista",
    "Enigma Berry": "Baie Énigma",
    "Micle Berry": "Baie Micle",
    "Custap Berry": "Baie Chérim",
    "Jaboca Berry": "Baie Jaboca",
    "Rowap Berry": "Baie Pommo",
    "Kee Berry": "Baie Éka",
    "Marang Berry": "Baie Rangma",
    "Roseli Berry": "Baie Selro",
}


def encode(name: str) -> bytes:
    try:
        return bytes(CHAR_TO_BYTE[c] for c in name)
    except KeyError as exc:  # pragma: no cover - guards against bad data edits
        raise ValueError(f"character {exc.args[0]!r} not in CFRU charmap") from exc


def decode_name(data, offset: int) -> str:
    """Decode the name held in the 14-byte name field (up to the 0xFF)."""
    out = []
    for i in range(NAME_FIELD):
        b = data[offset + i]
        if b == 0xFF:
            break
        out.append(BYTE_TO_CHAR.get(b, "�"))
    return "".join(out)


def apply_item_name_fixes(data: bytearray, names: dict) -> int:
    """Rewrite item name cells whose English name is a key in ``names``.

    Returns the number of cells patched. The English string must fit and the
    French replacement must fit the 14-byte name field; item data after the
    name field is never touched. Idempotent: cells already holding the French
    name are skipped.
    """
    # Pre-validate every French replacement fits before writing anything.
    for fr in names.values():
        if len(encode(fr)) + 1 > NAME_FIELD:
            raise ValueError(f"{fr!r} does not fit a {NAME_FIELD}-byte name cell")

    fr_by_en = names
    patched = 0
    for i in range(SCAN_COUNT):
        offset = ITEM_TABLE_BASE + i * ITEM_STRIDE
        if offset + NAME_FIELD > len(data):
            break
        current = decode_name(data, offset)
        fr = fr_by_en.get(current)
        if fr is None:
            continue  # not a Berry we translate (or already French → no match)
        new_bytes = encode(fr)
        old_bytes = encode(current)
        # Sanity: the cell must really hold the English name + terminator.
        if (
            bytes(data[offset : offset + len(old_bytes)]) != old_bytes
            or data[offset + len(old_bytes)] != 0xFF
        ):
            continue
        # Write French name + terminator, then clear the rest of the span the
        # old name occupied so no stale glyphs trail past the terminator. Stays
        # entirely within the 14-byte name field.
        cleared = max(len(old_bytes), len(new_bytes)) + 1
        data[offset : offset + cleared] = (
            new_bytes + b"\xff" + bytes(cleared - len(new_bytes) - 1)
        )
        patched += 1
    return patched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    patched = apply_item_name_fixes(data, BERRY_NAMES)
    if patched:
        args.rom.write_bytes(data)
    print(f"Item name cells translated: {patched} (of {len(BERRY_NAMES)} known)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
