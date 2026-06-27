#!/usr/bin/env python3
"""
18 - Discover the relocation mechanism

Searches for relocation patterns in the Spanish ROM.
- Indirection tables
- Pointers
- Special markers
- Additional code zone
"""

import sys
import json
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def find_relocation_pattern():
    """Searches for relocation patterns."""
    
    report_path = Path('output/tests/2026-01-14_spanish_simulation_report.json')
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    failures = report['failures']
    
    # Load ROMs
    english_rom = ROMReader('input/roms/englishrom.gba')
    spanish_rom = ROMReader('input/roms/spanishrom.gba')
    english_rom.load()
    spanish_rom.load()
    
    print()
    print("=" * 80)
    print("🔍 SEARCH: Relocation mechanism")
    print("=" * 80)
    print()
    
    # Collect all failure offsets
    failure_offsets = [int(f['offset'], 16) for f in failures]

    print(f"📍 Offsets to analyze: {len(failure_offsets)}")
    for i, offset in enumerate(failure_offsets, 1):
        print(f"   {i:2d}. 0x{offset:08X}")
    
    print()
    print("=" * 80)
    print("HYPOTHESIS 1: Special marker vs different encoding")
    print("=" * 80)
    print()
    
    for offset in failure_offsets:
        # Retrieve the byte at the offset in both ROMs
        en_byte = english_rom.rom_data[offset]
        es_byte = spanish_rom.rom_data[offset]

        print(f"0x{offset:08X}: EN=0x{en_byte:02X} ({chr(en_byte) if 32 <= en_byte <= 126 else '?'}), "
              f"ES=0x{es_byte:02X} ({chr(es_byte) if 32 <= es_byte <= 126 else '?'})")

        # Search for a recurring pattern
        if es_byte in [0xFF, 0xFE, 0x00, 0x01, 0x02]:
            print(f"      → Special marker detected: 0x{es_byte:02X}")
    
    print()
    print("=" * 80)
    print("HYPOTHESIS 2: Pointer indirection")
    print("=" * 80)
    print()
    
    for offset in failure_offsets:
        # Before each failed offset, look for a valid GBA pointer
        for back_offset in [4, 8, 12, 16, 20]:
            ptr_offset = offset - back_offset
            if ptr_offset >= 0:
                # Read as little-endian pointer
                ptr_bytes = english_rom.rom_data[ptr_offset:ptr_offset+4]
                ptr_value = struct.unpack('<I', ptr_bytes)[0]

                # Check if it's a valid GBA pointer (starts with 0x08)
                if (ptr_value & 0xFF000000) == 0x08000000:
                    rom_offset = ptr_value - 0x08000000
                    es_ptr_value = struct.unpack('<I', spanish_rom.rom_data[ptr_offset:ptr_offset+4])[0]

                    if ptr_value != es_ptr_value:
                        print(f"0x{offset:08X} - Pointer at -0x{back_offset:02X}:")
                        print(f"   EN: 0x{ptr_value:08X} → 0x{rom_offset:08X}")
                        print(f"   ES: 0x{es_ptr_value:08X}")
                        print(f"   → DIFFERENT! May indicate a relocation")
                        print()
                        break
    
    print()
    print("=" * 80)
    print("HYPOTHESIS 3: Alternative encoding (compression, lookup table)")
    print("=" * 80)
    print()
    
    for i, offset in enumerate(failure_offsets[:3]):  # First 3 cases
        print(f"\nCase {i+1}: 0x{offset:08X}")
        
        # Extract 30 bytes before and 50 after the offset
        start = max(0, offset - 30)
        end = min(len(english_rom.rom_data), offset + 50)
        
        en_data = english_rom.rom_data[start:end]
        es_data = spanish_rom.rom_data[start:end]
        
        marker = offset - start
        
        print(f"EN: {' '.join(f'{b:02x}' for b in en_data[:marker])} [{en_data[marker]:02x}] {' '.join(f'{b:02x}' for b in en_data[marker+1:])}")
        print(f"ES: {' '.join(f'{b:02x}' for b in es_data[:marker])} [{es_data[marker]:02x}] {' '.join(f'{b:02x}' for b in es_data[marker+1:])}")
        
        # Search for patterns
        # Terminator bytes
        if en_data[marker] == 0x00 and es_data[marker] != 0x00:
            print(f"→ Terminator MISSING in ES at this offset")

        if en_data[marker] == 0xFF and es_data[marker] != 0xFF:
            print(f"→ Padding terminator MODIFIED")

        # Check if ES continues after where EN stops
        en_term_pos = None
        for j in range(marker, min(marker+30, len(en_data))):
            if en_data[j] == 0x00:
                en_term_pos = j
                break

        if en_term_pos:
            print(f"→ EN ends at +{en_term_pos - marker} bytes")
            print(f"→ ES at this position: 0x{es_data[en_term_pos]:02x}")
    
    print()
    print("=" * 80)
    print("HYPOTHESIS 4: Is the data in the Spanish ROM?")
    print("=" * 80)
    print()
    
    # Load extracted texts
    with open('output/extracted_texts/spanishrom_texts.json', 'r', encoding='utf-8') as f:
        spanish_texts = json.load(f)

    # For each failed case, search for the Spanish text at other offsets
    found_relocations = 0

    for failure in failures[:3]:  # First 3 cases
        offset = int(failure['offset'], 16)
        english_text = failure['english_text']
        spanish_text = failure['spanish_text']

        print(f"\nOffset {hex(offset)}:")
        print(f"  EN: \"{english_text}\"")
        print(f"  ES: \"{spanish_text}\"")

        # Check if this Spanish text exists elsewhere in the ROM
        # (this is an approximation)
        # Normally we would search within the structure
        print(f"  → To investigate: where is this text embedded in ES?")


if __name__ == "__main__":
    find_relocation_pattern()
