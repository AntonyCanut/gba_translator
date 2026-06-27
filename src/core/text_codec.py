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
    # Directional double-quote glyphs. In the FireRed/CFRU font 0xB0 is the
    # ELLIPSIS glyph "…" (NOT a straight quote), so any quotation mark routed
    # to 0xB0 renders in-game as "…". The real quote glyphs are 0xB1 "“" and
    # 0xB2 "”" — the very bytes the English ROM uses itself, verified in its
    # prose: <0xB1>evolution this<0xB2>. Guillemets/curly quotes are folded
    # onto these in ENCODE_ALIASES; straight " is resolved by direction below.
    '“': 0xB1, '”': 0xB2,
    # Accented uppercase, standard Gen III international charmap. Verified
    # in-game by mGBA screenshot probes (À Ç È É Ê Ë Î Ï Ô Œ Ù Û) in both
    # the dialogue and intro fullscreen fonts, and against the French
    # species/move name tables of the source ROM (Électhor = 06 lecthor).
    # The previous trio (À 0x82, È 0x83, É 0x84) pointed at empty glyphs /
    # the superscript-e, rendering "Électhor" as "ᵉlecthor".
    'À': 0x01, 'Á': 0x02, 'Â': 0x03, 'Ç': 0x04, 'È': 0x05, 'É': 0x06,
    'Ê': 0x07, 'Ë': 0x08, 'Ì': 0x09, 'Î': 0x0B, 'Ï': 0x0C, 'Ò': 0x0D,
    'Ó': 0x0E, 'Ô': 0x0F, 'Œ': 0x10, 'Ù': 0x11, 'Ú': 0x12, 'Û': 0x13,
    'Ñ': 0x14, 'ß': 0x15, 'Í': 0x5A,
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

# French extended characters, standard Gen III international charmap.
# Verified in-game by mGBA screenshot probes: à ç è é ê ë î ï ô œ ù û all
# render at these codepoints in both the dialogue and intro fullscreen
# fonts. ù was previously mapped to 0x7F, an empty glyph in the intro
# fullscreen font and the vanilla FRLG fonts.
FRENCH_EXTENDED_TABLE: Dict[str, int] = {
    'à': 0x16,  # chercher à manger
    'ç': 0x19,  # façon
    'è': 0x1A,  # très
    'ê': 0x1C,  # être
    'ë': 0x1D,  # Noël
    'ì': 0x1E,
    'î': 0x20,  # naît
    'ï': 0x21,  # naïf
    'ò': 0x22,
    'ô': 0x24,  # bientôt
    'œ': 0x25,  # cœur
    'ù': 0x26,  # où
    'û': 0x28,  # sûr
    'â': 0x68,  # pâtissiers
}

POKEMON_TABLE.update(FRENCH_EXTENDED_TABLE)

# German umlauts — assigned to free slots 0x60-0x65 by commit 2c97f4e.
# Glyphs are drawn by scripts/patch_font_de.py (DE build only).
# These entries must live in POKEMON_TABLE so skip_aliases can reach them;
# ENCODE_ALIASES used to fold them to ASCII before table lookup (dead code).
GERMAN_UMLAUT_TABLE: Dict[str, int] = {
    'Ä': 0x60, 'Ö': 0x61, 'Ü': 0x62,
    'ä': 0x63, 'ö': 0x64, 'ü': 0x65,
}
GERMAN_UMLAUT_CHARS: frozenset = frozenset(GERMAN_UMLAUT_TABLE)

POKEMON_TABLE.update(GERMAN_UMLAUT_TABLE)

# Spanish alias characters mapped to base punctuation.
SPANISH_ALIASES = {
    '¡': '!',
    '¿': '?',
}

# Characters not present in the ROM font. Normalize to safe ASCII.
# ä ö ü Ä Ö Ü are listed here as ASCII fallbacks for FR/IT/ES (no glyphs).
# For DE, pass skip_aliases=GERMAN_UMLAUT_CHARS to encode_pokemon so they
# bypass these aliases and reach their POKEMON_TABLE slots 0x60-0x65.
ENCODE_ALIASES = {
    'ä': 'a',
    'ö': 'o',
    'ü': 'u',
    'ÿ': 'y',
    'Ä': 'A',
    'Ö': 'O',
    'Ü': 'U',
    'Ÿ': 'Y',
    '°': 'º',
    '！': '!',
    '？': '?',
    # Typographic characters normalized to encodable equivalents.
    '‘': "'",   # ‘ → straight apostrophe (0xB4)
    '’': "'",   # ’ → straight apostrophe (0xB4)
    # Double quotes are directional: open guillemet/curly → "“" (0xB1),
    # close → "”" (0xB2). They previously collapsed to '"' → 0xB0, the
    # ellipsis glyph, so « cellules » rendered in-game as "… cellules …".
    # "“"/"”" themselves are NOT aliased here — they map to 0xB1/0xB2
    # directly in POKEMON_TABLE.
    '«': '“',   # « → left double quote glyph (0xB1)
    '»': '”',   # » → right double quote glyph (0xB2)
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
# Matches {FDxx}, {FCxx}, {FExx} etc. brace-style control-code tokens.
# These appear in combined_fr.txt and JSON translations as human-readable
# placeholders.  encode_pokemon emits them as raw 2-byte sequences when
# _apply_control_placeholders has not already expanded them.
BRACE_CTRL_RE = re.compile(r'^([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$')


def _resolve_straight_double_quotes(text: str) -> str:
    """Turn ambiguous straight ``"`` into directional quote glyphs.

    The font has no straight double-quote glyph: 0xB0 is the ellipsis, so a
    straight ``"`` left mapped there renders in-game as "…". A straight quote
    is therefore always a quotation mark; alternate open "“" (0xB1) / close
    "”" (0xB2) so balanced pairs render correctly. Worst case for an
    unbalanced run is a cosmetic open/close swap — never an ellipsis. Quote
    glyphs are one byte, like 0xB0, so string length (and pointers) are
    unaffected. Runs inside ``<0xNN>`` hex tokens are left untouched (they
    never contain ``"``).
    """
    if '"' not in text:
        return text
    out = []
    open_next = True
    for ch in text:
        if ch == '"':
            out.append('“' if open_next else '”')
            open_next = not open_next
        else:
            out.append(ch)
    return ''.join(out)


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

    @staticmethod
    def _parse_brace_token(text: str, index: int) -> Optional[Tuple[Tuple[int, ...], int]]:
        """Parse a {FDxx}-style brace control-code token.

        Returns (bytes_tuple, new_index) when the brace content is exactly four
        hex digits (two bytes), e.g. ``{FD24}`` → ``(0xFD, 0x24)``.  Returns
        None for {COLOR} and other non-hex brace tokens so the caller can fall
        through to positional-placeholder logic.
        """
        if text[index] != '{':
            return None
        end = text.find('}', index + 1)
        if end == -1:
            return None
        token = text[index + 1:end]
        match = BRACE_CTRL_RE.match(token)
        if not match:
            return None
        return (int(match.group(1), 16), int(match.group(2), 16)), end + 1

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
    def encode_pokemon(cls, text: str, skip_aliases: frozenset = frozenset()) -> bytes:
        for src, dst in ENCODE_ALIASES.items():
            if src not in skip_aliases:
                text = text.replace(src, dst)
        text = _resolve_straight_double_quotes(text)

        encoded = []
        i = 0
        while i < len(text):
            token = cls._parse_hex_token(text, i)
            if token:
                value, i = token
                encoded.append(value)
                continue

            brace = cls._parse_brace_token(text, i)
            if brace:
                (b0, b1), i = brace
                encoded.append(b0)
                encoded.append(b1)
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
    def encode(cls, text: str, encoding: str, skip_aliases: frozenset = frozenset()) -> bytes:
        if encoding == 'ascii':
            return cls.encode_ascii(text)
        if encoding == 'pokemon':
            return cls.encode_pokemon(text, skip_aliases=skip_aliases)
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
