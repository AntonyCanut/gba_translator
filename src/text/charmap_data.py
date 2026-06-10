"""
Canonical charmap data for CFRU/Pokemon GBA ROMs.

Single source of truth for character encoding. The sync_charmap.py script
reads this module to generate the TypeScript equivalents.
"""

from __future__ import annotations

from typing import Dict

POKEMON_TERMINATOR = 0xFF
POKEMON_NEWLINE = 0xFE

# char -> byte mapping (base + all language extensions)
CHAR_TO_BYTE: Dict[str, int] = {
    ' ': 0x00,
    # Digits
    '0': 0xA1, '1': 0xA2, '2': 0xA3, '3': 0xA4, '4': 0xA5,
    '5': 0xA6, '6': 0xA7, '7': 0xA8, '8': 0xA9, '9': 0xAA,
    # Punctuation
    '!': 0xAB, '?': 0xAC, '.': 0xAD, '-': 0xAE, '"': 0xB0,
    "'": 0xB4, ',': 0xB8, '/': 0xBA, ':': 0xF0,
    # Verified against EN ROM prose: Pokédollar, parentheses, ampersand.
    # Remaining entries follow the standard Gen III international charmap.
    '¥': 0xB7, '(': 0x5C, ')': 0x5D, '&': 0x2D,
    '%': 0x5B, '+': 0x2E, '=': 0x35, ';': 0x36,
    '<': 0x85, '>': 0x86, '♂': 0xB5, '♀': 0xB6,
    '×': 0xB9, 'º': 0x2A, 'ª': 0x2B,
    # Uppercase
    'A': 0xBB, 'B': 0xBC, 'C': 0xBD, 'D': 0xBE, 'E': 0xBF,
    'F': 0xC0, 'G': 0xC1, 'H': 0xC2, 'I': 0xC3, 'J': 0xC4,
    'K': 0xC5, 'L': 0xC6, 'M': 0xC7, 'N': 0xC8, 'O': 0xC9,
    'P': 0xCA, 'Q': 0xCB, 'R': 0xCC, 'S': 0xCD, 'T': 0xCE,
    'U': 0xCF, 'V': 0xD0, 'W': 0xD1, 'X': 0xD2, 'Y': 0xD3, 'Z': 0xD4,
    # Lowercase
    'a': 0xD5, 'b': 0xD6, 'c': 0xD7, 'd': 0xD8, 'e': 0xD9,
    'f': 0xDA, 'g': 0xDB, 'h': 0xDC, 'i': 0xDD, 'j': 0xDE,
    'k': 0xDF, 'l': 0xE0, 'm': 0xE1, 'n': 0xE2, 'o': 0xE3,
    'p': 0xE4, 'q': 0xE5, 'r': 0xE6, 's': 0xE7, 't': 0xE8,
    'u': 0xE9, 'v': 0xEA, 'w': 0xEB, 'x': 0xEC, 'y': 0xED, 'z': 0xEE,
    # Accented uppercase
    'À': 0x82, 'È': 0x83, 'É': 0x84,
    # Accented lowercase (Spanish + French)
    'à': 0x16, 'á': 0x17, 'ç': 0x19, 'è': 0x1A, 'é': 0x1B,
    'î': 0x20, 'ó': 0x23, 'ú': 0x27, 'ñ': 0x29,
    'â': 0x68, 'ù': 0x7F,
    'í': 0x6F,
}

# byte -> char (reverse mapping, first char wins for duplicates)
BYTE_TO_CHAR: Dict[int, str] = {}
for _char, _byte in CHAR_TO_BYTE.items():
    if _byte not in BYTE_TO_CHAR:
        BYTE_TO_CHAR[_byte] = _char

BYTE_TO_CHAR[POKEMON_NEWLINE] = '\n'

# Multi-byte control code leaders and their total lengths (leader + args)
CONTROL_CODES: Dict[int, int] = {
    0xFC: 2,
    0xFD: 2,
    0xF8: 2,
    0xF9: 2,
    0xF7: 3,
}
