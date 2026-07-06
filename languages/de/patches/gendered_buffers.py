#!/usr/bin/env python3
"""Patch gendered buffer strings (man/woman, boy/girl, son/daughter, her) to German.

Same mechanism as ``patch_gendered_buffers_fr.py``. These are small buffers
inserted by script opcode 85 (bufferstring) and referenced by many dialogues
via control codes like FD02 (STR_VAR_1).

The main build pipeline does not touch these because they are not part of
the pointer-extracted text corpus. This post-build patch applies German
translations after injection.

Every buffer is a FIXED-size slot (no relocation possible): the German word
must encode to no more bytes (including the 0xFF terminator) than the
English original occupied. Some English words have no German equivalent that
short:

  - "son" (Sohn, 4 letters) does not fit the 3-char budget freed by "son"
    itself — left in English, same as the FR script's documented limitation.
  - "man" / "Man" (Mann, 4 letters) do not fit the 3-char budget either —
    left in English.

Every other buffer below has a German word that fits within budget.
"""

import sys
import argparse
from pathlib import Path


# Gendered buffer pairs: (offset, expected_english_bytes, german_translation)
# Uses shorter DE translations to fit in the available buffer space.
GENDERED_BUFFERS = [
    # son/daughter buffers (4 pairs found in the ROM).
    # "son" has no 3-letter German equivalent ("Sohn" needs 4) -> left English.
    (0x417FD0, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'Tochter'),  # daughter
    (0x77F57F, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'Tochter'),  # daughter
    (0x7DE1E5, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'Tochter'),  # daughter
    (0x1F41B12, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'Tochter'),  # daughter

    # boy/girl buffers (2 pairs).
    # boy (3 bytes) -> Bub (3 bytes, colloquial German for "boy")
    # girl (4 bytes) -> Maid (4 bytes, poetic German for "girl/maiden")
    (0x793FCB, bytes.fromhex('d6e3edff'), 'Bub'),   # boy -> Bub
    (0x793FCF, bytes.fromhex('dbdde6e0ff'), 'Maid'),  # girl -> Maid
    (0x1F5B56D, bytes.fromhex('d6e3edff'), 'Bub'),   # boy -> Bub
    (0x1F5B571, bytes.fromhex('dbdde6e0ff'), 'Maid'),  # girl -> Maid

    # man/woman and man/lady buffers.
    # "man"/"Man" (Mann, 4 letters) do not fit the 3-char budget -> left English.
    # woman (6 bytes) -> Frau (5 bytes, fits)
    (0x008CE1FC, bytes.fromhex('e0d5d8edff'), 'Dame'),  # lady -> Dame
    (0x01FA17C8, bytes.fromhex('ebe3e1d5e2ff'), 'Frau'),  # woman -> Frau
    (0x01FA17CE, bytes.fromhex('d1e3e1d5e2ff'), 'Frau'),  # Woman -> Frau

    # her pronoun buffer (object pronoun loaded by bufferstring before dialogue).
    # her (3 bytes) -> ihr (3 bytes, fits in 4-byte slot)
    (0x78922E, bytes.fromhex('dcd9e6ff'), 'ihr'),   # her -> ihr
    (0x1FA7652, bytes.fromhex('dcd9e6ff'), 'ihr'),   # her -> ihr (second set)
]


# CFRU charmap: char -> byte value (includes the German umlaut slots
# patch_font_de.py adds glyphs for, though none of the words above need them).
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
    # German umlauts (slots 0xF1-0xF6, see languages/de/patches/font.py)
    'Ä': 0xF1, 'Ö': 0xF2, 'Ü': 0xF3, 'ä': 0xF4, 'ö': 0xF5, 'ü': 0xF6,
}

POKEMON_TERMINATOR = 0xFF


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
    """Patch all gendered buffer strings from English to German in the ROM."""

    if not rom_path.exists():
        raise FileNotFoundError(f"ROM not found: {rom_path}")

    rom_data = bytearray(rom_path.read_bytes())
    patched_count = 0

    for offset, expected_en, de_text in GENDERED_BUFFERS:
        # Read current bytes at offset
        current = rom_data[offset:offset + len(expected_en)]

        # Verify it matches expected English text
        if current != expected_en:
            print(f"⚠ Offset 0x{offset:08X}: expected {expected_en!r}, found {current!r}")
            print(f"  Skipping this entry (already patched or corrupted)")
            continue

        # Encode German translation
        de_encoded = encode_text(de_text)

        # Check if it fits in the same space
        if len(de_encoded) > len(expected_en):
            # German text is longer — need to relocate (not supported for buffers)
            print(f"🔴 Offset 0x{offset:08X}: DE '{de_text}' ({len(de_encoded)} bytes) "
                  f"is longer than EN bytes (expected {len(expected_en)} bytes)")
            print(f"  Cannot patch: buffers have fixed size")
            continue

        # Pad with zeros if needed
        de_encoded = de_encoded.ljust(len(expected_en), b'\x00')

        # Patch the ROM
        rom_data[offset:offset + len(expected_en)] = de_encoded
        patched_count += 1
        print(f"✓ 0x{offset:08X}: → '{de_text}'")

    # Write patched ROM back
    rom_path.write_bytes(rom_data)
    print(f"\n✓ Patched {patched_count}/{len(GENDERED_BUFFERS)} gendered buffers")


def main():
    parser = argparse.ArgumentParser(
        description="Patch gendered buffer strings (man/woman, boy/girl, son/daughter) to German"
    )
    parser.add_argument(
        "--rom", required=True, type=str,
        help="Path to the DE ROM to patch"
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
