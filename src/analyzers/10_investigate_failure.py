#!/usr/bin/env python3
"""
Investigation Script - Analyze Specific Failure Case

Investigates the failure at offset 0x00A44125 to understand why
the Spanish translation doesn't fit and how to fix it properly.
"""

import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.rom_reader import ROMReader
from core.padding_detector import PaddingDetector
from core.text_codec import TextDecoder


def investigate_offset(english_rom_path: str, spanish_rom_path: str, offset: int):
    """
    Investigate a specific offset in both ROMs.

    Args:
        english_rom_path: Path to English ROM
        spanish_rom_path: Path to Spanish ROM
        offset: Offset to investigate (file offset, not GBA)
    """
    print(f"\n{'='*80}")
    print(f"INVESTIGATION: Offset 0x{offset:08X}")
    print(f"{'='*80}\n")

    # Load ROMs
    english_rom = ROMReader(english_rom_path)
    english_rom.load()

    spanish_rom = ROMReader(spanish_rom_path)
    spanish_rom.load()

    # Read English text
    print("1. ENGLISH ROM ANALYSIS")
    print("-" * 80)

    english_bytes = []
    pos = offset
    while pos < len(english_rom.rom_data):
        byte = english_rom.rom_data[pos]
        english_bytes.append(byte)
        if byte == 0xFF:  # Pokemon text terminator
            break
        pos += 1
        if len(english_bytes) > 100:  # Safety
            break

    english_text_pokemon = TextDecoder.decode_pokemon(bytes(english_bytes))
    english_text_ascii = TextDecoder.decode_ascii(bytes(english_bytes))

    print(f"Offset:         0x{offset:08X}")
    print(f"Bytes (hex):    {' '.join(f'{b:02X}' for b in english_bytes[:20])}")
    print(f"Text (Pokemon): '{english_text_pokemon}'")
    print(f"Text (ASCII):   '{english_text_ascii}'")
    print(f"Length:         {len(english_bytes)} bytes (including 0xFF)")

    # Check padding after English text
    print(f"\nPadding after English text:")
    padding_start = offset + len(english_bytes)
    padding_bytes = []
    for i in range(50):  # Check 50 bytes
        if padding_start + i >= len(english_rom.rom_data):
            break
        byte = english_rom.rom_data[padding_start + i]
        padding_bytes.append(byte)
        if byte not in [0x00, 0xFF]:
            break

    print(f"Padding bytes:  {' '.join(f'{b:02X}' for b in padding_bytes)}")
    print(f"Padding count:  {len([b for b in padding_bytes if b in [0x00, 0xFF]])} bytes")

    # Extended padding search
    detector = PaddingDetector(english_rom)
    basic_padding = detector.detect_padding(offset, len(english_bytes), extended_search=False)
    extended_padding_count = detector.detect_padding(offset, len(english_bytes), extended_search=True)
    print(f"\nPadding search:")
    print(f"  Basic:    {basic_padding} bytes")
    print(f"  Extended: {extended_padding_count} bytes")

    # Read Spanish text
    print(f"\n2. SPANISH ROM ANALYSIS")
    print("-" * 80)

    spanish_bytes = []
    pos = offset
    while pos < len(spanish_rom.rom_data):
        byte = spanish_rom.rom_data[pos]
        spanish_bytes.append(byte)
        if byte == 0xFF:  # Pokemon text terminator
            break
        pos += 1
        if len(spanish_bytes) > 100:  # Safety
            break

    spanish_text_pokemon = TextDecoder.decode_pokemon(bytes(spanish_bytes))
    spanish_text_ascii = TextDecoder.decode_ascii(bytes(spanish_bytes))

    print(f"Offset:         0x{offset:08X}")
    print(f"Bytes (hex):    {' '.join(f'{b:02X}' for b in spanish_bytes[:25])}")
    print(f"Text (Pokemon): '{spanish_text_pokemon}'")
    print(f"Text (ASCII):   '{spanish_text_ascii}'")
    print(f"Length:         {len(spanish_bytes)} bytes (including 0xFF)")

    # Check padding after Spanish text
    print(f"\nPadding after Spanish text:")
    padding_start = offset + len(spanish_bytes)
    padding_bytes = []
    for i in range(50):  # Check 50 bytes
        if padding_start + i >= len(spanish_rom.rom_data):
            break
        byte = spanish_rom.rom_data[padding_start + i]
        padding_bytes.append(byte)
        if byte not in [0x00, 0xFF]:
            break

    print(f"Padding bytes:  {' '.join(f'{b:02X}' for b in padding_bytes)}")
    print(f"Padding count:  {len([b for b in padding_bytes if b in [0x00, 0xFF]])} bytes")

    # Check if Spanish text was relocated
    print(f"\n3. RELOCATION ANALYSIS")
    print("-" * 80)

    if len(spanish_bytes) > len(english_bytes) + extended_padding_count:
        print("Spanish text is LONGER than available space")
        print("Checking if text was relocated in Spanish ROM...")

        # Search for the Spanish text elsewhere in the ROM
        search_text = bytes(spanish_bytes[:10])  # First 10 bytes
        print(f"\nSearching for: {' '.join(f'{b:02X}' for b in search_text)}")

        found_offsets = []
        for i in range(len(spanish_rom.rom_data) - len(search_text)):
            if spanish_rom.rom_data[i:i+len(search_text)] == search_text:
                found_offsets.append(i)

        print(f"Found {len(found_offsets)} occurrence(s):")
        for found_offset in found_offsets:
            print(f"  - 0x{found_offset:08X}")
            if found_offset != offset:
                print(f"    → Different from original offset! (relocated)")

                # Check if there's a pointer to this new location
                # Look for pointers in the region around the original offset
                print(f"    Checking for pointers to 0x{found_offset:08X}...")
                target_ptr = found_offset + 0x08000000  # Convert to GBA pointer

                # Search in a reasonable range (e.g., tables are usually before text data)
                search_start = max(0, offset - 0x10000)
                search_end = min(len(spanish_rom.rom_data) - 4, offset + 0x1000)

                for ptr_offset in range(search_start, search_end, 4):
                    ptr_value = int.from_bytes(
                        spanish_rom.rom_data[ptr_offset:ptr_offset+4],
                        byteorder='little'
                    )
                    if ptr_value == target_ptr:
                        print(f"    ✓ Found pointer at 0x{ptr_offset:08X} → 0x{target_ptr:08X}")
    else:
        print("Spanish text fits in available space")

    # Comparison
    print(f"\n4. COMPARISON")
    print("-" * 80)
    print(f"English length: {len(english_bytes)} bytes")
    print(f"Spanish length: {len(spanish_bytes)} bytes")
    print(f"Difference:     {len(spanish_bytes) - len(english_bytes):+d} bytes")
    print(f"Available pad:  {extended_padding_count} bytes")
    print(f"Real max:       {len(english_bytes) + extended_padding_count} bytes")

    if len(spanish_bytes) > len(english_bytes) + extended_padding_count:
        overflow = len(spanish_bytes) - (len(english_bytes) + extended_padding_count)
        print(f"OVERFLOW:       {overflow} bytes over limit")
        print(f"\n⚠️  This text CANNOT fit without relocation")
    else:
        print(f"✓ This text CAN fit in available space")

    # Check encoding issues
    print(f"\n5. ENCODING ANALYSIS")
    print("-" * 80)

    # Check for ? characters that might be encoding issues
    if '?' in spanish_text_ascii or '?' in spanish_text_pokemon:
        print("⚠️  Found '?' characters in Spanish text")
        print("This might indicate encoding issues")

        # Show byte-by-byte comparison
        print(f"\nByte-by-byte analysis:")
        for i, byte in enumerate(spanish_bytes[:len(spanish_text_ascii)]):
            char_pokemon = TextDecoder.decode_pokemon(bytes([byte]))
            char_ascii = TextDecoder.decode_ascii(bytes([byte]))
            print(f"  {i:2d}. 0x{byte:02X} → Pokemon: '{char_pokemon}' | ASCII: '{char_ascii}'")
            if char_ascii == '?' or char_pokemon == '?':
                print(f"      ^ Potential encoding issue")

    print(f"\n{'='*80}\n")


def main():
    """Main function."""
    # Paths
    english_rom_path = Path("input/roms/englishrom.gba")
    spanish_rom_path = Path("input/roms/spanishrom.gba")

    if not english_rom_path.exists():
        print(f"Error: {english_rom_path} not found")
        return

    if not spanish_rom_path.exists():
        print(f"Error: {spanish_rom_path} not found")
        return

    # Investigate the failing offset
    failing_offset = 0x00A44125

    investigate_offset(
        str(english_rom_path),
        str(spanish_rom_path),
        failing_offset
    )

    print("\n" + "="*80)
    print("INVESTIGATION COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. Analyze the findings above")
    print("2. Determine root cause of the failure")
    print("3. Implement a generic fix based on the analysis")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
