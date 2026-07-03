#!/usr/bin/env python3
"""Patch gendered buffer strings (man/woman, boy/girl, son/daughter, her) to Italian.

Same mechanism as ``patch_gendered_buffers_fr.py``. These are small buffers
inserted by script opcode 85 (bufferstring) and referenced by many dialogues
via control codes like FD02 (STR_VAR_1).

The main build pipeline does not touch these because they are not part of
the pointer-extracted text corpus. This post-build patch applies Italian
translations after injection.

Every buffer is a FIXED-size slot (no relocation possible): the Italian word
must encode to no more bytes (including the 0xFF terminator) than the
English original occupied. Some English words have no Italian equivalent
that short:

  - "son" (figlio, 6 letters) does not fit the 3-char budget freed by "son"
    itself — left in English, same as the FR/DE scripts' documented
    limitation.
  - "boy" / "girl" (ragazzo/ragazza — no natural 3/4-letter Italian word) do
    not fit their 3/4-char budgets — left in English.
  - "man" / "Man" (uomo, 4 letters) do not fit the 3-char budget of "man"
    itself, but abbreviate cleanly to "uom" (3 letters, exact fit).

Every other buffer below has an Italian word that fits within budget.
"""

import sys
import argparse
from pathlib import Path


# Gendered buffer pairs: (offset, expected_english_bytes, italian_translation)
# Uses shorter IT translations to fit in the available buffer space.
GENDERED_BUFFERS = [
    # son/daughter buffers (4 pairs found in the ROM).
    # "son" has no 3-letter Italian equivalent ("figlio" needs 6) -> left English.
    (0x417FD0, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'figlia'),  # daughter
    (0x77F57F, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'figlia'),  # daughter
    (0x7DE1E5, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'figlia'),  # daughter
    (0x1F41B12, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'figlia'),  # daughter

    # boy/girl buffers (2 pairs) are left in English: no natural Italian word
    # fits the 3-char ("boy") / 4-char ("girl") budget without sounding forced.

    # man/woman and man/lady buffers.
    # man (3 bytes) → uom (3 bytes, abbrev of "uomo")
    # woman (6 bytes) → donna (5 bytes, exact fit)
    (0x008CE1F8, bytes.fromhex('e1d5e2ff'), 'uom'),   # man -> uom
    (0x008CE1FC, bytes.fromhex('e0d5d8edff'), 'dama'),  # lady -> dama
    (0x01FA17C0, bytes.fromhex('e1d5e2ff'), 'uom'),   # man -> uom
    (0x01FA17C4, bytes.fromhex('c7d5e2ff'), 'Uom'),   # Man -> Uom
    (0x01FA17C8, bytes.fromhex('ebe3e1d5e2ff'), 'donna'),  # woman -> donna
    (0x01FA17CE, bytes.fromhex('d1e3e1d5e2ff'), 'Donna'),  # Woman -> Donna

    # her pronoun buffer (object pronoun loaded by bufferstring before dialogue).
    # her (3 bytes) -> lei (3 bytes, fits in 4-byte slot)
    (0x78922E, bytes.fromhex('dcd9e6ff'), 'lei'),   # her -> lei
    (0x1FA7652, bytes.fromhex('dcd9e6ff'), 'lei'),   # her -> lei (second set)
]


# CFRU charmap: char -> byte value (includes the Italian accented-vowel slots
# patch_font_fr.py adds glyphs for, though none of the words above need them).
POKEMON_CHARMAP = {
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
    "'": 0xB4, '"': 0xB0, '/': 0xBA, ':': 0xF0,
    # Italian accented vowels
    'À': 0x01, 'È': 0x05, 'É': 0x06, 'Ì': 0x09, 'Ò': 0x0B, 'Ù': 0x0C,
    'à': 0x22, 'è': 0x26, 'é': 0x27, 'ì': 0x2A, 'ò': 0x2C, 'ù': 0x2D,
}

POKEMON_TERMINATOR = 0xFF
POKEMON_CHARMAP_REV = {v: k for k, v in POKEMON_CHARMAP.items()}


def _decode_word(data: bytes, offset: int) -> str:
    """Decode CFRU charmap bytes from offset up to the 0xFF terminator."""
    out = []
    for b in data[offset:]:
        if b == POKEMON_TERMINATOR:
            break
        out.append(POKEMON_CHARMAP_REV.get(b, "?"))
    return "".join(out)


def encode_text(text: str) -> bytes:
    """Encode a string to CFRU charmap bytes with terminator."""
    encoded = []
    for char in text:
        if char not in POKEMON_CHARMAP:
            raise ValueError(f"Character '{char}' not in CFRU charmap")
        encoded.append(POKEMON_CHARMAP[char])
    encoded.append(POKEMON_TERMINATOR)
    return bytes(encoded)


def patch_gendered_buffers(rom_path: Path) -> None:
    """Patch all gendered buffer strings from English to Italian in the ROM."""

    if not rom_path.exists():
        raise FileNotFoundError(f"ROM not found: {rom_path}")

    rom_data = bytearray(rom_path.read_bytes())
    patched_count = 0

    for offset, expected_en, it_text in GENDERED_BUFFERS:
        # Read current bytes at offset
        current = rom_data[offset:offset + len(expected_en)]

        # Verify it matches expected English text
        if current != expected_en:
            # combined_it.txt may already carry this exact offset as a plain
            # printable string (see patch_time_format_it.py's "Never"->"Mai"
            # docstring for the same root cause) — the initial build then
            # splices the Italian word in ahead of this script, leaving stray
            # original bytes past the new terminator. If the decoded word
            # already reads as our target, treat it as done rather than warn.
            if _decode_word(bytes(rom_data), offset) == it_text:
                continue
            print(f"⚠ Offset 0x{offset:08X}: expected {expected_en!r}, found {current!r}")
            print(f"  Skipping this entry (already patched or corrupted)")
            continue

        # Encode Italian translation
        it_encoded = encode_text(it_text)

        # Check if it fits in the same space
        if len(it_encoded) > len(expected_en):
            # Italian text is longer — need to relocate (not supported for buffers)
            print(f"🔴 Offset 0x{offset:08X}: IT '{it_text}' ({len(it_encoded)} bytes) "
                  f"is longer than EN bytes (expected {len(expected_en)} bytes)")
            print(f"  Cannot patch: buffers have fixed size")
            continue

        # Pad with zeros if needed
        it_encoded = it_encoded.ljust(len(expected_en), b'\x00')

        # Patch the ROM
        rom_data[offset:offset + len(expected_en)] = it_encoded
        patched_count += 1
        print(f"✓ 0x{offset:08X}: → '{it_text}'")

    # Write patched ROM back
    rom_path.write_bytes(rom_data)
    print(f"\n✓ Patched {patched_count}/{len(GENDERED_BUFFERS)} gendered buffers")


def main():
    parser = argparse.ArgumentParser(
        description="Patch gendered buffer strings (man/woman, boy/girl, son/daughter) to Italian"
    )
    parser.add_argument(
        "--rom", required=True, type=str,
        help="Path to the IT ROM to patch"
    )

    args = parser.parse_args()

    try:
        rom_path = Path(args.rom)
        patch_gendered_buffers(rom_path)
        print(f"✓ ROM patched: {rom_path}")
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
