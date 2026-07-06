#!/usr/bin/env python3
"""Translate Pokédex species-category strings (table 0x1A357CC) to German.

The Pokédex info screen renders ``<category> Pokémon`` where ``<category>`` is
read from a table at ROM offset **0x1A357CC**, stride 36 bytes, indexed by
National Dex number (entry 0 = #1 Bulbasaur).  Each entry reserves **12 bytes**
for the category: up to 11 CFRU-encoded characters followed by a 0xFF
terminator.  The numeric height/weight/scale fields start at record+12, so the
patch must never write past that boundary.

Without this patch every category displays in English (e.g. ``Poison Pin
Pokémon``, ``Licking Pokémon``).  With the patch they display in German
(e.g. ``Giftstachel-Pokémon``, ``Schlecker-Pokémon``).

The mapping is loaded from ``languages/de/data/pokedex_categories_de.json`` (653 EN→DE
pairs).  Entries not found in the mapping are left unchanged.  The patch is
idempotent: running it twice produces the same ROM bytes.

Usage (run by ``make build-de`` after the base injection):
    python3 languages/de/patches/pokedex_categories.py --rom output/roms/GenedRom-de.gba
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Table geometry
# ---------------------------------------------------------------------------
TABLE_ADDR = 0x1A357CC   # first record = Dex #1
STRIDE = 36              # bytes per record
MAX_ENTRIES = 908        # up to Dex #907 (0-indexed: entries 0..906)
CELL_SIZE = 12           # bytes reserved for category (11 chars + 0xFF)
MAX_CHARS = CELL_SIZE - 1  # 11

# ---------------------------------------------------------------------------
# CFRU charmap (inline — avoids sys.path gymnastics when run from Makefile)
# ---------------------------------------------------------------------------
CHAR_TO_BYTE: dict[str, int] = {
    ' ': 0x00,
    '0': 0xA1, '1': 0xA2, '2': 0xA3, '3': 0xA4, '4': 0xA5,
    '5': 0xA6, '6': 0xA7, '7': 0xA8, '8': 0xA9, '9': 0xAA,
    '!': 0xAB, '?': 0xAC, '.': 0xAD, '-': 0xAE, '"': 0xB0,
    "'": 0xB4, ',': 0xB8, '/': 0xBA, ':': 0xF0,
    '"': 0xB1, '"': 0xB2, '«': 0xB1, '»': 0xB2,
    '¥': 0xB7, '(': 0x5C, ')': 0x5D, '&': 0x2D,
    '%': 0x5B, '+': 0x2E, '=': 0x35, ';': 0x36,
    '<': 0x85, '>': 0x86, '♂': 0xB5, '♀': 0xB6,
    '×': 0xB9, 'º': 0x2A, 'ª': 0x2B,
    'A': 0xBB, 'B': 0xBC, 'C': 0xBD, 'D': 0xBE, 'E': 0xBF,
    'F': 0xC0, 'G': 0xC1, 'H': 0xC2, 'I': 0xC3, 'J': 0xC4,
    'K': 0xC5, 'L': 0xC6, 'M': 0xC7, 'N': 0xC8, 'O': 0xC9,
    'P': 0xCA, 'Q': 0xCB, 'R': 0xCC, 'S': 0xCD, 'T': 0xCE,
    'U': 0xCF, 'V': 0xD0, 'W': 0xD1, 'X': 0xD2, 'Y': 0xD3, 'Z': 0xD4,
    'a': 0xD5, 'b': 0xD6, 'c': 0xD7, 'd': 0xD8, 'e': 0xD9,
    'f': 0xDA, 'g': 0xDB, 'h': 0xDC, 'i': 0xDD, 'j': 0xDE,
    'k': 0xDF, 'l': 0xE0, 'm': 0xE1, 'n': 0xE2, 'o': 0xE3,
    'p': 0xE4, 'q': 0xE5, 'r': 0xE6, 's': 0xE7, 't': 0xE8,
    'u': 0xE9, 'v': 0xEA, 'w': 0xEB, 'x': 0xEC, 'y': 0xED, 'z': 0xEE,
    'À': 0x01, 'Á': 0x02, 'Â': 0x03, 'Ç': 0x04, 'È': 0x05, 'É': 0x06,
    'Ê': 0x07, 'Ë': 0x08, 'Ì': 0x09, 'Î': 0x0B, 'Ï': 0x0C, 'Ò': 0x0D,
    'Ó': 0x0E, 'Ô': 0x0F, 'Œ': 0x10, 'Ù': 0x11, 'Ú': 0x12, 'Û': 0x13,
    'Ñ': 0x14, 'ß': 0x15, 'Í': 0x5A,
    'à': 0x16, 'á': 0x17, 'ç': 0x19, 'è': 0x1A, 'é': 0x1B,
    'ê': 0x1C, 'ë': 0x1D, 'ì': 0x1E, 'î': 0x20, 'ï': 0x21,
    'ò': 0x22, 'ó': 0x23, 'ô': 0x24, 'œ': 0x25, 'ù': 0x26,
    'ú': 0x27, 'û': 0x28, 'ñ': 0x29,
    'â': 0x68,
    'í': 0x6F,
    'Ä': 0xF1, 'Ö': 0xF2, 'Ü': 0xF3,
    'ä': 0xF4, 'ö': 0xF5, 'ü': 0xF6,
}

BYTE_TO_CHAR: dict[int, str] = {}
for _c, _b in CHAR_TO_BYTE.items():
    if _b not in BYTE_TO_CHAR:
        BYTE_TO_CHAR[_b] = _c


def _decode_cell(data: bytes | bytearray, offset: int) -> str:
    """Decode up to CELL_SIZE-1 bytes from *offset*, stopping at 0xFF."""
    result: list[str] = []
    for i in range(MAX_CHARS):
        b = data[offset + i]
        if b == 0xFF:
            break
        result.append(BYTE_TO_CHAR.get(b, f'[{b:02X}]'))
    return ''.join(result)


def _encode(text: str) -> bytes:
    """Encode *text* to CFRU bytes + 0xFF terminator."""
    if len(text) > MAX_CHARS:
        raise ValueError(f'Category too long ({len(text)} > {MAX_CHARS}): {text!r}')
    raw = bytearray()
    for ch in text:
        if ch not in CHAR_TO_BYTE:
            raise ValueError(f'Unencodable character {ch!r} in {text!r}')
        raw.append(CHAR_TO_BYTE[ch])
    raw.append(0xFF)
    return bytes(raw)


def load_mapping(data_dir: Path) -> dict[str, str]:
    path = data_dir / 'pokedex_categories_de.json'
    with path.open(encoding='utf-8') as fh:
        return json.load(fh)


def apply_patch(data: bytearray, mapping: dict[str, str]) -> tuple[int, int]:
    """Write DE categories into *data* in-place.

    Returns (patched, skipped) counts.
    """
    patched = 0
    skipped = 0
    for idx in range(MAX_ENTRIES):
        cell_offset = TABLE_ADDR + idx * STRIDE
        if cell_offset + CELL_SIZE > len(data):
            break
        en_cat = _decode_cell(data, cell_offset)
        if not en_cat or '[' in en_cat:
            # empty or contains undecodable bytes — leave alone
            skipped += 1
            continue
        de_cat = mapping.get(en_cat)
        if de_cat is None:
            skipped += 1
            continue
        de_bytes = _encode(de_cat)
        # Pad remaining space with 0xFF to clear old bytes
        padded = de_bytes + b'\xFF' * (CELL_SIZE - len(de_bytes))
        current = bytes(data[cell_offset:cell_offset + CELL_SIZE])
        if current == padded:
            continue  # already patched — idempotent
        data[cell_offset:cell_offset + CELL_SIZE] = padded
        patched += 1
    return patched, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--rom', type=Path, default=Path('output/roms/GenedRom-de.gba'),
        help='DE ROM to patch in place',
    )
    parser.add_argument(
        '--data-dir', type=Path, default=Path('languages/de/data'),
        help='Directory containing pokedex_categories_de.json',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Report what would be patched without writing',
    )
    args = parser.parse_args(argv)

    mapping = load_mapping(args.data_dir)
    data = bytearray(args.rom.read_bytes())
    patched, skipped = apply_patch(data, mapping)
    if not args.dry_run and patched:
        args.rom.write_bytes(data)
    print(
        f'Pokédex categories DE patch: {patched} translated, '
        f'{skipped} skipped (no mapping / undecodable)'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
