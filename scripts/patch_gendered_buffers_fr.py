#!/usr/bin/env python3
"""Patch gendered buffer strings (man/woman, boy/girl, son/daughter) to French.

These are small buffers inserted by script opcode 85 (bufferstring) and
referenced by many dialogues via control codes like FD02 (STR_VAR_1).

The main build pipeline does not touch these because they are not part of
the pointer-extracted text corpus. This post-build patch applies the
French translations from combined_fr.txt after injection.
"""

import sys
import argparse
from pathlib import Path


# Gendered buffer pairs: (offset, expected_english_bytes, french_translation)
# Uses shorter FR translations to fit in the available buffer space
GENDERED_BUFFERS = [
    # son/daughter buffers (4 pairs found in the ROM)
    # son (3 bytes) → son (FR same word, 3 bytes)
    (0x417FCC, bytes.fromhex('e7e3e2ff'), 'son'),  # son stays 'son' in FR
    (0x417FD0, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'fille'),  # daughter
    (0x77F57B, bytes.fromhex('e7e3e2ff'), 'son'),  # son
    (0x77F57F, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'fille'),  # daughter
    (0x7DE1E1, bytes.fromhex('e7e3e2ff'), 'son'),  # son
    (0x7DE1E5, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'fille'),  # daughter
    (0x1F41B0E, bytes.fromhex('e7e3e2ff'), 'son'),  # son
    (0x1F41B12, bytes.fromhex('d8d5e9dbdce8d9e6ff'), 'fille'),  # daughter

    # boy/girl buffers (2 pairs)
    # boy (3 bytes) → gon (3 bytes, from garçon)
    # girl (4 bytes) → girl (FR: fille, 5 bytes - doesn't fit)
    (0x793FCB, bytes.fromhex('d6e3edff'), 'gon'),  # boy → gon (part of garçon)
    (0x793FCF, bytes.fromhex('dbdde6e0ff'), 'fille'),  # girl → fille (5 bytes, as is)
    (0x1F5B56D, bytes.fromhex('d6e3edff'), 'gon'),  # boy → gon
    (0x1F5B571, bytes.fromhex('dbdde6e0ff'), 'fille'),  # girl → fille

    # man/woman and man/lady buffers
    # man (3 bytes) → hom (3 bytes, from homme)
    # woman (6 bytes) → femme (5 bytes - might fit)
    (0x008CE1F8, bytes.fromhex('e1d5e2ff'), 'hom'),  # man → hom
    (0x008CE1FC, bytes.fromhex('e0d5d8edff'), 'dame'),  # lady
    (0x01FA17C0, bytes.fromhex('e1d5e2ff'), 'hom'),  # man → hom
    (0x01FA17C4, bytes.fromhex('c7d5e2ff'), 'Hom'),  # Man → Hom
    (0x01FA17C8, bytes.fromhex('ebe3e1d5e2ff'), 'femme'),  # woman
    (0x01FA17CE, bytes.fromhex('d1e3e1d5e2ff'), 'Femme'),  # Woman
]


# CFRU charmap: char -> byte value
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
    # French accented characters
    'À': 0x01, 'Á': 0x02, 'Â': 0x03, 'Ç': 0x04, 'È': 0x05, 'É': 0x06,
    'Ê': 0x07, 'Ë': 0x08, 'Î': 0x09, 'Ï': 0x0A, 'Ô': 0x0B, 'Ù': 0x0C,
    'Û': 0x0D, 'Ü': 0x0E, 'Ñ': 0x0F, 'Ö': 0x10,
    'à': 0x22, 'á': 0x23, 'â': 0x24, 'ç': 0x25, 'è': 0x26, 'é': 0x27,
    'ê': 0x28, 'ë': 0x29, 'î': 0x2A, 'ï': 0x2B, 'ô': 0x2C, 'ù': 0x2D,
    'û': 0x2E, 'ü': 0x2F, 'ñ': 0x30, 'ö': 0x31, 'œ': 0x32,
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
    """Patch all gendered buffer strings from English to French in the ROM."""

    if not rom_path.exists():
        raise FileNotFoundError(f"ROM not found: {rom_path}")

    rom_data = bytearray(rom_path.read_bytes())
    patched_count = 0

    for offset, expected_en, fr_text in GENDERED_BUFFERS:
        # Read current bytes at offset
        current = rom_data[offset:offset + len(expected_en)]

        # Verify it matches expected English text
        if current != expected_en:
            print(f"⚠ Offset 0x{offset:08X}: expected {expected_en!r}, found {current!r}")
            print(f"  Skipping this entry (already patched or corrupted)")
            continue

        # Encode French translation
        fr_encoded = encode_text(fr_text)

        # Check if it fits in the same space
        if len(fr_encoded) > len(expected_en):
            # French text is longer — need to relocate (not supported for buffers)
            print(f"🔴 Offset 0x{offset:08X}: FR '{fr_text}' ({len(fr_encoded)} bytes) "
                  f"is longer than EN bytes (expected {len(expected_en)} bytes)")
            print(f"  Cannot patch: buffers have fixed size")
            continue

        # Pad with zeros if needed
        fr_encoded = fr_encoded.ljust(len(expected_en), b'\x00')

        # Patch the ROM
        rom_data[offset:offset + len(expected_en)] = fr_encoded
        patched_count += 1
        print(f"✓ 0x{offset:08X}: → '{fr_text}'")

    # Write patched ROM back
    rom_path.write_bytes(rom_data)
    print(f"\n✓ Patched {patched_count}/{len(GENDERED_BUFFERS)} gendered buffers")


def main():
    parser = argparse.ArgumentParser(
        description="Patch gendered buffer strings (man/woman, boy/girl, son/daughter) to French"
    )
    parser.add_argument(
        "--rom", required=True, type=str,
        help="Path to the FR ROM to patch"
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
