#!/usr/bin/env python3
"""
Text codec - Encoding and decoding for GBA ROM strings.

Provides a shared Pokemon/ASCII table with Spanish extensions.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple


ASCII_TABLE: Dict[str, int] = {chr(i): i for i in range(32, 127)}
ASCII_TERMINATOR = 0x00

POKEMON_TERMINATOR = 0xFF
POKEMON_NEWLINE = 0xFE

# Base Pokemon FireRed/LeafGreen table
POKEMON_TABLE: Dict[str, int] = {
    ' ': 0x00,
    '0': 0xA1, '1': 0xA2, '2': 0xA3, '3': 0xA4, '4': 0xA5,
    '5': 0xA6, '6': 0xA7, '7': 0xA8, '8': 0xA9, '9': 0xAA,
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
    '!': 0xAB, '?': 0xAC, '.': 0xAD, '-': 0xAE, ',': 0xB8,
    '\'': 0xB4, '"': 0xB0, '/': 0xBA, ':': 0xF0,
    'À': 0x82, 'È': 0x83, 'É': 0x84,
    # Verified against EN ROM prose ("It costs only <0xB7>50.",
    # "Hit <0xFD> time<0x5C>s<0x5D>!", "Brains <0x2D> Brawn"): Pokédollar,
    # parentheses, ampersand. Remaining entries follow the standard Gen III
    # international charmap, which every byte verified so far has matched.
    '¥': 0xB7, '(': 0x5C, ')': 0x5D, '&': 0x2D,
    '%': 0x5B, '+': 0x2E, '=': 0x35, ';': 0x36,
    '<': 0x85, '>': 0x86, '♂': 0xB5, '♀': 0xB6,
    '×': 0xB9, 'º': 0x2A, 'ª': 0x2B,
}

# Spanish extended characters (reverse-engineered from ROM bytes)
SPANISH_EXTENDED_TABLE: Dict[str, int] = {
    'á': 0x17,  # Látigo, Rápido, Sonámbulo, dinámico, Estándar
    'é': 0x1B,  # Pétalo, Mimético, Kinético, Pokémon
    'í': 0x6F,  # Cuídate mucho!
    'ó': 0x23,  # Doblebofetón, Pisotón, Constricción, Supersónico
    'ú': 0x27,  # música de batalla
    'ñ': 0x29,  # Puño
}

POKEMON_TABLE.update(SPANISH_EXTENDED_TABLE)

# French extended characters (reverse-engineered from ROM bytes)
FRENCH_EXTENDED_TABLE: Dict[str, int] = {
    'à': 0x16,  # chercher à manger
    'ç': 0x19,  # façon
    'è': 0x1A,  # très
    'î': 0x20,  # naît
    'â': 0x68,  # pâtissiers
    'ù': 0x7F,  # où
}

POKEMON_TABLE.update(FRENCH_EXTENDED_TABLE)

# Spanish alias characters mapped to base punctuation.
SPANISH_ALIASES = {
    '¡': '!',
    '¿': '?',
}

# Characters not present in the ROM font. Normalize to safe ASCII.
ENCODE_ALIASES = {
    'œ': 'oe',
    'Œ': 'OE',
    'ê': 'e',
    'ô': 'o',
    'û': 'u',
    'ä': 'a',
    'ë': 'e',
    'ï': 'i',
    'ö': 'o',
    'ü': 'u',
    'ÿ': 'y',
    'Â': 'A',
    'Ê': 'E',
    'Î': 'I',
    'Ô': 'O',
    'Û': 'U',
    'Ä': 'A',
    'Ë': 'E',
    'Ï': 'I',
    'Ö': 'O',
    'Ü': 'U',
    'Ÿ': 'Y',
    'Ç': 'ç',
    'Ù': 'U',
    'Ú': 'U',
    'Ì': 'I',
    'Í': 'I',
    'Ò': 'O',
    'Ó': 'O',
    'Ñ': 'N',
    'Á': 'A',
    'ì': 'i',
    'ò': 'o',
    '°': 'º',
    'ß': 's',
    '！': '!',
    '？': '?',
    # Typographic characters normalized to encodable equivalents.
    '‘': "'",   # ‘
    '’': "'",   # ’
    '“': '"',   # “
    '”': '"',   # ”
    '«': '"',   # «
    '»': '"',   # »
    '…': '...', # …
    '—': '-',   # —
    '–': '-',   # –
    'ー': '-',   # ー (chōonpu, JP-leftover strings)
    ' ': ' ',   # non-breaking space
    '　': ' ',   # 　 ideographic space (JP-leftover strings)
    '​': '',    # zero-width space
    '。': '.',   # 。
    '・': '.',   # ・
    '·': '.',   # ·
    '‥': '..',  # ‥
}

CONTROL_CODE_ENCODE = {
    '\n': POKEMON_NEWLINE,
}

CONTROL_CODE_DECODE = {
    POKEMON_NEWLINE: '\n',
}

HEX_TOKEN_RE = re.compile(r'^(?:0x)?([0-9A-Fa-f]{2})$')


class TextEncoder:
    """
    Encode strings into ASCII or Pokemon byte sequences.
    """

    ASCII_TABLE = ASCII_TABLE
    POKEMON_TABLE = POKEMON_TABLE
    ASCII_TERMINATOR = ASCII_TERMINATOR
    POKEMON_TERMINATOR = POKEMON_TERMINATOR

    @staticmethod
    def _parse_hex_token(text: str, index: int) -> Optional[Tuple[int, int]]:
        if text[index] != '<':
            return None
        end = text.find('>', index + 1)
        if end == -1:
            return None
        token = text[index + 1:end]
        match = HEX_TOKEN_RE.match(token)
        if not match:
            return None
        return int(match.group(1), 16), end + 1

    @classmethod
    def encode_ascii(cls, text: str) -> bytes:
        encoded = []
        i = 0
        while i < len(text):
            token = cls._parse_hex_token(text, i)
            if token:
                value, i = token
                encoded.append(value)
                continue

            char = text[i]
            if char in cls.ASCII_TABLE:
                encoded.append(cls.ASCII_TABLE[char])
            else:
                encoded.append(ord('?'))
            i += 1

        encoded.append(cls.ASCII_TERMINATOR)
        return bytes(encoded)

    @classmethod
    def encode_pokemon(cls, text: str) -> bytes:
        for src, dst in ENCODE_ALIASES.items():
            text = text.replace(src, dst)

        encoded = []
        i = 0
        while i < len(text):
            token = cls._parse_hex_token(text, i)
            if token:
                value, i = token
                encoded.append(value)
                continue

            char = text[i]
            if char in CONTROL_CODE_ENCODE:
                encoded.append(CONTROL_CODE_ENCODE[char])
                i += 1
                continue

            if char in cls.POKEMON_TABLE:
                encoded.append(cls.POKEMON_TABLE[char])
            elif char in SPANISH_ALIASES:
                base = SPANISH_ALIASES[char]
                encoded.append(cls.POKEMON_TABLE.get(base, cls.POKEMON_TABLE['?']))
            else:
                encoded.append(cls.POKEMON_TABLE.get('?', 0xAC))
            i += 1

        encoded.append(cls.POKEMON_TERMINATOR)
        return bytes(encoded)

    @classmethod
    def encode(cls, text: str, encoding: str) -> bytes:
        if encoding == 'ascii':
            return cls.encode_ascii(text)
        if encoding == 'pokemon':
            return cls.encode_pokemon(text)
        raise ValueError(f"Unknown encoding: {encoding}")


class TextDecoder:
    """
    Decode ASCII or Pokemon byte sequences into strings.
    """

    ASCII_DECODE = {i: chr(i) for i in range(32, 127)}
    POKEMON_DECODE = {v: k for k, v in POKEMON_TABLE.items()}
    POKEMON_DECODE.update(CONTROL_CODE_DECODE)

    @staticmethod
    def _unknown_char(byte: int, preserve_unknown: bool) -> str:
        if preserve_unknown:
            return f"<0x{byte:02X}>"
        return '?'

    @classmethod
    def decode_ascii(cls, data: bytes, preserve_unknown: bool = False) -> str:
        result = []
        for byte in data:
            if byte == ASCII_TERMINATOR:
                break
            if byte in cls.ASCII_DECODE:
                result.append(cls.ASCII_DECODE[byte])
            else:
                result.append(cls._unknown_char(byte, preserve_unknown))
        return ''.join(result)

    @classmethod
    def decode_pokemon(
        cls,
        data: bytes,
        preserve_unknown: bool = False,
        prefer_inverted_punctuation: bool = False,
    ) -> str:
        result = []
        for byte in data:
            if byte == POKEMON_TERMINATOR:
                break
            if byte in CONTROL_CODE_DECODE:
                result.append(CONTROL_CODE_DECODE[byte])
                continue
            if byte in cls.POKEMON_DECODE:
                char = cls.POKEMON_DECODE[byte]
                if prefer_inverted_punctuation:
                    if char == '!':
                        char = '¡'
                    elif char == '?':
                        char = '¿'
                result.append(char)
            else:
                result.append(cls._unknown_char(byte, preserve_unknown))
        return ''.join(result)

    @classmethod
    def decode(
        cls,
        data: bytes,
        encoding: str,
        preserve_unknown: bool = False,
        prefer_inverted_punctuation: bool = False,
    ) -> str:
        if encoding == 'ascii':
            return cls.decode_ascii(data, preserve_unknown=preserve_unknown)
        if encoding == 'pokemon':
            return cls.decode_pokemon(
                data,
                preserve_unknown=preserve_unknown,
                prefer_inverted_punctuation=prefer_inverted_punctuation,
            )
        raise ValueError(f"Unknown encoding: {encoding}")
