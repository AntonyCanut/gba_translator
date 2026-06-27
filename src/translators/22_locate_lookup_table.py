#!/usr/bin/env python3
"""
22 - Locate the lookup table

Bytes 0x66, 0xBB, 0x33, 0xAA, 0x70, 0x88, 0x77, 0x11, 0x17, 0x71, 0xEE
are likely INDICES into a lookup table.

Looking for:
1. Where this table is stored
2. How it is used
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def find_lookup_table():
    """Search for the lookup table."""

    print()
    print("=" * 80)
    print("🔍 SEARCH: Lookup table")
    print("=" * 80)
    print()
    
    english_rom = ROMReader('input/roms/englishrom.gba')
    spanish_rom = ROMReader('input/roms/spanishrom.gba')
    english_rom.load()
    spanish_rom.load()
    
    # Observed index bytes
    common_bytes = [0x66, 0xBB, 0x33, 0xAA, 0x70, 0x88, 0x77, 0x11, 0x17, 0x71, 0xEE]

    print(f"📍 Observed index bytes: {[f'0x{b:02X}' for b in common_bytes]}")
    print()
    
    # Search for zones with a repetitive pattern
    # Lookup tables are often at aligned addresses (multiples of 4, 16, etc.)

    print("Searching for zones where these bytes replicate...\n")
    
    # Count occurrences of each byte in both ROMs
    for byte_val in common_bytes:
        en_count = english_rom.rom_data.count(bytes([byte_val]))
        es_count = spanish_rom.rom_data.count(bytes([byte_val]))

        print(f"Byte 0x{byte_val:02X}: EN={en_count} times, ES={es_count} times", end="")
        
        if en_count != es_count:
            print(f" ⚠️ Difference: {es_count - en_count}")
        else:
            print(" ✅ Identical count")
    
    print()
    print("=" * 80)
    print("ALTERNATIVE HYPOTHESIS: Corrupted/misread data")
    print("=" * 80)
    print()

    print("""
The high proportion of identical bytes (0x66, 0xBB, 0x33, 0xAA) suggests that
these zones do NOT contain VALID TEXT.

The "direct substitutions" we see could be:
1. PADDING/CORRUPTED DATA zones in the English ROM
2. Replaced by REAL TEXT in the Spanish ROM

Or conversely:
1. The English ROM contains NOISE/PADDING
2. The Spanish ROM cleaned it up or re-embedded it differently

The 11 failure cases could therefore be NON-TEXT ZONES
that our system correctly detects as problematic!
""")


if __name__ == "__main__":
    find_lookup_table()
